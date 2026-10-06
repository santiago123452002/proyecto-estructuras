from .arbol_avl import ArbolAVL
from .evento import Evento, ValidacionError
from .zona import pertenece_a_zona_poblada
from .resultado_reporte import ResultadoReporte, TipoResultadoReporte
from .asociaciones import candidatos, elegir_referencia


class Catalogo:
    """
    Wraps the Phase 1 ArbolAVL and handles what the tree cannot resolve
    on its own: locating an event by identifier. The AVL is ordered by
    K = (P, M, I), so searching by I by traversing the tree would cost O(n)
    in the worst case.

    Auxiliary structure chosen: dictionary identifier -> active AVL Node.
    - Operation cost: O(1) on average (hashing an integer).
    - Memory cost: O(n) additional, one entry per active event.
    Alternative discarded: maintaining a parallel list sorted by I and
    reordering it after every change — the statement itself prohibits it
    as the exclusive management mechanism (section 2), and it also costs
    O(n log n) per reordering instead of O(1).

    In addition to the active AVL, the history is currently kept in memory
    (two id->Event dictionaries: archived and deleted). JSON persistence
    comes in Phase 7; this dictionary is exactly what will be serialized then.

    Implements: event registration, querying, and manual correction (section 6);
    report processing through a queue with stress mode (sections 6 and 8);
    individual deletion and subtree archiving (section 10); and
    candidate/aftershock associations between events (section 7).
    """

    def __init__(self):
        self.avl = ArbolAVL()
        self._indice_por_id = {}    # id -> Nodo activo
        self._archivados = {}       # id -> Evento (histórico, sección 10)
        self._eliminados = {}       # id -> Evento (histórico, sección 10)
        self._asociaciones = {}     # id_b -> id_a (referencia elegida, sección 7)

        # Parameters configurable by the user (sections 7, 9, and 10).
        self.w_horas = 48.0
        self.r_km = 40.0
        self.t_horas = 72.0
        self.l_profundidad = 3

        # Accumulated metrics (section 14). They are updated within
        # the operations themselves (registration, correction, report
        # processing, archiving) as they occur; undoing an action also restores
        # these counters because they live inside Catalog and the entire
        # Catalog is copied in each Escenario snapshot.
        self.metricas = {
            "correcciones_aceptadas": 0,
            "altas_nuevas": 0,
            "confirmaciones": 0,
            "conflictos": 0,
            "reportes_antiguos": 0,
            "reportes_rechazados_invalidos": 0,
            "eliminaciones": 0,
            "archivos_masivos": 0,
            "eventos_archivados_total": 0,
        }
        self.l_profundidad = 3

    def __len__(self):
        return len(self._indice_por_id)

    # ---------------- estado de un identificador ----------------

    def esta_activo(self, identificador):
        return identificador in self._indice_por_id

    def esta_archivado(self, identificador):
        return identificador in self._archivados

    def esta_eliminado(self, identificador):
        return identificador in self._eliminados

    def identificador_en_uso(self, identificador):
        """An identifier is not reused for another earthquake (section 3),
        whether it is archived or deleted, not just active."""
        return (self.esta_activo(identificador) or self.esta_archivado(identificador)
                or self.esta_eliminado(identificador))

    def _evento_activo_o_archivado(self, identificador):
        nodo = self._indice_por_id.get(identificador)
        if nodo is not None:
            return nodo.elemento
        return self._archivados.get(identificador)

    # ---------------- alta manual (sección 6) ----------------

    def alta_evento(self, identificador, magnitud, profundidad, epicentro_x, epicentro_y,
                     fecha_hora, estacion_origen, zonas, reloj_simulacion):
        """
        If any data is invalid or the identifier already exists (active,
        archived, or deleted), no structure is modified and a ValidacionError
        is raised with the cause. If everything is valid, the registration is
        executed as a single action: P is calculated, K is constructed, the
        event is inserted into the AVL, the event is marked as pending, and
        associations are updated.
        """
        if self.identificador_en_uso(identificador):
            raise ValidacionError(f"El identificador {identificador} ya está en uso.")

        if fecha_hora > reloj_simulacion:
            raise ValidacionError(
                "La fecha y hora de ocurrencia no puede ser posterior al reloj de simulación."
            )

        evento = Evento(identificador, magnitud, profundidad, epicentro_x, epicentro_y,
                         fecha_hora, estacion_origen, revision=1)

        en_zona_poblada = pertenece_a_zona_poblada(evento.epicentro_x, evento.epicentro_y, zonas)
        evento.actualizar_prioridad(en_zona_poblada)

        nodo = self.avl.insertar(evento)
        self._indice_por_id[identificador] = nodo
        self._recalcular_todas_las_asociaciones()
        self.metricas["altas_nuevas"] += 1
        return evento

    # ---------------- consulta (sección 6) ----------------

    def consultar_evento(self, identificador):
        """
        Returns (event, nodes_visited). If it is not active, event is
        None. `nodes_visited` is the simulated cost from section 9: it is
        obtained by searching again by key in the AVL (depth + 1), even though
        the actual location by identifier uses the O(1) index.
        """
        nodo = self._indice_por_id.get(identificador)
        if nodo is None:
            return None, 0
        _, visitados = self.avl.buscar_nodo(nodo.clave)
        return nodo.elemento, visitados

    # ---------------- corrección manual (sección 6) ----------------

    def corregir_evento(self, identificador, zonas, reloj_simulacion, **cambios):
        """
        `cambios` accepts any of: magnitude, depth,
        epicenter_x, epicenter_y, date_time. The identifier never
        changes. The revision increases by 1 whenever the correction is
        applied, even if the resulting key is the same as the previous one.

        The ENTIRE proposed state is validated before modifying the tree; if
        anything fails, no partial change is applied.
        """
        nodo = self._indice_por_id.get(identificador)
        if nodo is None:
            raise ValidacionError(f"El identificador {identificador} no corresponde a un evento activo.")

        evento_actual = nodo.elemento
        clave_anterior = evento_actual.clave

        magnitud = cambios.get("magnitud", evento_actual.magnitud)
        profundidad = cambios.get("profundidad", evento_actual.profundidad)
        epicentro_x = cambios.get("epicentro_x", evento_actual.epicentro_x)
        epicentro_y = cambios.get("epicentro_y", evento_actual.epicentro_y)
        fecha_hora = cambios.get("fecha_hora", evento_actual.fecha_hora)

        if fecha_hora > reloj_simulacion:
            raise ValidacionError(
                "La fecha y hora de ocurrencia no puede ser posterior al reloj de simulación."
            )

        propuesto = Evento(
            identificador, magnitud, profundidad, epicentro_x, epicentro_y, fecha_hora,
            estacion_origen=next(iter(evento_actual.estaciones)),
            revision=evento_actual.revision + 1,
        )

        en_zona_poblada = pertenece_a_zona_poblada(propuesto.epicentro_x, propuesto.epicentro_y, zonas)
        propuesto.actualizar_prioridad(en_zona_poblada)
        propuesto.estaciones = set(evento_actual.estaciones)
        propuesto.estado_atencion = "pendiente"

        if propuesto.clave == clave_anterior:
            nodo.elemento = propuesto
        else:
            self.avl.eliminar(clave_anterior)
            nuevo_nodo = self.avl.insertar(propuesto)
            self._indice_por_id[identificador] = nuevo_nodo

        self._recalcular_todas_las_asociaciones()
        self.metricas["correcciones_aceptadas"] += 1
        return propuesto

    # ---------------- marcar como revisado (sección 6) ----------------

    def marcar_revisado(self, identificador):
        """Does not modify P, M, or I: the key and position in the AVL do not change."""
        nodo = self._indice_por_id.get(identificador)
        if nodo is None:
            raise ValidacionError(f"El identificador {identificador} no corresponde a un evento activo.")
        nodo.elemento.estado_atencion = "revisado"
        return nodo.elemento

    # ---------------- eliminación individual (sección 6 y 10) ----------------

    def eliminar_evento(self, identificador, balancear=True):
        """
        Removes ONLY the selected event from the active AVL. The other
        nodes remain active, including those that were descendants of this
        node in the tree (the AVL is a storage structure; it does not
        represent domain relationships between earthquakes). Their data is
        stored in the deleted history, affected associations are updated,
        and the identifier is retired: it cannot be reused or reactivated
        by a report (it can only be recovered by undoing the deletion or
        restoring a version, when that module exists).
        """
        nodo = self._indice_por_id.get(identificador)
        if nodo is None:
            raise ValidacionError(f"El identificador {identificador} no corresponde a un evento activo.")

        evento = nodo.elemento
        self.avl.eliminar(evento.clave, balancear=balancear)
        del self._indice_por_id[identificador]

        self._eliminados[identificador] = evento
        self._asociaciones.pop(identificador, None)
        self._recalcular_todas_las_asociaciones()
        self.metricas["eliminaciones"] += 1
        return evento

    # ---------------- archivo de subárboles (sección 10) ----------------

    def archivar_rama_antigua(self, reloj_simulacion, balancear=True):
        """
        "Archive branch of old events": evaluates ALL subtrees
        of the active AVL. A subtree is eligible if ALL of its events
        have low priority and an age strictly greater than
        `self.t_horas` (age = simulation clock - occurrence time).
        Among eligible branches, the one with the largest
        number of nodes is selected; tie -> greatest root depth;
        tie -> greatest root identifier. A leaf also counts as a subtree;
        if the entire tree is eligible, it is archived completely.

        The set of affected identifiers is determined BEFORE modifying
        the tree (the existing topology is read when the operation starts),
        so rotations that occur while removing nodes one by one cannot add
        or exclude events from that set.

        Returns the list of archived identifiers, or [] if there is no
        eligible branch (in that case, nothing is modified).
        """
        def es_elegible(evento):
            antiguedad_horas = (reloj_simulacion - evento.fecha_hora).total_seconds() / 3600.0
            return evento.prioridad == 1 and antiguedad_horas > self.t_horas

        candidatas = self.avl.subarboles_elegibles(es_elegible)
        if not candidatas:
            return []

        nodo_raiz, _cantidad, _profundidad = max(
            candidatas,
            key=lambda c: (c[1], c[2], c[0].elemento.identificador),
        )

        eventos_afectados = self._eventos_del_subarbol(nodo_raiz)
        identificadores_afectados = [e.identificador for e in eventos_afectados]

        for evento in eventos_afectados:
            self.avl.eliminar(evento.clave, balancear=balancear)
            del self._indice_por_id[evento.identificador]
            self._archivados[evento.identificador] = evento

        # DO NOT call _recalcular_todas_las_asociaciones() or modify
        # self._asociaciones here: section 7 is explicit ("simple
        # archiving does not change those relationships"). An archived event
        # still counts as "available" to be a candidate/reference for
        # other events (see _eventos_disponibles_para_asociacion), and the
        # history preserves its associations for querying (section 10)
        # -- so archiving has nothing to recalculate or delete.
        self.metricas["archivos_masivos"] += 1
        self.metricas["eventos_archivados_total"] += len(identificadores_afectados)
        return identificadores_afectados

    @staticmethod
    def _eventos_del_subarbol(nodo):
        """List of events from an AVL subtree, read only once
        (before modifying anything), as required by section 10."""
        resultado = []

        def recorrer(actual):
            if actual is not None:
                resultado.append(actual.elemento)
                recorrer(actual.izquierdo)
                recorrer(actual.derecho)

        recorrer(nodo)
        return resultado

    # ---------------- procesamiento de reportes (sección 6 y 8) ----------------

    def procesar_reporte(self, reporte, zonas, reloj_simulacion, balancear=True):
        """
        Applies the decision table from section 6 to a Report received
        from the queue. Returns a ResultadoReporte; it never raises an
        exception for invalid business data (this is translated into a
        RECHAZADO_INVALIDO result), so queue processing never stops
        halfway through a burst.

        `balancear=False` is stress mode (section 8): registrations and
        updates preserve BST ordering without rotations.
        """
        identificador = reporte.identificador

        # A deleted identifier remains retired: its subsequent
        # reports are rejected until the deletion is undone.
        if self.esta_eliminado(identificador):
            return ResultadoReporte(
                TipoResultadoReporte.RECHAZADO_ELIMINADO,
                f"El identificador {identificador} fue eliminado; no puede reactivarse por reporte.",
            )

        nodo = self._indice_por_id.get(identificador)

        # Unknown identifier (neither active nor archived): new registration.
        # The first received revision may be greater than 1.
        if nodo is None and not self.esta_archivado(identificador):
            return self._alta_por_reporte(reporte, zonas, reloj_simulacion, balancear)

        # Archived: a higher and valid revision reactivates it as
        # pending; a confirmation or an old report does NOT reactivate it.
        if nodo is None and self.esta_archivado(identificador):
            return self._procesar_reporte_para_archivado(reporte, identificador, zonas,
                                                           reloj_simulacion, balancear)

        # Active identifier: compare revisions.
        evento_actual = nodo.elemento

        if reporte.revision < evento_actual.revision:
            self.metricas["reportes_antiguos"] += 1
            return ResultadoReporte(
                TipoResultadoReporte.ANTIGUO,
                f"El reporte de {identificador} trae una revisión antigua "
                f"({reporte.revision} < {evento_actual.revision}); se descarta.",
            )

        if reporte.revision == evento_actual.revision:
            if evento_actual.datos_iguales(reporte.magnitud, reporte.profundidad,
                                            reporte.epicentro_x, reporte.epicentro_y,
                                            reporte.fecha_hora):
                evento_actual.estaciones.add(reporte.estacion)
                self.metricas["confirmaciones"] += 1
                return ResultadoReporte(
                    TipoResultadoReporte.CONFIRMADO,
                    f"Reporte de {identificador} confirmado por {reporte.estacion}.",
                    evento_actual,
                )
            self.metricas["conflictos"] += 1
            return ResultadoReporte(
                TipoResultadoReporte.CONFLICTO,
                f"Conflicto en {identificador}: misma revisión ({reporte.revision}) con datos "
                "distintos. Se rechaza sin sobrescribir los datos del evento.",
            )

        # reporte.revision > evento_actual.revision: sustituir datos vigentes.
        return self._actualizar_por_reporte(nodo, evento_actual, reporte, zonas,
                                             reloj_simulacion, balancear)

    def _alta_por_reporte(self, reporte, zonas, reloj_simulacion, balancear):
        try:
            if reporte.fecha_hora > reloj_simulacion:
                raise ValidacionError(
                    "La fecha y hora de ocurrencia no puede ser posterior al reloj de simulación."
                )
            evento = Evento(reporte.identificador, reporte.magnitud, reporte.profundidad,
                             reporte.epicentro_x, reporte.epicentro_y, reporte.fecha_hora,
                             reporte.estacion, revision=reporte.revision)
        except ValidacionError as error:
            self.metricas["reportes_rechazados_invalidos"] += 1
            return ResultadoReporte(TipoResultadoReporte.RECHAZADO_INVALIDO, str(error))

        en_zona_poblada = pertenece_a_zona_poblada(evento.epicentro_x, evento.epicentro_y, zonas)
        evento.actualizar_prioridad(en_zona_poblada)

        nuevo_nodo = self.avl.insertar(evento, balancear=balancear)
        self._indice_por_id[reporte.identificador] = nuevo_nodo
        self._recalcular_todas_las_asociaciones()
        self.metricas["altas_nuevas"] += 1
        return ResultadoReporte(
            TipoResultadoReporte.ALTA_NUEVA,
            f"Evento {reporte.identificador} registrado como nuevo (revisión {evento.revision}).",
            evento,
        )

    def _actualizar_por_reporte(self, nodo, evento_actual, reporte, zonas, reloj_simulacion, balancear):
        clave_anterior = evento_actual.clave
        try:
            if reporte.fecha_hora > reloj_simulacion:
                raise ValidacionError(
                    "La fecha y hora de ocurrencia no puede ser posterior al reloj de simulación."
                )
            propuesto = Evento(reporte.identificador, reporte.magnitud, reporte.profundidad,
                                reporte.epicentro_x, reporte.epicentro_y, reporte.fecha_hora,
                                reporte.estacion, revision=reporte.revision)
        except ValidacionError as error:
            self.metricas["reportes_rechazados_invalidos"] += 1
            return ResultadoReporte(TipoResultadoReporte.RECHAZADO_INVALIDO, str(error))

        en_zona_poblada = pertenece_a_zona_poblada(propuesto.epicentro_x, propuesto.epicentro_y, zonas)
        propuesto.actualizar_prioridad(en_zona_poblada)
        propuesto.estaciones = set(evento_actual.estaciones)
        propuesto.estaciones.add(reporte.estacion)
        propuesto.estado_atencion = "pendiente"

        if propuesto.clave == clave_anterior:
            nodo.elemento = propuesto
        else:
            self.avl.eliminar(clave_anterior, balancear=balancear)
            nuevo_nodo = self.avl.insertar(propuesto, balancear=balancear)
            self._indice_por_id[reporte.identificador] = nuevo_nodo

        self._recalcular_todas_las_asociaciones()
        self._recalcular_todas_las_asociaciones()
        self.metricas["correcciones_aceptadas"] += 1
        return ResultadoReporte(
            TipoResultadoReporte.ACTUALIZADO,
            f"Evento {reporte.identificador} actualizado a revisión {propuesto.revision} "
            f"(clave {propuesto.clave}).",
            propuesto,
        )

    def _procesar_reporte_para_archivado(self, reporte, identificador, zonas,
                                          reloj_simulacion, balancear):
        evento_archivado = self._archivados[identificador]

        if reporte.revision < evento_archivado.revision:
            self.metricas["reportes_antiguos"] += 1
            return ResultadoReporte(
                TipoResultadoReporte.ANTIGUO,
                f"El reporte de {identificador} trae una revisión antigua respecto al "
                "evento archivado; se descarta.",
            )

        if reporte.revision == evento_archivado.revision:
            if evento_archivado.datos_iguales(reporte.magnitud, reporte.profundidad,
                                               reporte.epicentro_x, reporte.epicentro_y,
                                               reporte.fecha_hora):
                evento_archivado.estaciones.add(reporte.estacion)
                self.metricas["confirmaciones"] += 1
                return ResultadoReporte(
                    TipoResultadoReporte.CONFIRMADO,
                    f"Reporte de {identificador} confirmado (evento archivado, no se reactiva).",
                    evento_archivado,
                )
            self.metricas["conflictos"] += 1
            return ResultadoReporte(
                TipoResultadoReporte.CONFLICTO,
                f"Conflicto en {identificador} (evento archivado): misma revisión con "
                "datos distintos.",
            )

        # revisión mayor y válida: reactiva el evento como pendiente
        try:
            if reporte.fecha_hora > reloj_simulacion:
                raise ValidacionError(
                    "La fecha y hora de ocurrencia no puede ser posterior al reloj de simulación."
                )
            evento_nuevo = Evento(identificador, reporte.magnitud, reporte.profundidad,
                                   reporte.epicentro_x, reporte.epicentro_y, reporte.fecha_hora,
                                   reporte.estacion, revision=reporte.revision)
        except ValidacionError as error:
            self.metricas["reportes_rechazados_invalidos"] += 1
            return ResultadoReporte(TipoResultadoReporte.RECHAZADO_INVALIDO, str(error))

        en_zona_poblada = pertenece_a_zona_poblada(evento_nuevo.epicentro_x,
                                                     evento_nuevo.epicentro_y, zonas)
        evento_nuevo.actualizar_prioridad(en_zona_poblada)
        evento_nuevo.estaciones = set(evento_archivado.estaciones)
        evento_nuevo.estaciones.add(reporte.estacion)
        evento_nuevo.estado_atencion = "pendiente"

        del self._archivados[identificador]
        nuevo_nodo = self.avl.insertar(evento_nuevo, balancear=balancear)
        self._indice_por_id[identificador] = nuevo_nodo
        self._recalcular_todas_las_asociaciones()
        self.metricas["altas_nuevas"] += 1

        return ResultadoReporte(
            TipoResultadoReporte.ALTA_NUEVA,
            f"Evento {identificador} reactivado desde el histórico (revisión {evento_nuevo.revision}).",
            evento_nuevo,
        )

    # ---------------- asociaciones candidato/réplica (sección 7) ----------------

    def configurar_asociaciones(self, w_horas=None, r_km=None):
        """Changes W and/or R (both must be positive) and recalculates ALL
        associations, as required by section 7."""
        if w_horas is not None:
            if w_horas <= 0:
                raise ValidacionError("W debe ser un valor positivo.")
            self.w_horas = w_horas
        if r_km is not None:
            if r_km <= 0:
                raise ValidacionError("R debe ser un valor positivo.")
            self.r_km = r_km
        self._recalcular_todas_las_asociaciones()

    def configurar_t_horas(self, t_horas):
        """Changes T (must be positive), used by archivar_rama_antigua."""
        if t_horas <= 0:
            raise ValidacionError("T debe ser un valor positivo.")
        self.t_horas = t_horas

    def _eventos_disponibles_para_asociacion(self):
        """Active + archived; never deleted (section 7)."""
        return [nodo.elemento for nodo in self._indice_por_id.values()] + list(self._archivados.values())

    def _recalcular_todas_las_asociaciones(self):
        """
        Recalculates the candidate/aftershock association for ALL
        active and archived events. All are recalculated because a change in
        any event (or in W/R) can alter the set of candidates for any other
        event occurring later in time.

        Cost: O(n^2) in the worst case (for each event, all
        other events are traversed). Acceptable for the scenario size of this
        project; a reasonable future optimization would be to recalculate
        only the events that occurred after the changed event, within the
        W window (the only ones whose candidate set can be affected).
        """
        disponibles = self._eventos_disponibles_para_asociacion()
        nuevas_asociaciones = {}
        for evento_b in disponibles:
            lista_candidatos = candidatos(evento_b, disponibles, self.w_horas, self.r_km)
            referencia = elegir_referencia(evento_b, lista_candidatos)
            if referencia is not None:
                nuevas_asociaciones[evento_b.identificador] = referencia.identificador
        self._asociaciones = nuevas_asociaciones

    def candidatos_de(self, identificador):
        """List of events that are candidates to be the reference for `identifier`
        (active or archived)."""
        evento = self._evento_activo_o_archivado(identificador)
        if evento is None:
            raise ValidacionError(
                f"El identificador {identificador} no corresponde a un evento activo ni archivado."
            )
        disponibles = self._eventos_disponibles_para_asociacion()
        return candidatos(evento, disponibles, self.w_horas, self.r_km)

    def referencia_de(self, identificador):
        """Identifier of the event chosen as the reference/aftershock for
        `identifier`, or None if it has no association."""
        return self._asociaciones.get(identificador)

    def eventos_que_referencian(self, identificador):
        """Identifiers of the events that use `identifier`
        as their reference."""
        return [id_b for id_b, id_a in self._asociaciones.items() if id_a == identificador]

    # ---------------- stress mode: global recovery (section 8) ----------------
    def esta_balanceado(self):
        return self.avl.esta_balanceado()

    def recuperar_equilibrio(self):
        """
        Restores the AVL property throughout the entire catalog after a burst
        in stress mode. Rotations do not create or destroy nodes, so the
        identifier->node index remains valid without modifying it.
        Returns True if the tree is balanced.
        """
        return self.avl.recuperar_equilibrio()

    # ---------------- consultas (sección 11) ----------------

    def configurar_l_profundidad(self, l_profundidad):
        """L (section 9): depth limit for marking costly access.
        Must be a non-negative integer."""
        if not isinstance(l_profundidad, int) or l_profundidad < 0:
            raise ValidacionError("L debe ser un entero no negativo.")
        self.l_profundidad = l_profundidad

    def pendientes_top_k(self, k):
        """
        Query 1: the first k ACTIVE events pending
        attention, in DESCENDING order of K. If there are fewer than k
        pending events, all available events are returned.

        Cost: reverse traversal (right, node, left) of the AVL -- visits
        keys from highest to lowest, exactly the requested order -- and
        STOPS as soon as k pending events have been collected. This pruning
        is safe because any unvisited node has a key smaller than all
        already visited nodes (due to the BST property), so it could never
        displace any of the k events already found.
        In the worst case (the last k nodes in descending order
        are the only pending ones), the entire tree is traversed,
        O(n).

        Returns (list_of_events, nodes_visited).
        """
        if not isinstance(k, int) or k <= 0:
            raise ValidacionError("k debe ser un entero positivo.")

        resultado = []
        visitados = [0]

        def recorrer(nodo):
            if nodo is None or len(resultado) >= k:
                return
            recorrer(nodo.derecho)
            if len(resultado) >= k:
                return
            visitados[0] += 1
            if nodo.elemento.estado_atencion == "pendiente":
                resultado.append(nodo.elemento)
            if len(resultado) >= k:
                return
            recorrer(nodo.izquierdo)

        recorrer(self.avl.raiz)
        return resultado, visitados[0]

    def buscar_por_filtros(self, magnitud_min=None, magnitud_max=None, profundidad_max=None,
                            fecha_inicio=None, fecha_fin=None):
        """
        Query 2: ACTIVE events with magnitude within an inclusive interval,
        hypocenter depth less than or equal to a limit,
        and occurrence date within an inclusive interval. All
        filters are optional (None = no restriction on that field).

        Cost: the AVL key K is ordered by (priority, magnitude, id),
        not by depth or date, so none of the filters in this
        query match the tree ordering -- there is no safe way to
        prune branches. The entire tree is traversed, O(n).

        Returns (list_of_events, nodes_visited).
        """
        resultado = []
        visitados = [0]

        def cumple(evento):
            if magnitud_min is not None and evento.magnitud < magnitud_min:
                return False
            if magnitud_max is not None and evento.magnitud > magnitud_max:
                return False
            if profundidad_max is not None and evento.profundidad > profundidad_max:
                return False
            if fecha_inicio is not None and evento.fecha_hora < fecha_inicio:
                return False
            if fecha_fin is not None and evento.fecha_hora > fecha_fin:
                return False
            return True

        def recorrer(nodo):
            if nodo is None:
                return
            recorrer(nodo.izquierdo)
            visitados[0] += 1
            if cumple(nodo.elemento):
                resultado.append(nodo.elemento)
            recorrer(nodo.derecho)

        recorrer(self.avl.raiz)
        return resultado, visitados[0]

    def consultar_asociaciones(self, identificador):
        """
        Query 3: candidates and selected reference for an event, and
        the events that use IT as their reference. Unlike
        the other queries, THIS one also considers the history (archived,
        not deleted) — this is explicitly required by section 11.
        Each result indicates whether it is active or archived.
        """
        if not (self.esta_activo(identificador) or self.esta_archivado(identificador)):
            raise ValidacionError(
                f"El identificador {identificador} no corresponde a un evento activo ni archivado."
            )

        def _con_estado(identificador_evento):
            estado = "activo" if self.esta_activo(identificador_evento) else "archivado"
            return {"identificador": identificador_evento, "estado": estado}

        lista_candidatos = [_con_estado(e.identificador) for e in self.candidatos_de(identificador)]
        referencia_id = self.referencia_de(identificador)
        referencia = _con_estado(referencia_id) if referencia_id is not None else None
        referenciado_por = [_con_estado(i) for i in self.eventos_que_referencian(identificador)]

        return {
            "candidatos": lista_candidatos,
            "referencia": referencia,
            "referenciado_por": referenciado_por,
        }

    def eventos_prioridad_alta_con_acceso_costoso(self):
        """
        Query 4: ACTIVE events with high priority whose depth
        in the tree is strictly greater than L (section 9). For each
        one, its depth, the current L limit, and the nodes
        visited in its key search (depth + 1) are provided.

        Cost: O(n) to traverse the active events, plus O(depth)
        for each high-priority event to locate it -- in the worst case
        (a tree degraded in stress mode) this is O(n^2); in a normally
        balanced AVL it is O(n log n).

        Returns (list_of_dicts, total_nodes_visited).
        """
        resultado = []
        total_visitados = 0
        for nodo in self._indice_por_id.values():
            evento = nodo.elemento
            if evento.prioridad != 3:
                continue
            profundidad_nodo = self.avl.profundidad(nodo.clave)
            if profundidad_nodo is not None and profundidad_nodo > self.l_profundidad:
                _, visitados = self.avl.buscar_nodo(nodo.clave)
                total_visitados += visitados
                resultado.append({
                    "identificador": evento.identificador,
                    "profundidad": profundidad_nodo,
                    "limite": self.l_profundidad,
                    "nodos_visitados": visitados,
                })
        return resultado, total_visitados

    # ---------------- audit: "Verify structure" (section 14) ----------------

    def verificar_estructura(self, modo="normal"):
        """
        Checks, for the ENTIRE tree (not just the immediate child of each
        node): global BST ordering by K, identifier uniqueness,
        that references are consistent (parent/child pointers, and
        candidate/aftershock associations point to events that
        actually exist and do not reference themselves), and that
        heights and balance factors match those recalculated
        from the actual structure.

        In normal mode, a balance factor outside {-1, 0, 1} is an
        ERROR. In stress mode, it is reported separately as an "expected
        imbalance" (it is not an error by itself, since stress mode
        intentionally postpones balancing) -- but BST ordering errors
        or metadata errors (heights, parents, identifiers, associations)
        remain errors in any mode.

        Returns {"ok": bool, "errores": [...], "desbalances_esperados": [...]}.
        """
        errores = []
        desbalances_esperados = []
        identificadores_vistos = set()
        claves = []

        def recorrer(nodo, padre_esperado):
            if nodo is None:
                return
            if nodo.padre is not padre_esperado:
                errores.append(
                    f"El nodo {nodo.elemento.identificador} tiene un puntero 'padre' inconsistente."
                )
            recorrer(nodo.izquierdo, nodo)

            if nodo.elemento.identificador in identificadores_vistos:
                errores.append(f"Identificador duplicado en el árbol: {nodo.elemento.identificador}.")
            identificadores_vistos.add(nodo.elemento.identificador)
            claves.append(nodo.clave)

            altura_izq = nodo.izquierdo.altura if nodo.izquierdo is not None else -1
            altura_der = nodo.derecho.altura if nodo.derecho is not None else -1
            altura_calculada = 1 + max(altura_izq, altura_der)
            if nodo.altura != altura_calculada:
                errores.append(
                    f"Altura almacenada del nodo {nodo.elemento.identificador} ({nodo.altura}) "
                    f"no coincide con la recalculada ({altura_calculada})."
                )

            factor = altura_izq - altura_der
            if factor not in (-1, 0, 1):
                if modo == "normal":
                    errores.append(
                        f"Factor de balance del nodo {nodo.elemento.identificador} "
                        f"fuera de rango: {factor}."
                    )
                else:
                    desbalances_esperados.append(
                        f"Nodo {nodo.elemento.identificador} con factor de balance {factor} "
                        "(esperado en modo estrés)."
                    )

            recorrer(nodo.derecho, nodo)

        recorrer(self.avl.raiz, None)

        if claves != sorted(claves):
            errores.append("El orden global BST por la clave K no se respeta.")

        if len(identificadores_vistos) != len(self.avl):
            errores.append(
                f"La cantidad de nodos recorridos ({len(identificadores_vistos)}) no coincide "
                f"con la cantidad registrada en el árbol ({len(self.avl)})."
            )

        disponibles = {e.identificador for e in self._eventos_disponibles_para_asociacion()}
        for id_b, id_a in self._asociaciones.items():
            if id_b == id_a:
                errores.append(f"Asociación inválida: el evento {id_b} se referencia a sí mismo.")
            elif id_a not in disponibles:
                errores.append(
                    f"La asociación del evento {id_b} apunta a un identificador "
                    f"inexistente o no disponible: {id_a}."
                )

        return {
            "ok": len(errores) == 0,
            "errores": errores,
            "desbalances_esperados": desbalances_esperados,
        }