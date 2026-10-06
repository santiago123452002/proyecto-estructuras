"""
Pruebas de la Fase 5: eliminación individual, archivo de subárboles
(sección 10) y asociaciones candidato/réplica entre eventos (sección 7).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import pytest

from core import Zona, Catalogo, ValidacionError, Evento
from core.asociaciones import es_candidato, elegir_referencia, distancia_euclidiana


RELOJ = datetime(2026, 9, 10, 12, 0, 0)


def _zonas_ejemplo():
    return [
        Zona("Ciudad Central", 400.0, 600.0, 400.0, 600.0, poblada=True),
        Zona("Zona Rural", 0.0, 400.0, 0.0, 400.0, poblada=False),
    ]


def _alta(catalogo, identificador, magnitud, fecha_hora, x=500.0, y=500.0,
          profundidad=10.0, estacion="EST-01"):
    return catalogo.alta_evento(identificador, magnitud, profundidad, x, y,
                                 fecha_hora, estacion, _zonas_ejemplo(), RELOJ)


# ---------------- eliminación individual ----------------

def test_eliminacion_individual_retira_solo_ese_evento():
    """
    Ejemplo del enunciado (sección 10): si un evento tiene descendientes
    en el AVL, eliminarlo individualmente NO los afecta a ellos.
    """
    catalogo = Catalogo()
    for i in range(1, 8):
        _alta(catalogo, 100 + i, 5.0, datetime(2026, 9, 10, 9, 0, 0))

    assert len(catalogo) == 7
    catalogo.eliminar_evento(104)

    assert len(catalogo) == 6
    assert catalogo.esta_activo(104) is False
    assert catalogo.esta_eliminado(104) is True
    # los demás siguen activos
    for i in [101, 102, 103, 105, 106, 107]:
        evento, _ = catalogo.consultar_evento(i)
        assert evento is not None


def test_identificador_eliminado_no_se_reutiliza():
    catalogo = Catalogo()
    _alta(catalogo, 200, 5.0, datetime(2026, 9, 10, 9, 0, 0))
    catalogo.eliminar_evento(200)

    with pytest.raises(ValidacionError):
        _alta(catalogo, 200, 6.0, datetime(2026, 9, 10, 10, 0, 0))


def test_eliminar_identificador_inexistente():
    catalogo = Catalogo()
    with pytest.raises(ValidacionError):
        catalogo.eliminar_evento(999)


# ---------------- archivo de subárboles ----------------

def test_archivar_rama_sin_ramas_elegibles_no_modifica_nada():
    catalogo = Catalogo()
    # eventos de alta prioridad y recientes: ninguno es elegible
    _alta(catalogo, 300, 6.5, datetime(2026, 9, 10, 11, 0, 0))
    _alta(catalogo, 301, 6.2, datetime(2026, 9, 10, 11, 30, 0))

    resultado = catalogo.archivar_rama_antigua(RELOJ)

    assert resultado == []
    assert len(catalogo) == 2


def test_archivar_rama_encuentra_la_mayor_subrama_elegible():
    """
    Construye un catálogo con eventos de prioridad baja y antiguos
    (elegibles) mezclados con un evento de prioridad alta (no elegible),
    y verifica que archivar_rama_antigua identifica correctamente la
    mayor sub-rama totalmente elegible: se compara contra lo que la
    propia función de bajo nivel del AVL (subarboles_elegibles) reporta
    como el mejor candidato, en vez de asumir a mano la forma del árbol.
    """
    catalogo = Catalogo()
    fecha_antigua = datetime(2026, 9, 1, 9, 0, 0)  # antigüedad > 72h por defecto

    # cinco eventos de prioridad baja (magnitud < 4.5) y antiguos
    for i in range(1, 6):
        _alta(catalogo, 400 + i, 2.0, fecha_antigua)

    # un evento de prioridad alta: por construcción de la clave K=(P,M,I),
    # cae en una zona distinta del árbol (P mayor), así que cualquier
    # subárbol que lo incluya deja de ser elegible
    _alta(catalogo, 500, 6.5, fecha_antigua)

    def es_elegible(evento):
        antiguedad_horas = (RELOJ - evento.fecha_hora).total_seconds() / 3600.0
        return evento.prioridad == 1 and antiguedad_horas > catalogo.t_horas

    esperado = catalogo.avl.subarboles_elegibles(es_elegible)
    assert esperado  # debe haber al menos una rama elegible
    mejor_esperado = max(esperado, key=lambda c: (c[1], c[2], c[0].elemento.identificador))
    ids_esperados = sorted(e.identificador for e in Catalogo._eventos_del_subarbol(mejor_esperado[0]))

    resultado = catalogo.archivar_rama_antigua(RELOJ)

    assert sorted(resultado) == ids_esperados
    assert 500 not in resultado  # el evento de prioridad alta nunca se archiva
    assert len(catalogo) == 6 - len(ids_esperados)
    for identificador in ids_esperados:
        assert catalogo.esta_archivado(identificador)


def test_rama_con_raiz_de_baja_prioridad_no_es_elegible_si_contiene_uno_de_mayor_prioridad():
    """
    Caso explícito del enunciado (sección 16): una rama cuya raíz sea de
    baja prioridad NO es elegible si contiene un descendiente de
    prioridad mayor.

    Con solo 2 eventos, uno de los dos siempre termina siendo antepasado
    del otro en el AVL (un árbol de 2 nodos es una cadena), así que no
    alcanza para mostrar una subrama pequeña y elegible aparte de la
    grande y no elegible. Con 3 eventos balanceados sí se puede: la raíz
    queda con un hijo de baja prioridad (elegible por sí solo) y otro de
    prioridad alta (que invalida a la raíz completa, pero no al hermano).
    """
    catalogo = Catalogo()
    fecha_antigua = datetime(2026, 9, 1, 9, 0, 0)
    _alta(catalogo, 700, 1.0, fecha_antigua)   # prioridad baja, antiguo -> quedará como hijo aislado
    _alta(catalogo, 701, 3.0, fecha_antigua)   # prioridad baja, antiguo -> quedará como raíz
    _alta(catalogo, 702, 6.0, fecha_antigua)   # prioridad alta, antiguo también -> invalida a la raíz

    def es_elegible(evento):
        antiguedad_horas = (RELOJ - evento.fecha_hora).total_seconds() / 3600.0
        return evento.prioridad == 1 and antiguedad_horas > catalogo.t_horas

    candidatas = catalogo.avl.subarboles_elegibles(es_elegible)
    ids_por_subarbol = [sorted(e.identificador for e in Catalogo._eventos_del_subarbol(c[0]))
                         for c in candidatas]

    assert [700, 701, 702] not in ids_por_subarbol  # el árbol completo nunca es elegible
    assert [700] in ids_por_subarbol                 # pero el hijo de baja prioridad, aislado, sí
    assert [701] not in ids_por_subarbol             # la raíz sola nunca aparece: su subárbol real
    assert [702] not in ids_por_subarbol             # incluye a 702, y 702 no es de prioridad baja


def test_archivar_conserva_datos_en_el_historico():
    catalogo = Catalogo()
    fecha_antigua = datetime(2026, 9, 1, 9, 0, 0)
    _alta(catalogo, 700, 2.0, fecha_antigua)

    catalogo.archivar_rama_antigua(RELOJ)

    assert catalogo.esta_archivado(700)
    assert catalogo.esta_activo(700) is False
    evento, _ = catalogo.consultar_evento(700)
    assert evento is None  # consultar_evento solo mira activos


# ---------------- asociaciones candidato/réplica ----------------

def test_es_candidato_exige_mayor_magnitud_y_ocurrir_antes():
    a = Evento(1, 6.0, 10.0, 500.0, 500.0, datetime(2026, 9, 7, 9, 0, 0), "EST-01")
    a.actualizar_prioridad(False)
    b = Evento(2, 5.0, 10.0, 500.0, 500.0, datetime(2026, 9, 7, 10, 0, 0), "EST-01")
    b.actualizar_prioridad(False)

    assert es_candidato(a, b, w_horas=48, r_km=40) is True
    assert es_candidato(b, a, w_horas=48, r_km=40) is False  # b tiene menor magnitud


def test_es_candidato_respeta_limites_de_w_y_r():
    a = Evento(1, 6.0, 10.0, 0.0, 0.0, datetime(2026, 9, 7, 9, 0, 0), "EST-01")
    a.actualizar_prioridad(False)
    b = Evento(2, 5.0, 10.0, 100.0, 0.0, datetime(2026, 9, 10, 9, 0, 0), "EST-01")  # 3 días después, 100 km
    b.actualizar_prioridad(False)

    assert es_candidato(a, b, w_horas=48, r_km=200) is False  # excede W (72h > 48h)
    assert es_candidato(a, b, w_horas=100, r_km=40) is False  # excede R (100km > 40km)
    assert es_candidato(a, b, w_horas=100, r_km=200) is True  # dentro de ambos límites


def test_elegir_referencia_desempata_por_magnitud_luego_tiempo_luego_distancia_luego_id():
    b = Evento(99, 4.0, 10.0, 500.0, 500.0, datetime(2026, 9, 7, 12, 0, 0), "EST-01")
    b.actualizar_prioridad(False)

    def candidato(identificador, magnitud, hora, x):
        e = Evento(identificador, magnitud, 10.0, x, 500.0,
                    datetime(2026, 9, 7, hora, 0, 0), "EST-01")
        e.actualizar_prioridad(False)
        return e

    mayor_magnitud = candidato(1, 6.0, 9, 500.0)
    menor_magnitud = candidato(2, 5.0, 9, 500.0)

    elegido = elegir_referencia(b, [mayor_magnitud, menor_magnitud])
    assert elegido.identificador == 1  # gana la mayor magnitud

    # empate en magnitud: gana el más cercano en el tiempo
    cercano_en_tiempo = candidato(3, 6.0, 11, 500.0)
    lejano_en_tiempo = candidato(4, 6.0, 8, 500.0)
    elegido2 = elegir_referencia(b, [cercano_en_tiempo, lejano_en_tiempo])
    assert elegido2.identificador == 3


def test_referencia_de_evento_tardio_caso_de_la_seccion_16():
    """
    Sección 16, "Reporte tardío": eventos de M=5.6 a las 10:00 y M=4.2 a
    las 10:20; luego llega uno de M=6.1 ocurrido a las 09:55 (antes que
    los otros dos, aunque se reciba después). El nuevo evento debe volverse
    la referencia elegida de ambos, por tener mayor magnitud y ocurrir antes.
    """
    catalogo = Catalogo()
    _alta(catalogo, 800, 5.6, datetime(2026, 9, 10, 10, 0, 0))
    _alta(catalogo, 801, 4.2, datetime(2026, 9, 10, 10, 20, 0))

    # antes de que llegue el tardío: 800 (M=5.6, antes) es candidato de 801
    assert catalogo.referencia_de(801) == 800
    assert catalogo.referencia_de(800) is None  # 800 no tiene candidatos aún

    _alta(catalogo, 802, 6.1, datetime(2026, 9, 10, 9, 55, 0))  # el tardío

    assert catalogo.referencia_de(800) == 802
    assert catalogo.referencia_de(801) == 802
    assert sorted(catalogo.eventos_que_referencian(802)) == [800, 801]


def test_eliminar_evento_de_referencia_actualiza_las_asociaciones_afectadas():
    catalogo = Catalogo()
    _alta(catalogo, 900, 6.0, datetime(2026, 9, 10, 9, 0, 0))
    _alta(catalogo, 901, 5.0, datetime(2026, 9, 10, 9, 30, 0))
    assert catalogo.referencia_de(901) == 900

    catalogo.eliminar_evento(900)

    assert catalogo.referencia_de(901) is None  # 900 ya no existe como candidato


def test_configurar_asociaciones_valida_valores_positivos():
    catalogo = Catalogo()
    with pytest.raises(ValidacionError):
        catalogo.configurar_asociaciones(w_horas=0)
    with pytest.raises(ValidacionError):
        catalogo.configurar_asociaciones(r_km=-5)


def test_cambiar_r_reduce_candidatos_y_actualiza_asociaciones():
    catalogo = Catalogo()
    _alta(catalogo, 1000, 6.0, datetime(2026, 9, 10, 9, 0, 0), x=0.0, y=0.0)
    _alta(catalogo, 1001, 5.0, datetime(2026, 9, 10, 9, 30, 0), x=30.0, y=0.0)  # 30 km de distancia

    assert catalogo.referencia_de(1001) == 1000  # dentro del R=40 por defecto

    catalogo.configurar_asociaciones(r_km=10.0)  # ahora 30km > 10km

    assert catalogo.referencia_de(1001) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])