import copy

from .catalogo import Catalogo
from .cola_reportes import ColaReportes
from .evento import ValidacionError
from .pila import Pila
from .procesador_reportes import procesar_siguiente
from .resultado_reporte import TipoResultadoReporte

# Atributos que forman el "estado operativo" del escenario: lo que la
# sección 13 exige recuperar al deshacer o restaurar una versión
# ("datos, histórico, referencias, cola, reloj, parámetros, modo y
# métricas"). `_pila_deshacer` y `versiones` quedan FUERA a propósito:
# son metadatos administrativos del propio mecanismo de deshacer, no
# parte del escenario que se está simulando (el enunciado lo confirma:
# "[las versiones] no necesitan contener la pila de retroceso ni otras
# versiones").
_CAMPOS_ESTADO = ("catalogo", "cola", "zonas", "reloj_simulacion", "modo", "metricas")


class Escenario:
    """
    Orquesta el Catalogo (AVL + histórico + asociaciones), la cola de
    reportes, el reloj de simulación y el modo de ejecución como una
    sola unidad deshacible, tal como exige la sección 13: "Cada alta,
    corrección, eliminación, archivo masivo, cambio de parámetros,
    avance del reloj, cambio de atención, carga y recuperación global
    constituye una acción independiente" — y "cada paso de
    procesamiento de la cola también constituye una acción".

    Estrategia de deshacer elegida: ANTES de cada acción se guarda una
    COPIA COMPLETA (deep copy) del estado operativo en la pila; deshacer
    simplemente restaura la copia más reciente. Se descartó guardar solo
    el "delta" de cada acción (p. ej. qué rotaciones ocurrieron) porque
    para deshacerlo con exactitud habría que invertir cada rotación una
    por una, y el propio enunciado ya aclara que "las inserciones y
    rotaciones internas de una corrección o archivo masivo no se
    deshacen por separado" — es decir, la granularidad exigida es la de
    la ACCIÓN completa, no la de cada paso interno. Copiar todo el
    estado es más simple de verificar como correcto, a cambio de más
    memoria por paso: cada snapshot cuesta O(n) en tiempo y memoria,
    proporcional al número total de eventos (activos + histórico) más
    el tamaño de la cola pendiente.

    Si una acción falla (lanza ValidacionError porque los datos son
    inválidos), la copia se descarta sin apilarse: como ninguna de las
    operaciones del Catalogo modifica nada antes de validar, no hace
    falta deshacer una acción que nunca llegó a aplicarse.
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
        self.versiones = {}  # nombre -> snapshot del estado operativo

    # ---------------- mecanismo de deshacer ----------------

    def _capturar_estado(self):
        """Copia completa (deep copy) de los campos operativos."""
        return {campo: copy.deepcopy(getattr(self, campo)) for campo in _CAMPOS_ESTADO}

    def _restaurar_estado(self, estado):
        for campo, valor in estado.items():
            setattr(self, campo, valor)

    def _ejecutar_con_deshacer(self, funcion, *args, **kwargs):
        """
        Captura el estado, ejecuta `funcion`, y solo si no lanzó
        excepción apila la copia previa. Devuelve lo que devuelva
        `funcion`.
        """
        snapshot = self._capturar_estado()
        resultado = funcion(*args, **kwargs)
        self._pila_deshacer.apilar(snapshot)
        return resultado

    def deshacer(self):
        """
        Restaura el estado guardado en el último punto de deshacer.
        Devuelve True si se deshizo algo, False si no había ninguna
        acción pendiente por deshacer.
        """
        if self._pila_deshacer.esta_vacia():
            return False
        estado_anterior = self._pila_deshacer.desapilar()
        self._restaurar_estado(estado_anterior)
        return True

    def hay_algo_que_deshacer(self):
        return not self._pila_deshacer.esta_vacia()

    # ---------------- versiones nombradas persistentes ----------------

    def guardar_version(self, nombre):
        """Guarda (o sobrescribe) una copia con nombre del estado
        operativo actual. No incluye la pila de deshacer ni otras
        versiones, tal como exige el enunciado."""
        self.versiones[nombre] = self._capturar_estado()

    def restaurar_version(self, nombre):
        """
        Restaura una versión guardada. Es, en sí misma, una acción que
        puede deshacerse: se apila el estado actual antes de aplicar la
        versión, así que un `deshacer()` posterior regresa exactamente a
        como estaba el escenario justo antes de restaurar.
        """
        if nombre not in self.versiones:
            raise ValidacionError(f"No existe una versión guardada con el nombre '{nombre}'.")

        def _restaurar():
            # se aplica una COPIA de lo guardado, para que cambios
            # posteriores al escenario nunca contaminen la versión
            # almacenada (la versión sigue disponible para restaurarla
            # de nuevo más adelante, sin importar qué pase después).
            self._restaurar_estado(copy.deepcopy(self.versiones[nombre]))

        return self._ejecutar_con_deshacer(_restaurar)

    def listar_versiones(self):
        return sorted(self.versiones.keys())

    # ---------------- acciones deshacibles (sección 13) ----------------

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
            self.modo = nuevo_modo

        return self._ejecutar_con_deshacer(_cambiar)

    def recuperar_equilibrio(self):
        return self._ejecutar_con_deshacer(self.catalogo.recuperar_equilibrio)

    def procesar_siguiente_reporte(self):
        """
        Un paso de procesamiento de la cola (sección 8 y 13). Es una
        acción deshacible AUNQUE el reporte termine descartado (revisión
        antigua, conflicto, etc.): deshacerla regresa tanto el escenario
        como el reporte a su posición original en la cola. Si la cola
        está vacía, `cola.desencolar()` lanza IndexError antes de que se
        apile nada, así que no queda una acción vacía en la pila.
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

    # ---------------- persistencia en JSON (sección 12) ----------------

    def guardar_json(self, ruta):
        """Guardado estructural completo: topología real, histórico,
        cola, reloj, zonas, parámetros, modo y métricas."""
        from .persistencia import exportar_escenario, guardar_json as _guardar_json
        datos = exportar_escenario(self)
        _guardar_json(datos, ruta)

    def cargar_por_topologia(self, ruta_o_datos):
        """
        "Carga por topología" (sección 12). Reemplaza TODO el escenario
        actual con lo reconstruido y validado a partir del archivo. Si
        el archivo es inválido (orden roto, referencias inconsistentes,
        alturas o prioridades que no cuadran, etc.), no se modifica nada
        — se conserva el escenario anterior y la excepción indica la
        causa. Es, en sí misma, una acción que puede deshacerse.

        `ruta_o_datos` puede ser una ruta de archivo o un dict ya
        parseado (útil para pruebas sin tocar el disco).
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
        "Carga por inserciones" (sección 12). Reemplaza el catálogo
        activo (NO el histórico ni la cola) insertando la secuencia de
        eventos del archivo, en orden, en un AVL nuevo Y en un BST de
        comparación con el mismo comparador. Un identificador repetido
        en la secuencia invalida el archivo completo.

        Devuelve (resumen, bst_comparacion): `resumen` trae altura,
        hojas y raíz de ambos árboles (para la vista comparativa de la
        sección 15); `bst_comparacion` es el ArbolBST completo, por si
        la interfaz quiere dibujarlo.
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

    # ---------------- indicadores (sección 14) ----------------

    def generar_indicadores(self):
        """
        Reúne todos los indicadores que la sección 14 exige mantener
        visibles o accesibles: cantidades de eventos activos/históricos,
        altura, hojas, los 4 recorridos, contadores de correcciones
        aceptadas / reportes descartados / conflictos / archivos
        masivos / eventos archivados, casos LL-RR-LR-RL y giros simples,
        eventos por prioridad, pendientes de atención, y eventos con
        acceso costoso.
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
