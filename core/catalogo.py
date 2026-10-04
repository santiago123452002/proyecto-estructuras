from .arbol_avl import ArbolAVL
from .evento import Evento, ValidacionError
from .zona import pertenece_a_zona_poblada
from .resultado_reporte import ResultadoReporte, TipoResultadoReporte
from .asociaciones import candidatos, elegir_referencia


class Catalogo:
    """
    Envuelve el ArbolAVL de la Fase 1 y resuelve lo que el árbol no
    puede resolver solo: localizar un evento por identificador. El AVL
    ordena por K = (P, M, I), así que buscar por I recorriendo el árbol
    costaría O(n) en el peor caso.

    Estructura auxiliar elegida: diccionario identificador -> Nodo
    activo del AVL.
      - Costo por operación: O(1) promedio (hash de un entero).
      - Costo de memoria: O(n) adicional, una entrada por evento activo.
    Alternativa descartada: mantener una lista paralela ordenada por I
    y reordenarla tras cada cambio — el propio enunciado la prohíbe como
    mecanismo exclusivo de gestión (sección 2), y además cuesta O(n log n)
    por reordenamiento en vez de O(1).

    Además del AVL activo, se mantiene el histórico en memoria por ahora
    (dos diccionarios id->Evento: archivados y eliminados). La
    persistencia en JSON llega en la Fase 7; este diccionario es
    exactamente lo que se va a serializar entonces.

    Implementa: alta, consulta y corrección manual (sección 6);
    procesamiento de reportes por cola con modo estrés (sección 6 y 8);
    eliminación individual y archivo de subárboles (sección 10); y
    asociaciones candidato/réplica entre eventos (sección 7).
    """

    def __init__(self):
        self.avl = ArbolAVL()
        self._indice_por_id = {}    # id -> Nodo activo
        self._archivados = {}       # id -> Evento (histórico, sección 10)
        self._eliminados = {}       # id -> Evento (histórico, sección 10)
        self._asociaciones = {}     # id_b -> id_a (referencia elegida, sección 7)

        # Parámetros configurables por el usuario (secciones 7, 9 y 10).
        self.w_horas = 48.0
        self.r_km = 40.0
        self.t_horas = 72.0
        self.l_profundidad = 3

        # Indicadores acumulados (sección 14). Se actualizan dentro de
        # las propias operaciones (alta, corrección, procesamiento de
        # reportes, archivo) según ocurren; deshacer una acción restaura
        # también estos contadores, porque viven dentro de Catalogo y
        # Catalogo entero se copia en cada snapshot de Escenario.
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
        """Un identificador no se reutiliza para otro terremoto (sección 3),
        así esté archivado o eliminado, no solo activo."""
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
        Si algún dato es inválido o el identificador ya existe (activo,
        archivado o eliminado), no se modifica ninguna estructura y se
        lanza ValidacionError con la causa. Si todo es válido, ejecuta
        el alta como una sola acción: calcula P, construye K, inserta en
        el AVL, marca el evento como pendiente y actualiza asociaciones.
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
        Devuelve (evento, nodos_visitados). Si no está activo, evento es
        None. `nodos_visitados` es el costo simulado de la sección 9: se
        obtiene rebuscando por clave en el AVL (profundidad + 1), aunque
        la localización real por identificador use el índice en O(1).
        """
        nodo = self._indice_por_id.get(identificador)
        if nodo is None:
            return None, 0
        _, visitados = self.avl.buscar_nodo(nodo.clave)
        return nodo.elemento, visitados

    # ---------------- corrección manual (sección 6) ----------------

    def corregir_evento(self, identificador, zonas, reloj_simulacion, **cambios):
        """
        `cambios` acepta cualquiera de: magnitud, profundidad,
        epicentro_x, epicentro_y, fecha_hora. El identificador nunca
        cambia. La revisión sube en 1 siempre que la corrección se
        aplique, aunque la clave resultante sea igual a la anterior.

        Se valida TODO el estado propuesto antes de tocar el árbol; si
        algo falla, no se aplica ningún cambio parcial.
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
        """No modifica P, M ni I: la clave y la posición en el AVL no cambian."""
        nodo = self._indice_por_id.get(identificador)
        if nodo is None:
            raise ValidacionError(f"El identificador {identificador} no corresponde a un evento activo.")
        nodo.elemento.estado_atencion = "revisado"
        return nodo.elemento

    # ---------------- eliminación individual (sección 6 y 10) ----------------

    def eliminar_evento(self, identificador, balancear=True):
        """
        Retira SOLO el evento seleccionado del AVL activo. Los demás
        nodos permanecen activos, incluidos los que eran descendientes
        de este en el árbol (el AVL es una estructura de almacenamiento;
        no representa relaciones de dominio entre terremotos). Se
        guardan sus datos en el histórico de eliminados, se actualizan
        las asociaciones afectadas, y el identificador queda retirado:
        no puede reutilizarse ni reactivarse por reporte (solo se
        recupera deshaciendo la eliminación o restaurando una versión,
        cuando exista ese módulo).
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
        "Archivar rama de eventos antiguos": evalúa TODOS los subárboles
        del AVL activo. Un subárbol es elegible si TODOS sus eventos
        tienen prioridad baja y antigüedad estrictamente mayor que
        `self.t_horas` (antigüedad = reloj de simulación - hora de
        ocurrencia). Entre las ramas elegibles se elige la de mayor
        cantidad de nodos; empate -> mayor profundidad de la raíz;
        empate -> mayor identificador de la raíz. Una hoja también
        cuenta como subárbol; si todo el árbol es elegible, se archiva
        completo.

        El conjunto de identificadores afectados se fija ANTES de tocar
        el árbol (se lee la topología existente al iniciar la
        operación), así que las rotaciones que ocurran mientras se
        retiran uno por uno no pueden añadir ni excluir eventos de ese
        conjunto.

        Devuelve la lista de identificadores archivados, o [] si no
        existe ninguna rama elegible (en ese caso no se modifica nada).
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

        # NO se llama a _recalcular_todas_las_asociaciones() ni se toca
        # self._asociaciones aquí: la sección 7 es explícita ("un simple
        # archivo no cambia esas relaciones"). Un evento archivado sigue
        # contando como "disponible" para ser candidato/referencia de
        # otros (ver _eventos_disponibles_para_asociacion), y el
        # histórico conserva sus asociaciones para consulta (sección 10)
        # -- así que archivar no tiene nada que recalcular ni que borrar.
        self.metricas["archivos_masivos"] += 1
        self.metricas["eventos_archivados_total"] += len(identificadores_afectados)
        return identificadores_afectados

    @staticmethod
    def _eventos_del_subarbol(nodo):
        """Lista de eventos de un subárbol del AVL, leída de una sola
        vez (antes de modificar nada), tal como exige la sección 10."""
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
        Aplica la tabla de decisión de la sección 6 a un Reporte recibido
        de la cola. Devuelve un ResultadoReporte; nunca lanza una
        excepción por datos de negocio inválidos (eso se traduce en un
        resultado RECHAZADO_INVALIDO), para que el procesamiento de la
        cola nunca se detenga a mitad de una ráfaga.

        `balancear=False` es el modo estrés (sección 8): las altas y
        actualizaciones se hacen conservando el orden BST, sin rotar.
        """
        identificador = reporte.identificador

        # Un identificador eliminado se conserva como retirado: sus
        # reportes posteriores se rechazan hasta deshacer la eliminación.
        if self.esta_eliminado(identificador):
            return ResultadoReporte(
                TipoResultadoReporte.RECHAZADO_ELIMINADO,
                f"El identificador {identificador} fue eliminado; no puede reactivarse por reporte.",
            )

        nodo = self._indice_por_id.get(identificador)

        # Identificador desconocido (ni activo ni archivado): alta nueva.
        # La primera revisión recibida puede ser mayor que 1.
        if nodo is None and not self.esta_archivado(identificador):
            return self._alta_por_reporte(reporte, zonas, reloj_simulacion, balancear)

        # Archivado: una revisión mayor y válida lo reactiva como
        # pendiente; una confirmación o un reporte antiguo NO lo reactiva.
        if nodo is None and self.esta_archivado(identificador):
            return self._procesar_reporte_para_archivado(reporte, identificador, zonas,
                                                           reloj_simulacion, balancear)

        # Identificador activo: comparar revisiones.
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
        """Cambia W y/o R (ambos deben ser positivos) y recalcula TODAS
        las asociaciones, como exige la sección 7."""
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
        """Cambia T (debe ser positivo), usado por archivar_rama_antigua."""
        if t_horas <= 0:
            raise ValidacionError("T debe ser un valor positivo.")
        self.t_horas = t_horas

    def _eventos_disponibles_para_asociacion(self):
        """Activos + archivados; nunca eliminados (sección 7)."""
        return [nodo.elemento for nodo in self._indice_por_id.values()] + list(self._archivados.values())

    def _recalcular_todas_las_asociaciones(self):
        """
        Recalcula la asociación candidato/réplica de TODOS los eventos
        activos y archivados. Se recalculan todos porque un cambio en
        cualquier evento (o en W/R) puede alterar el conjunto de
        candidatos de cualquier otro evento posterior en el tiempo.

        Costo: O(n^2) en el peor caso (por cada evento se recorren todos
        los demás). Aceptable para el tamaño de escenario de este
        proyecto; una optimización futura razonable sería recalcular
        solo los eventos ocurridos después del que cambió, dentro de la
        ventana W (los únicos cuyo conjunto de candidatos puede verse
        afectado).
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
        """Lista de eventos candidatos a referencia de `identificador`
        (activo o archivado)."""
        evento = self._evento_activo_o_archivado(identificador)
        if evento is None:
            raise ValidacionError(
                f"El identificador {identificador} no corresponde a un evento activo ni archivado."
            )
        disponibles = self._eventos_disponibles_para_asociacion()
        return candidatos(evento, disponibles, self.w_horas, self.r_km)

    def referencia_de(self, identificador):
        """Identificador del evento elegido como referencia/réplica de
        `identificador`, o None si no tiene ninguna asociación."""
        return self._asociaciones.get(identificador)

    def eventos_que_referencian(self, identificador):
        """Identificadores de los eventos que usan a `identificador`
        como su referencia."""
        return [id_b for id_b, id_a in self._asociaciones.items() if id_a == identificador]

    # ---------------- modo estrés: recuperación global (sección 8) ----------------

    def esta_balanceado(self):
        return self.avl.esta_balanceado()

    def recuperar_equilibrio(self):
        """
        Restaura la propiedad AVL en todo el catálogo tras una ráfaga en
        modo estrés. Las rotaciones no crean ni destruyen nodos, así que
        el índice identificador->nodo sigue siendo válido sin tocarlo.
        Devuelve True si el árbol quedó balanceado.
        """
        return self.avl.recuperar_equilibrio()

    # ---------------- consultas (sección 11) ----------------

    def configurar_l_profundidad(self, l_profundidad):
        """L (sección 9): límite de profundidad para marcar acceso
        costoso. Debe ser un entero no negativo."""
        if not isinstance(l_profundidad, int) or l_profundidad < 0:
            raise ValidacionError("L debe ser un entero no negativo.")
        self.l_profundidad = l_profundidad

    def pendientes_top_k(self, k):
        """
        Consulta 1: los primeros k eventos ACTIVOS pendientes de
        atención, en orden DESCENDENTE de K. Si hay menos de k
        pendientes, devuelve todos los disponibles.

        Costo: recorrido inverso (derecho, nodo, izquierdo) del AVL --
        visita las claves de mayor a menor, exactamente el orden que se
        pide -- y se DETIENE apenas junta k pendientes. Esa poda es
        segura porque cualquier nodo que quede sin visitar tiene una
        clave menor que todos los ya vistos (por la propiedad BST), así
        que nunca podría desplazar a ninguno de los k ya encontrados.
        En el peor caso (los últimos k nodos en orden descendente
        resultan ser los únicos pendientes) se recorre el árbol
        completo, O(n).

        Devuelve (lista_de_eventos, nodos_visitados).
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
        Consulta 2: eventos ACTIVOS con magnitud dentro de un intervalo
        inclusivo, profundidad del hipocentro menor o igual a un límite,
        y fecha de ocurrencia dentro de un intervalo inclusivo. Todos
        los filtros son opcionales (None = sin restricción en ese campo).

        Costo: la clave K del AVL ordena por (prioridad, magnitud, id),
        no por profundidad ni por fecha, así que ningún filtro de esta
        consulta coincide con el orden del árbol -- no hay forma de
        podar ramas con seguridad. Se recorre el árbol completo, O(n).

        Devuelve (lista_de_eventos, nodos_visitados).
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
        Consulta 3: candidatos y referencia elegida para un evento, y
        los eventos que lo usan a ÉL como referencia. A diferencia de
        las demás consultas, ESTA sí considera el histórico (archivados,
        no eliminados) — así lo exige la sección 11 explícitamente.
        Cada resultado indica si está activo o archivado.
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
        Consulta 4: eventos ACTIVOS de prioridad alta cuya profundidad
        en el árbol es estrictamente mayor que L (sección 9). Para cada
        uno se indica profundidad, el límite L vigente, y los nodos
        visitados en su búsqueda por clave (profundidad + 1).

        Costo: O(n) para recorrer los eventos activos, más O(profundidad)
        por cada uno de prioridad alta para ubicarlo -- en el peor caso
        (árbol degradado en modo estrés) esto es O(n^2); en un AVL
        balanceado normal es O(n log n).

        Devuelve (lista_de_dicts, total_nodos_visitados).
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

    # ---------------- auditoría: "Verificar estructura" (sección 14) ----------------

    def verificar_estructura(self, modo="normal"):
        """
        Comprueba, para TODO el árbol (no solo el hijo inmediato de cada
        nodo): el orden global BST por K, unicidad de identificadores,
        que las referencias sean consistentes (punteros padre/hijo, y
        que las asociaciones candidato/réplica apunten a eventos que
        realmente existen y no se referencien a sí mismos), y que las
        alturas y factores de balance coincidan con los recalculados
        desde la estructura real.

        En modo normal, un factor de balance fuera de {-1, 0, 1} es un
        ERROR. En modo estrés se reporta aparte como "desbalance
        esperado" (no es un error en sí mismo, ya que el modo estrés
        aplaza el balanceo a propósito) -- pero los errores de orden BST
        o de metadatos (alturas, padres, identificadores, asociaciones)
        siguen siendo errores en cualquier modo.

        Devuelve {"ok": bool, "errores": [...], "desbalances_esperados": [...]}.
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