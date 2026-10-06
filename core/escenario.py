import copy

from .catalogo import Catalogo
from .cola_reportes import ColaReportes
from .evento import ValidacionError
from .pila import Pila
from .procesador_reportes import procesar_siguiente
from .resultado_reporte import TipoResultadoReporte

# Attributes that make up the scenario's "operating state": what
# section 13 requires recovering when undoing or restoring a version
# ("data, history, references, queue, clock, parameters, mode, and
# metrics"). `_pila_deshacer` and `versiones` are deliberately left OUT:
# they are administrative metadata of the undo mechanism itself, not
# part of the scenario being simulated (the statement confirms it:
# "[versions] do not need to contain the undo stack or other
# versions").
_CAMPOS_ESTADO = ("catalogo", "cola", "zonas", "reloj_simulacion", "modo", "metricas")


class Escenario:
    """
    Orchestrates the Catalog (AVL + history + associations), the report
    queue, the simulation clock, and the execution mode as a single
    undoable unit, as required by section 13: "Each registration,
    correction, deletion, mass archive, parameter change, clock advance,
    attention change, load, and global recovery is an independent
    action" — and "each queue-processing step is also an action".

    Chosen undo strategy: BEFORE each action a COMPLETE COPY (deep copy)
    of the operating state is saved on the stack; undo simply restores
    the most recent copy. Saving only each action's "delta" (for example,
    which rotations occurred) was discarded because undoing it exactly
    would require inverting every rotation one by one, and the statement
    already clarifies that "the internal insertions and rotations of a
    correction or mass archive are not undone separately" — that is, the
    required granularity is that of the complete ACTION, not of each
    internal step. Copying the whole state is simpler to verify as
    correct, at the cost of more memory per step: each snapshot costs
    O(n) in time and memory, proportional to the total number of events
    (active + history) plus the size of the pending queue.

    If an action fails (it raises ValidacionError because the data is
    invalid), the copy is discarded without being pushed: since none of
    the Catalog operations modify anything before validating, there is
    no need to undo an action that never took effect.
    """

    def __init__(self, zonas=None, reloj_simulacion=None):
        self.catalogo = Catalogo()
        self.cola = ColaReportes()
        self.zonas = zonas if zonas is not None else []
        self.reloj_simulacion = reloj_simulacion
        self.modo = "normal"  # "normal" | "estres"
        self.metricas = {
            "reportes_procesados": 0,
            "correcciones_aceptadas": 0,
            "reportes_descartados": 0,
            "conflictos": 0,
            "archivos_masivos": 0,
        }

        self._pila_deshacer = Pila()
        self.versiones = {}  # name -> snapshot of the operating state

    # ---------------- undo mechanism ----------------

    def _capturar_estado(self):
        """Complete copy (deep copy) of the operating fields."""
        return {campo: copy.deepcopy(getattr(self, campo)) for campo in _CAMPOS_ESTADO}

    def _restaurar_estado(self, estado):
        for campo, valor in estado.items():
            setattr(self, campo, valor)

    def _ejecutar_con_deshacer(self, funcion, *args, **kwargs):
        """
        Captures the state, runs `funcion`, and pushes the previous copy
        only if it did not raise. Returns whatever `funcion` returns.
        """
        snapshot = self._capturar_estado()
        resultado = funcion(*args, **kwargs)
        self._pila_deshacer.apilar(snapshot)
        return resultado

    def deshacer(self):
        """
        Restores the state saved at the last undo point.
        Returns True if something was undone, False if there was no
        pending action to undo.
        """
        if self._pila_deshacer.esta_vacia():
            return False
        estado_anterior = self._pila_deshacer.desapilar()
        self._restaurar_estado(estado_anterior)
        return True

    def hay_algo_que_deshacer(self):
        return not self._pila_deshacer.esta_vacia()

    # ---------------- persistent named versions ----------------

    def guardar_version(self, nombre):
        """Saves (or overwrites) a named copy of the current operating
        state. It does not include the undo stack or other versions,
        as required by the statement."""
        self.versiones[nombre] = self._capturar_estado()

    def restaurar_version(self, nombre):
        """
        Restores a saved version. It is itself an action that can be
        undone: the current state is pushed before applying the version,
        so a later `deshacer()` returns exactly to how the scenario was
        just before the restore.
        """
        if nombre not in self.versiones:
            raise ValidacionError(f"No existe una versión guardada con el nombre '{nombre}'.")

        def _restaurar():
            # a COPY of what was saved is applied, so later changes
            # to the scenario never contaminate the stored version
            # (the version stays available to restore again later,
            # no matter what happens afterwards).
            self._restaurar_estado(copy.deepcopy(self.versiones[nombre]))

        return self._ejecutar_con_deshacer(_restaurar)

    def listar_versiones(self):
        return sorted(self.versiones.keys())

    # ---------------- undoable actions (section 13) ----------------

    def alta_evento(self, identificador, magnitud, profundidad, epicentro_x, epicentro_y,
                     fecha_hora, estacion_origen):
        return self._ejecutar_con_deshacer(
            self.catalogo.alta_evento, identificador, magnitud, profundidad,
            epicentro_x, epicentro_y, fecha_hora, estacion_origen,
            self.zonas, self.reloj_simulacion,
        )

    def corregir_evento(self, identificador, **cambios):
        def _corregir():
            resultado = self.catalogo.corregir_evento(
                identificador, self.zonas, self.reloj_simulacion, **cambios
            )
            self.metricas["correcciones_aceptadas"] += 1
            return resultado

        return self._ejecutar_con_deshacer(_corregir)

    def marcar_revisado(self, identificador):
        return self._ejecutar_con_deshacer(self.catalogo.marcar_revisado, identificador)

    def eliminar_evento(self, identificador):
        return self._ejecutar_con_deshacer(self.catalogo.eliminar_evento, identificador)

    def archivar_rama_antigua(self):
        def _archivar():
            archivados = self.catalogo.archivar_rama_antigua(self.reloj_simulacion)
            self.metricas["archivos_masivos"] += 1
            return archivados

        return self._ejecutar_con_deshacer(_archivar)

    def configurar_l_profundidad(self, l_profundidad):
        return self._ejecutar_con_deshacer(self.catalogo.configurar_l_profundidad, l_profundidad)

    def configurar_asociaciones(self, w_horas=None, r_km=None):
        return self._ejecutar_con_deshacer(
            self.catalogo.configurar_asociaciones, w_horas, r_km
        )

    def configurar_t_horas(self, t_horas):
        return self._ejecutar_con_deshacer(self.catalogo.configurar_t_horas, t_horas)

    def configurar_w_r_l(self, w_horas, r_km, l_profundidad):
        """One undoable action for W, R and L (sections 7 and 9)."""
        def _aplicar():
            self.catalogo.configurar_asociaciones(w_horas, r_km)
            self.catalogo.configurar_l_profundidad(l_profundidad)

        return self._ejecutar_con_deshacer(_aplicar)

    def avanzar_reloj(self, nuevo_reloj):
        def _avanzar():
            if nuevo_reloj < self.reloj_simulacion:
                raise ValidacionError("El reloj de simulación no puede retroceder.")
            self.reloj_simulacion = nuevo_reloj

        return self._ejecutar_con_deshacer(_avanzar)

    def cambiar_modo(self, nuevo_modo):
        def _cambiar():
            if nuevo_modo not in ("normal", "estres"):
                raise ValidacionError("El modo debe ser 'normal' o 'estres'.")
            if nuevo_modo == "normal" and not self.catalogo.esta_balanceado():
                raise ValidacionError(
                    "No se puede volver a modo normal: la auditoría no confirma el equilibrio. "
                    "Use 'Recuperar equilibrio' primero."
                )
            self.modo = nuevo_modo

        return self._ejecutar_con_deshacer(_cambiar)

    def recuperar_equilibrio(self):
        return self._ejecutar_con_deshacer(self.catalogo.recuperar_equilibrio)

    def procesar_siguiente_reporte(self):
        """
        One queue-processing step (sections 8 and 13). It is an undoable
        action EVEN IF the report ends up discarded (old revision,
        conflict, and so on): undoing it returns both the scenario and
        the report to its original position in the queue. If the queue
        is empty, `cola.desencolar()` raises IndexError before anything
        is pushed, so no empty action is left on the stack.
        """
        def _procesar():
            balancear = (self.modo == "normal")
            reporte, resultado = procesar_siguiente(
                self.cola, self.catalogo, self.zonas, self.reloj_simulacion, balancear=balancear
            )
            self.metricas["reportes_procesados"] += 1
            if resultado.tipo == TipoResultadoReporte.CONFLICTO:
                self.metricas["conflictos"] += 1
                self.metricas["reportes_descartados"] += 1
            elif resultado.tipo in (
                TipoResultadoReporte.ANTIGUO,
                TipoResultadoReporte.RECHAZADO_INVALIDO,
                TipoResultadoReporte.RECHAZADO_ELIMINADO,
            ):
                self.metricas["reportes_descartados"] += 1
            return reporte, resultado

        return self._ejecutar_con_deshacer(_procesar)

    # ---------------- JSON persistence (section 12) ----------------

    def guardar_json(self, ruta):
        """Complete structural save: real topology, history,
        queue, clock, zones, parameters, mode, and metrics."""
        from .persistencia import exportar_escenario, guardar_json as _guardar_json
        datos = exportar_escenario(self)
        _guardar_json(datos, ruta)

    def cargar_por_topologia(self, ruta_o_datos):
        """
        "Topology loading" (section 12). Replaces the ENTIRE current
        scenario with what was reconstructed and validated from the file.
        If the file is invalid (broken order, inconsistent references,
        heights or priorities that do not match, and so on), nothing is
        modified — the previous scenario is kept and the exception states
        the cause. It is itself an action that can be undone.

        `ruta_o_datos` may be a file path or an already parsed dict
        (useful for tests without touching the disk).
        """
        from .persistencia import construir_escenario_desde_topologia, leer_json
        datos = ruta_o_datos if isinstance(ruta_o_datos, dict) else leer_json(ruta_o_datos)

        def _cargar():
            nuevo = construir_escenario_desde_topologia(datos)
            self.catalogo = nuevo.catalogo
            self.cola = nuevo.cola
            self.zonas = nuevo.zonas
            self.reloj_simulacion = nuevo.reloj_simulacion
            self.modo = nuevo.modo
            self.metricas = nuevo.metricas

        return self._ejecutar_con_deshacer(_cargar)

    def cargar_por_inserciones(self, ruta_o_datos):
        """
        "Insertion loading" (section 12). Replaces the active catalog
        (NOT the history or the queue) by inserting the file's event
        sequence, in order, into a new AVL AND into a comparison BST
        with the same comparator. A repeated identifier in the sequence
        invalidates the whole file.

        Returns (resumen, bst_comparacion): `resumen` carries the height,
        leaves, and root of both trees (for the section 15 comparison
        view); `bst_comparacion` is the full ArbolBST, in case the
        interface wants to draw it.
        """
        from .persistencia import construir_arboles_por_insercion, leer_json
        datos = ruta_o_datos if isinstance(ruta_o_datos, dict) else leer_json(ruta_o_datos)
        eventos_json = datos.get("eventos", datos) if isinstance(datos, dict) else datos

        def _cargar():
            avl, bst, resumen = construir_arboles_por_insercion(eventos_json, self.zonas)
            nuevo_catalogo = Catalogo()
            nuevo_catalogo.avl = avl

            indice = {}

            def reindexar(nodo):
                if nodo is None:
                    return
                reindexar(nodo.izquierdo)
                indice[nodo.elemento.identificador] = nodo
                reindexar(nodo.derecho)

            reindexar(avl.raiz)
            nuevo_catalogo._indice_por_id = indice
            nuevo_catalogo.w_horas = self.catalogo.w_horas
            nuevo_catalogo.r_km = self.catalogo.r_km
            nuevo_catalogo.t_horas = self.catalogo.t_horas
            nuevo_catalogo._recalcular_todas_las_asociaciones()

            self.catalogo = nuevo_catalogo
            return resumen, bst

        return self._ejecutar_con_deshacer(_cargar)

    # ---------------- indicators (section 14) ----------------

    def generar_indicadores(self):
        """
        Gathers every indicator that section 14 requires to stay visible
        or accessible: counts of active/historical events, height, leaves,
        the 4 traversals, counters of accepted corrections / discarded
        reports / conflicts / mass archives / archived events, LL-RR-LR-RL
        cases and simple rotations, events by priority, pending attention,
        and events with costly access.
        """
        catalogo = self.catalogo
        avl = catalogo.avl

        por_prioridad = {1: 0, 2: 0, 3: 0}
        pendientes = 0
        for nodo in catalogo._indice_por_id.values():
            evento = nodo.elemento
            por_prioridad[evento.prioridad] += 1
            if evento.estado_atencion == "pendiente":
                pendientes += 1

        accesos_costosos, _ = catalogo.eventos_prioridad_alta_con_acceso_costoso()

        return {
            "eventos_activos": len(catalogo),
            "eventos_historicos": len(catalogo._archivados) + len(catalogo._eliminados),
            "eventos_archivados": len(catalogo._archivados),
            "eventos_eliminados": len(catalogo._eliminados),
            "altura": avl.altura_total(),
            "hojas": avl.contar_hojas(),
            "recorrido_inorden": [e.identificador for e in avl.recorrido_inorden()],
            "recorrido_preorden": [e.identificador for e in avl.recorrido_preorden()],
            "recorrido_postorden": [e.identificador for e in avl.recorrido_postorden()],
            "recorrido_por_niveles": [e.identificador for e in avl.recorrido_por_niveles()],
            "correcciones_aceptadas": catalogo.metricas.get("correcciones_aceptadas", 0),
            "reportes_descartados": catalogo.metricas.get("reportes_antiguos", 0),
            "conflictos": catalogo.metricas.get("conflictos", 0),
            "archivos_masivos": catalogo.metricas.get("archivos_masivos", 0),
            "eventos_archivados_total": catalogo.metricas.get("eventos_archivados_total", 0),
            "altas_nuevas": catalogo.metricas.get("altas_nuevas", 0),
            "confirmaciones": catalogo.metricas.get("confirmaciones", 0),
            "eliminaciones": catalogo.metricas.get("eliminaciones", 0),
            "reportes_rechazados_invalidos": catalogo.metricas.get("reportes_rechazados_invalidos", 0),
            "reportes_procesados_por_cola": self.metricas.get("reportes_procesados", 0),
            "eventos_por_prioridad": por_prioridad,
            "pendientes_de_atencion": pendientes,
            "eventos_con_acceso_costoso": len(accesos_costosos),
            "rotaciones": dict(avl.contador_casos),
            "giros_izquierda": avl.contador_giros_izquierda,
            "giros_derecha": avl.contador_giros_derecha,
        }
