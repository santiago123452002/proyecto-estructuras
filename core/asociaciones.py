import math


def distancia_euclidiana(evento_a, evento_b):
    return math.hypot(evento_a.epicentro_x - evento_b.epicentro_x,
                       evento_a.epicentro_y - evento_b.epicentro_y)


def es_candidato(evento_a, evento_b, w_horas, r_km):
    """
    Sección 7: A es candidato a referencia de B cuando:
      - A tiene mayor magnitud que B,
      - A ocurrió ESTRICTAMENTE antes que B,
      - la diferencia temporal es como máximo W horas,
      - la distancia euclidiana entre epicentros es como máximo R km.
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
    Candidatos a referencia de `evento_b` entre `eventos_disponibles`
    (deben ser eventos activos y archivados; nunca eliminados —
    responsabilidad de quien llama filtrar eso antes).
    """
    return [a for a in eventos_disponibles if es_candidato(a, evento_b, w_horas, r_km)]


def elegir_referencia(evento_b, lista_candidatos):
    """
    Criterio determinista de desempate cuando `evento_b` tiene varios
    candidatos (sección 7 exige uno que "dependa de los datos, no del
    orden de llegada ni de la topología del AVL"):

      1) mayor magnitud del candidato (el sismo más fuerte es la
         explicación más plausible de una réplica),
      2) si empatan, el ocurrido más cerca en el tiempo de B,
      3) si persiste el empate, el epicentro más cercano a B,
      4) si aún persiste, el de menor identificador (desempate final
         estable y reproducible).

    No depende del orden de llegada de los reportes ni de la forma que
    tenga el AVL en ese momento: solo de los datos propios de los
    eventos, así que el resultado es el mismo sin importar cómo se haya
    insertado o balanceado el árbol.
    """
    if not lista_candidatos:
        return None

    def clave_orden(a):
        diferencia_horas = (evento_b.fecha_hora - a.fecha_hora).total_seconds() / 3600.0
        distancia = distancia_euclidiana(a, evento_b)
        return (-a.magnitud, diferencia_horas, distancia, a.identificador)

    return min(lista_candidatos, key=clave_orden)