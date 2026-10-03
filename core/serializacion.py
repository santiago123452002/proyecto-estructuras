"""
Conversión entre los objetos del dominio (Evento, Zona, Reporte, Nodo del
AVL) y diccionarios que `json.dump`/`json.load` pueden escribir y leer
directamente (sección 12). El formato de fecha es ISO 8601 con sufijo
'Z' (UTC), tal como especifica la sección 3 del enunciado — por ejemplo
"2026-09-07T10:00:00Z".

Toda función `dict_a_*` revalida los datos al reconstruir el objeto
(reutilizando las validaciones que ya tiene Evento, y recalculando la
prioridad y la pertenencia a zona poblada) — así un JSON editado a mano
con datos corruptos se rechaza igual que si viniera de la interfaz.
"""

from datetime import datetime, timezone

from .nodo import Nodo
from .evento import Evento, ValidacionError
from .zona import Zona, pertenece_a_zona_poblada
from .reporte import Reporte


# ---------------- fechas (ISO 8601, sección 3) ----------------

def fecha_a_texto(fecha_hora):
    """datetime -> texto ISO 8601 con sufijo 'Z', con precisión de segundos."""
    if fecha_hora.tzinfo is not None:
        fecha_hora = fecha_hora.astimezone(timezone.utc).replace(tzinfo=None)
    return fecha_hora.strftime("%Y-%m-%dT%H:%M:%SZ")


def texto_a_fecha(texto):
    """texto ISO 8601 (con o sin sufijo 'Z') -> datetime naive en UTC."""
    limpio = texto.strip()
    if limpio.endswith("Z"):
        limpio = limpio[:-1] + "+00:00"
    try:
        fecha = datetime.fromisoformat(limpio)
    except ValueError as error:
        raise ValidacionError(f"Fecha y hora con formato inválido: '{texto}'.") from error
    if fecha.tzinfo is not None:
        fecha = fecha.astimezone(timezone.utc).replace(tzinfo=None)
    return fecha


# ---------------- Zona ----------------

def zona_a_dict(zona):
    return {
        "nombre": zona.nombre,
        "x_min": zona.x_min, "x_max": zona.x_max,
        "y_min": zona.y_min, "y_max": zona.y_max,
        "poblada": zona.poblada,
    }


def dict_a_zona(datos):
    try:
        return Zona(datos["nombre"], datos["x_min"], datos["x_max"],
                     datos["y_min"], datos["y_max"], datos["poblada"])
    except (KeyError, ValueError) as error:
        raise ValidacionError(f"Zona con datos inválidos: {error}") from error


# ---------------- Evento ----------------

def evento_a_dict(evento):
    return {
        "identificador": evento.identificador,
        "magnitud": evento.magnitud,
        "profundidad": evento.profundidad,
        "epicentro_x": evento.epicentro_x,
        "epicentro_y": evento.epicentro_y,
        "fecha_hora": fecha_a_texto(evento.fecha_hora),
        "revision": evento.revision,
        "estaciones": sorted(evento.estaciones),
        "estado_atencion": evento.estado_atencion,
        "prioridad": evento.prioridad,  # se valida al recargar, no se asigna directo
    }


def dict_a_evento(datos, zonas):
    """
    Reconstruye un Evento a partir de un dict. Recalcula la prioridad
    con las `zonas` dadas y la compara contra `datos["prioridad"]`: si
    no coinciden, el archivo está corrupto o fue editado a mano de forma
    inconsistente, y se rechaza (sección 12: "Una prioridad almacenada
    debe coincidir con la calculada").
    """
    try:
        estaciones = datos.get("estaciones") or ["DESCONOCIDA"]
        evento = Evento(
            identificador=datos["identificador"],
            magnitud=datos["magnitud"],
            profundidad=datos["profundidad"],
            epicentro_x=datos["epicentro_x"],
            epicentro_y=datos["epicentro_y"],
            fecha_hora=texto_a_fecha(datos["fecha_hora"]),
            estacion_origen=estaciones[0],
            revision=datos.get("revision", 1),
        )
    except KeyError as error:
        raise ValidacionError(f"Al evento le falta el campo obligatorio {error}.") from error

    evento.estaciones = set(estaciones)
    evento.estado_atencion = datos.get("estado_atencion", "pendiente")
    if evento.estado_atencion not in ("pendiente", "revisado"):
        raise ValidacionError(
            f"Estado de atención inválido para el evento {evento.identificador}: "
            f"'{evento.estado_atencion}'."
        )

    en_zona_poblada = pertenece_a_zona_poblada(evento.epicentro_x, evento.epicentro_y, zonas)
    prioridad_calculada = evento.actualizar_prioridad(en_zona_poblada)
    prioridad_almacenada = datos.get("prioridad")
    if prioridad_almacenada is not None and prioridad_almacenada != prioridad_calculada:
        raise ValidacionError(
            f"La prioridad almacenada del evento {evento.identificador} "
            f"({prioridad_almacenada}) no coincide con la calculada ({prioridad_calculada})."
        )
    return evento


# ---------------- Reporte ----------------

def reporte_a_dict(reporte):
    return {
        "identificador": reporte.identificador,
        "magnitud": reporte.magnitud,
        "profundidad": reporte.profundidad,
        "epicentro_x": reporte.epicentro_x,
        "epicentro_y": reporte.epicentro_y,
        "fecha_hora": fecha_a_texto(reporte.fecha_hora),
        "revision": reporte.revision,
        "estacion": reporte.estacion,
    }


def dict_a_reporte(datos):
    try:
        return Reporte(
            identificador=datos["identificador"],
            magnitud=datos["magnitud"],
            profundidad=datos["profundidad"],
            epicentro_x=datos["epicentro_x"],
            epicentro_y=datos["epicentro_y"],
            fecha_hora=texto_a_fecha(datos["fecha_hora"]),
            revision=datos["revision"],
            estacion=datos["estacion"],
        )
    except KeyError as error:
        raise ValidacionError(f"Al reporte le falta el campo obligatorio {error}.") from error


# ---------------- topología del AVL (carga por topología, sección 12) ----------------

def nodo_a_dict(nodo):
    """
    Serializa la topología REAL (no se reconstruye a partir de una
    lista ordenada, sino que se recorre el árbol tal como está). Incluye
    `altura` y `factor_balance` explícitamente (aunque son derivables)
    porque la sección 12 exige poder validar, al cargar, que "una
    topología... alturas y factores almacenados" coincidan con los
    recalculados a partir de la estructura real.
    """
    if nodo is None:
        return None
    altura_izq = nodo.izquierdo.altura if nodo.izquierdo is not None else -1
    altura_der = nodo.derecho.altura if nodo.derecho is not None else -1
    return {
        "evento": evento_a_dict(nodo.elemento),
        "altura": nodo.altura,
        "factor_balance": altura_izq - altura_der,
        "izquierdo": nodo_a_dict(nodo.izquierdo),
        "derecho": nodo_a_dict(nodo.derecho),
    }


def dict_a_nodo(datos, zonas):
    """
    Reconstruye el nodo (y recursivamente sus hijos) SIN reinsertar
    nada: se arman los enlaces izquierdo/derecho/padre directamente,
    preservando exactamente la topología del archivo. Valida altura y
    factor de balance almacenados contra los recalculados a partir de
    los hijos ya reconstruidos.
    """
    if datos is None:
        return None
    evento = dict_a_evento(datos["evento"], zonas)
    nodo = Nodo(evento)
    nodo.izquierdo = dict_a_nodo(datos.get("izquierdo"), zonas)
    nodo.derecho = dict_a_nodo(datos.get("derecho"), zonas)
    if nodo.izquierdo is not None:
        nodo.izquierdo.padre = nodo
    if nodo.derecho is not None:
        nodo.derecho.padre = nodo

    altura_izq = nodo.izquierdo.altura if nodo.izquierdo is not None else -1
    altura_der = nodo.derecho.altura if nodo.derecho is not None else -1
    altura_calculada = 1 + max(altura_izq, altura_der)
    factor_calculado = altura_izq - altura_der

    altura_almacenada = datos.get("altura")
    if altura_almacenada is not None and altura_almacenada != altura_calculada:
        raise ValidacionError(
            f"La altura almacenada del nodo {evento.identificador} ({altura_almacenada}) "
            f"no coincide con la recalculada a partir de sus hijos ({altura_calculada})."
        )
    factor_almacenado = datos.get("factor_balance")
    if factor_almacenado is not None and factor_almacenado != factor_calculado:
        raise ValidacionError(
            f"El factor de balance almacenado del nodo {evento.identificador} "
            f"({factor_almacenado}) no coincide con el recalculado ({factor_calculado})."
        )

    nodo.altura = altura_calculada
    return nodo