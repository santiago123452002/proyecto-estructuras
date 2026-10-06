"""
JSON persistence (section 12): complete structural saving, topology-based
loading (rebuilds the tree exactly as it was, with full validation), and
insertion-based loading (compares AVL vs BST using the same sequence).

This module does NOT import `Escenario` at module level -- it does so
lazily, inside the function that needs it -- because `escenario.py`
imports from here (`from .persistencia import ...`) for its loading/saving
methods; importing it above would create an import cycle.
"""

import json

from .arbol_avl import ArbolAVL
from .arbol_bst import ArbolBST
from .catalogo import Catalogo
from .cola_reportes import ColaReportes
from .evento import ValidacionError
from .serializacion import (
    zona_a_dict, dict_a_zona,
    evento_a_dict, dict_a_evento,
    reporte_a_dict, dict_a_reporte,
    nodo_a_dict, dict_a_nodo,
    fecha_a_texto, texto_a_fecha,
)


# ---------------- structural saving (complete export) ----------------

def exportar_escenario(escenario):
    """
    "Structural saving" (section 12): actual topology of the active tree
    (current data, heights, balance factors, attention status), complete
    history, queue in its original order, clock, zones, W/R/T parameters,
    execution mode, and accumulated metrics.

    Associations are NOT saved explicitly: they are always rebuilt
    using the same deterministic policy when loading. The statement
    allows either option ("the team may save the associations or rebuild
    them... in both cases the same logical result must be recovered"), and
    rebuilding avoids having to separately validate that the saved data
    remains consistent with the current data.
    """
    catalogo = escenario.catalogo
    avl = catalogo.avl
    return {
        "zonas": [zona_a_dict(z) for z in escenario.zonas],
        "reloj_simulacion": fecha_a_texto(escenario.reloj_simulacion),
        "modo": escenario.modo,
        "parametros": {
            "w_horas": catalogo.w_horas,
            "r_km": catalogo.r_km,
            "t_horas": catalogo.t_horas,
            "l_profundidad": catalogo.l_profundidad,
        },
        "metricas": {
            "reportes_procesados": escenario.metricas.get("reportes_procesados", 0),
            "rotaciones": dict(avl.contador_casos),
            "giros_izquierda": avl.contador_giros_izquierda,
            "giros_derecha": avl.contador_giros_derecha,
            "rotaciones_recuperacion": avl.contador_rotaciones_recuperacion,
        },
        "arbol_activo": nodo_a_dict(avl.raiz),
        "historico": {
            "archivados": [evento_a_dict(e) for e in catalogo._archivados.values()],
            "eliminados": [evento_a_dict(e) for e in catalogo._eliminados.values()],
        },
        "cola": [reporte_a_dict(r) for r in escenario.cola.ver_orden()],
    }


# ---------------- topology-based loading ----------------
def _validar_topologia_reconstruida(raiz, modo):
    """
    Traverses the ALREADY reconstructed topology (with dict_a_nodo, which
    has already validated height/balance factor per node and the priority
    of each event) and validates what can only be checked by looking at
    the complete tree:

    - Global BST ordering by K: the inorder traversal must be
    strictly ascending. This also rules out cycles -- a cycle in the
    left/right pointers would cause infinite recursion instead of a list,
    so if `recorrer` finishes, there are no cycles (and a real infinite
    recursion is impossible here anyway: the JSON text itself is a tree
    of nested objects without shared references, so there is no way to
    encode a cycle in the input file).
    - Identifier uniqueness within the active tree.
    - That the actual balance is compatible with the declared mode: in
    normal mode EVERY node must have a balance factor in {-1, 0, 1};
    in stress mode any balance is accepted (the tree may be degraded).

    Returns the set of identifiers from the active tree.
    """
    identificadores = set()
    claves = []
    balanceado = True

    def recorrer(nodo):
        nonlocal balanceado
        if nodo is None:
            return
        recorrer(nodo.izquierdo)
        if nodo.elemento.identificador in identificadores:
            raise ValidacionError(
                f"Identificador duplicado en la topología: {nodo.elemento.identificador}."
            )
        identificadores.add(nodo.elemento.identificador)
        claves.append(nodo.clave)
        altura_izq = nodo.izquierdo.altura if nodo.izquierdo is not None else -1
        altura_der = nodo.derecho.altura if nodo.derecho is not None else -1
        if (altura_izq - altura_der) not in (-1, 0, 1):
            balanceado = False
        recorrer(nodo.derecho)

    recorrer(raiz)

    if claves != sorted(claves):
        raise ValidacionError("La topología no respeta el orden global BST por la clave K.")
    if modo not in ("normal", "estres"):
        raise ValidacionError(f"Modo de ejecución inválido en el archivo: '{modo}'.")
    if modo == "normal" and not balanceado:
        raise ValidacionError(
            "La topología no está balanceada; solo puede cargarse con el modo estrés activado."
        )

    return identificadores


def construir_escenario_desde_topologia(datos):
    """
    "Topology-based loading" (section 12). Rebuilds the ENTIRE scenario
    from an already parsed dict. It only uses LOCAL variables until
    all validation passes -- therefore, if something fails halfway through,
    the caller never receives a partially built scenario, allowing
    `Escenario.cargar_por_topologia` to preserve the previous scenario
    when given an invalid file, as required by the statement.
    """
    zonas = [dict_a_zona(z) for z in datos.get("zonas", [])]
    reloj_simulacion = texto_a_fecha(datos["reloj_simulacion"])
    modo = datos.get("modo", "normal")

    raiz = dict_a_nodo(datos.get("arbol_activo"), zonas)
    identificadores_activos = _validar_topologia_reconstruida(raiz, modo)

    historico = datos.get("historico", {})
    archivados = {}
    for datos_evento in historico.get("archivados", []):
        evento = dict_a_evento(datos_evento, zonas)
        if evento.identificador in identificadores_activos or evento.identificador in archivados:
            raise ValidacionError(f"Identificador duplicado en el histórico: {evento.identificador}.")
        archivados[evento.identificador] = evento

    eliminados = {}
    for datos_evento in historico.get("eliminados", []):
        evento = dict_a_evento(datos_evento, zonas)
        if (evento.identificador in identificadores_activos
                or evento.identificador in archivados or evento.identificador in eliminados):
            raise ValidacionError(f"Identificador duplicado en el histórico: {evento.identificador}.")
        eliminados[evento.identificador] = evento

    parametros = datos.get("parametros", {})
    w_horas = parametros.get("w_horas", 48.0)
    r_km = parametros.get("r_km", 40.0)
    t_horas = parametros.get("t_horas", 72.0)
    l_profundidad = parametros.get("l_profundidad", 3)
    if w_horas <= 0 or r_km <= 0 or t_horas <= 0:
        raise ValidacionError("Los parámetros W, R y T deben ser positivos.")
    if not isinstance(l_profundidad, int) or l_profundidad < 0:
        raise ValidacionError("El parámetro L debe ser un entero no negativo.")

    # --- everything already validated: only now are the real objects built ---

    avl = ArbolAVL()
    avl.raiz = raiz
    indice_por_id = {}
    contador = [0]

    def indexar(nodo):
        if nodo is None:
            return
        indexar(nodo.izquierdo)
        indice_por_id[nodo.elemento.identificador] = nodo
        contador[0] += 1
        indexar(nodo.derecho)

    indexar(raiz)
    avl._cantidad = contador[0]

    metricas_json = datos.get("metricas", {})
    rotaciones = metricas_json.get("rotaciones", {})
    for caso in ("LL", "RR", "LR", "RL"):
        avl.contador_casos[caso] = rotaciones.get(caso, 0)
    avl.contador_giros_izquierda = metricas_json.get("giros_izquierda", 0)
    avl.contador_giros_derecha = metricas_json.get("giros_derecha", 0)
    avl.contador_rotaciones_recuperacion = metricas_json.get("rotaciones_recuperacion", 0)

    catalogo = Catalogo()
    catalogo.avl = avl
    catalogo._indice_por_id = indice_por_id
    catalogo._archivados = archivados
    catalogo._eliminados = eliminados
    catalogo.w_horas = w_horas
    catalogo.r_km = r_km
    catalogo.t_horas = t_horas
    catalogo.l_profundidad = l_profundidad
    catalogo._recalcular_todas_las_asociaciones()

    cola = ColaReportes()
    for datos_reporte in datos.get("cola", []):
        cola.encolar(dict_a_reporte(datos_reporte))

    from .escenario import Escenario  # deferred import: avoids a cycle with escenario.py
    nuevo = Escenario(zonas=zonas, reloj_simulacion=reloj_simulacion)
    nuevo.catalogo = catalogo
    nuevo.cola = cola
    nuevo.modo = modo
    nuevo.metricas = {"reportes_procesados": metricas_json.get("reportes_procesados", 0)}
    return nuevo


# ---------------- insertion loading (AVL vs BST comparison) ----------------

def construir_arboles_por_insercion(eventos_json, zonas):
    """
    "Insertion-based loading" (section 12). Applies the SAME comparator and
    the SAME insertion sequence to an AVL (with balancing) and a BST
    (without balancing), in order to compare height, leaves, and
    comparisons when searching. This is an EVENT loading operation, not
    one involving repeated reports: a duplicate identifier in the sequence
    invalidates the entire file (nothing is built).

    Returns (avl, bst, resumen); `resumen` contains the root, height, and
    number of leaves of each tree, ready to be displayed in the comparison view.
    """
    identificadores = [datos_evento["identificador"] for datos_evento in eventos_json]
    if len(identificadores) != len(set(identificadores)):
        raise ValidacionError(
            "La secuencia de carga por inserciones tiene un identificador duplicado."
        )

    avl = ArbolAVL()
    bst = ArbolBST()
    for datos_evento in eventos_json:
        # two independent Event instances: each tree has its
        # own nodes, without sharing state with the other
        avl.insertar(dict_a_evento(datos_evento, zonas))
        bst.insertar(dict_a_evento(datos_evento, zonas))

    resumen = {
        "avl": {
            "raiz": avl.raiz.clave if avl.raiz is not None else None,
            "altura": avl.altura_total(),
            "hojas": avl.contar_hojas(),
            "cantidad": len(avl),
        },
        "bst": {
            "raiz": bst.raiz.clave if bst.raiz is not None else None,
            "altura": bst.altura(),
            "hojas": bst.contar_hojas(),
            "cantidad": len(bst),
        },
    }
    return avl, bst, resumen


# ---------------- file reading/writing ----------------

def guardar_json(datos, ruta):
    """Writes `datos` (a JSON-compatible dict) to `ruta`, with
    readable indentation so the file can be reviewed manually."""
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, indent=2, ensure_ascii=False)


def leer_json(ruta):
    """Reads and parses a JSON file. If the file is not valid JSON,
    lets json.JSONDecodeError propagate as-is -- the graphical interface
    distinguishes it from a ValidacionError caused by business rules."""
    with open(ruta, "r", encoding="utf-8") as archivo:
        return json.load(archivo)
    