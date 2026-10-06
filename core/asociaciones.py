import math


def distancia_euclidiana(evento_a, evento_b):
    return math.hypot(evento_a.epicentro_x - evento_b.epicentro_x,
                       evento_a.epicentro_y - evento_b.epicentro_y)


def es_candidato(evento_a, evento_b, w_horas, r_km):
    """
    Section 7: A is a candidate reference for B when:
    - A has a greater magnitude than B,
    - A occurred STRICTLY before B,
    - the time difference is at most W hours,
    - the Euclidean distance between epicenters is at most R km.
    """
    if evento_a.identificador == evento_b.identificador:
        return False
    if not (evento_a.magnitud > evento_b.magnitud):
        return False
    if not (evento_a.fecha_hora < evento_b.fecha_hora):
        return False

    diferencia_horas = (evento_b.fecha_hora - evento_a.fecha_hora).total_seconds() / 3600.0
    if diferencia_horas > w_horas:
        return False

    if distancia_euclidiana(evento_a, evento_b) > r_km:
        return False

    return True


def candidatos(evento_b, eventos_disponibles, w_horas, r_km):
    """
    Reference candidates for `event_b` among `available_events`
    (they must be active and archived events; never deleted —
    it is the caller's responsibility to filter them beforehand).
    """
    return [a for a in eventos_disponibles if es_candidato(a, evento_b, w_horas, r_km)]


def elegir_referencia(evento_b, lista_candidatos):
    """
    Deterministic tie-breaking criterion when `event_b` has multiple
    candidates (section 7 requires one that "depends on the data, not on
    the arrival order or AVL topology"):

    1) greater candidate magnitude (the stronger earthquake is the
        most plausible explanation for an aftershock),
    2) if tied, the one that occurred closest in time to B,
    3) if still tied, the epicenter closest to B,
    4) if still tied, the one with the lowest identifier (final
    stable and reproducible tie-breaker).

    It does not depend on the arrival order of the reports or the shape
    of the AVL at that moment: only on the events' own data, so the
    result is the same regardless of how the tree was inserted or balanced.
    """
    if not lista_candidatos:
        return None

    def clave_orden(a):
        diferencia_horas = (evento_b.fecha_hora - a.fecha_hora).total_seconds() / 3600.0
        distancia = distancia_euclidiana(a, evento_b)
        return (-a.magnitud, diferencia_horas, distancia, a.identificador)

    return min(lista_candidatos, key=clave_orden)