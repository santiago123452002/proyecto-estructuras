"""
Persistencia en JSON (sección 12): guardado estructural completo, carga
por topología (reconstruye el árbol tal cual, con toda su validación) y
carga por inserciones (compara AVL vs BST con la misma secuencia).

Este módulo NO importa `Escenario` a nivel de módulo -- lo hace de forma
diferida, dentro de la función que lo necesita -- porque `escenario.py`
importa de aquí (`from .persistencia import ...`) para sus métodos de
carga/guardado; importarlo arriba crearía un ciclo de importación.
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


# ---------------- guardado estructural (exportación completa) ----------------

def exportar_escenario(escenario):
    """
    "Guardado estructural" (sección 12): topología real del árbol
    activo (datos vigentes, alturas, factores de balance, estado de
    atención), histórico completo, cola en su orden original, reloj,
    zonas, parámetros W/R/T, modo de ejecución y métricas acumuladas.

    Las asociaciones NO se guardan explícitas: se reconstruyen siempre
    con la misma política determinista al cargar. El enunciado permite
    cualquiera de las dos opciones ("el equipo puede guardar las
    asociaciones o reconstruirlas... en ambos casos debe recuperar el
    mismo resultado lógico") y reconstruirlas evita tener que validar
    aparte que lo guardado siga siendo consistente con los datos.
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


# ---------------- carga por topología ----------------

def _validar_topologia_reconstruida(raiz, modo):
    """
    Recorre la topología YA reconstruida (con dict_a_nodo, que ya validó
    altura/factor por nodo y la prioridad de cada evento) y valida lo
    que solo se puede comprobar viendo el árbol completo:

    - Orden global BST por K: el recorrido inorden debe salir
      estrictamente ascendente. Esto de paso descarta ciclos -- un
      ciclo en los punteros izquierdo/derecho produciría una recursión
      infinita en vez de una lista, así que si `recorrer` termina, no
      hay ciclos (y una recursión infinita real es imposible aquí de
      todos modos: el propio texto JSON es un árbol de objetos anidados
      sin referencias compartidas, así que no hay forma de codificar un
      ciclo en el archivo de entrada).
    - Unicidad de identificadores dentro del árbol activo.
    - Que el balance real sea compatible con el modo declarado: en modo
      normal TODO nodo debe tener factor de balance en {-1, 0, 1}; en
      modo estrés se acepta cualquier balance (puede estar degradado).

    Devuelve el conjunto de identificadores del árbol activo.
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
    "Carga por topología" (sección 12). Reconstruye TODO el escenario a
    partir de un dict ya parseado. Solo usa variables LOCALES hasta que
    toda la validación pasa -- así, si algo falla a mitad de camino,
    quien llama nunca recibe un escenario a medio construir, lo que le
    permite a `Escenario.cargar_por_topologia` conservar el escenario
    anterior ante un archivo inválido, tal como exige el enunciado.
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

    # --- ya todo validó: recién ahora se arman los objetos reales ---

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

    from .escenario import Escenario  # import diferido: evita ciclo con escenario.py
    nuevo = Escenario(zonas=zonas, reloj_simulacion=reloj_simulacion)
    nuevo.catalogo = catalogo
    nuevo.cola = cola
    nuevo.modo = modo
    nuevo.metricas = {"reportes_procesados": metricas_json.get("reportes_procesados", 0)}
    return nuevo


# ---------------- carga por inserciones (comparación AVL vs BST) ----------------

def construir_arboles_por_insercion(eventos_json, zonas):
    """
    "Carga por inserciones" (sección 12). Aplica el MISMO comparador y
    la MISMA secuencia de inserción a un AVL (con balanceo) y a un BST
    (sin balanceo), para poder comparar altura, hojas y comparaciones al
    buscar. Es una carga de EVENTOS, no de reportes repetidos: un
    identificador duplicado en la secuencia invalida el archivo
    completo (no se construye nada).

    Devuelve (avl, bst, resumen); `resumen` trae raíz, altura y hojas de
    cada árbol, listos para mostrar en la vista comparativa.
    """
    identificadores = [datos_evento["identificador"] for datos_evento in eventos_json]
    if len(identificadores) != len(set(identificadores)):
        raise ValidacionError(
            "La secuencia de carga por inserciones tiene un identificador duplicado."
        )

    avl = ArbolAVL()
    bst = ArbolBST()
    for datos_evento in eventos_json:
        # dos instancias de Evento independientes: cada árbol tiene sus
        # propios nodos, sin compartir estado entre sí
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


# ---------------- lectura/escritura de archivo ----------------

def guardar_json(datos, ruta):
    """Escribe `datos` (un dict ya JSON-compatible) en `ruta`, con
    sangría legible para poder revisar el archivo a mano."""
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, indent=2, ensure_ascii=False)


def leer_json(ruta):
    """Lee y parsea un archivo JSON. Si el archivo no es JSON válido,
    deja que json.JSONDecodeError se propague tal cual -- la interfaz
    gráfica lo distingue de un ValidacionError de reglas de negocio."""
    with open(ruta, "r", encoding="utf-8") as archivo:
        return json.load(archivo)
    