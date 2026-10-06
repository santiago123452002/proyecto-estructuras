"""
Phase 2 + 3 tests: Event, priority, zone, and the event
creation / query / correction operations on the Catalog (which wraps the
Phase 1 AVLTree plus the identifier index).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
import pytest

from core import Zona, calcular_prioridad, Evento, ValidacionError, Catalogo


RELOJ = datetime(2026, 9, 7, 12, 0, 0)


def _zonas_ejemplo():
    return [
        Zona("Ciudad Central", 400.0, 600.0, 400.0, 600.0, poblada=True),
        Zona("Zona Rural", 0.0, 400.0, 0.0, 400.0, poblada=False),
    ]


# ---------------- priority (Section 4) ----------------

def test_prioridad_alta_por_magnitud():
    assert calcular_prioridad(6.0, 500.0, en_zona_poblada=False) == 3


def test_prioridad_alta_por_limite_exacto_en_zona_poblada():
    # M = 4.5, H = 30.0, populated zone -> priority 3 (inclusive boundaries, example from the statement)
    assert calcular_prioridad(4.5, 30.0, en_zona_poblada=True) == 3


def test_mismo_evento_fuera_de_zona_poblada_es_prioridad_2():
    assert calcular_prioridad(4.5, 30.0, en_zona_poblada=False) == 2


def test_prioridad_baja():
    assert calcular_prioridad(3.0, 500.0, en_zona_poblada=False) == 1


# ---------------- zone (inclusive boundary) ----------------

def test_zona_contiene_borde():
    zona = Zona("Z", 0.0, 100.0, 0.0, 100.0, poblada=True)
    assert zona.contiene(100.0, 100.0) is True
    assert zona.contiene(100.1, 50.0) is False


#---------------- Event validation ----------------

def test_evento_rechaza_magnitud_fuera_de_rango():
    with pytest.raises(ValidacionError):
        Evento(1, 11.0, 10.0, 500.0, 500.0, datetime(2026, 9, 7), "EST-01")


def test_evento_rechaza_mas_de_un_decimal():
    with pytest.raises(ValidacionError):
        Evento(1, 5.55, 10.0, 500.0, 500.0, datetime(2026, 9, 7), "EST-01")


# ---------------- event creation ----------------

def test_alta_evento_calcula_prioridad_y_clave():
    catalogo = Catalogo()
    evento = catalogo.alta_evento(
        identificador=10, magnitud=6.0, profundidad=10.0,
        epicentro_x=500.0, epicentro_y=500.0,
        fecha_hora=datetime(2026, 9, 7, 10, 0, 0),
        estacion_origen="EST-01", zonas=_zonas_ejemplo(), reloj_simulacion=RELOJ,
    )
    assert evento.prioridad == 3
    assert evento.clave == (3, 6.0, 10)
    assert evento.estado_atencion == "pendiente"
    assert len(catalogo) == 1


def test_alta_rechaza_identificador_duplicado_sin_modificar_nada():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    catalogo.alta_evento(10, 6.0, 10.0, 500.0, 500.0,
                          datetime(2026, 9, 7, 10, 0, 0), "EST-01", zonas, RELOJ)
    with pytest.raises(ValidacionError):
        catalogo.alta_evento(10, 5.0, 10.0, 500.0, 500.0,
                              datetime(2026, 9, 7, 10, 0, 0), "EST-02", zonas, RELOJ)
    assert len(catalogo) == 1


def test_alta_rechaza_fecha_posterior_al_reloj():
    catalogo = Catalogo()
    with pytest.raises(ValidacionError):
        catalogo.alta_evento(11, 6.0, 10.0, 500.0, 500.0,
                              datetime(2027, 1, 1), "EST-01", _zonas_ejemplo(), RELOJ)
    assert len(catalogo) == 0


# ---------------- query ----------------
def test_consultar_evento_existente_reporta_nodos_visitados():
    catalogo = Catalogo()
    catalogo.alta_evento(20, 5.0, 10.0, 500.0, 500.0,
                          datetime(2026, 9, 7, 10, 0, 0), "EST-01", _zonas_ejemplo(), RELOJ)
    evento, visitados = catalogo.consultar_evento(20)
    assert evento is not None
    assert evento.identificador == 20
    assert visitados >= 1


def test_consultar_evento_inexistente():
    catalogo = Catalogo()
    evento, visitados = catalogo.consultar_evento(999)
    assert evento is None
    assert visitados == 0


# ---------------- correction (mandatory case from Section 16) ----------------
def test_correccion_cambia_prioridad_de_2_a_3_y_sube_revision():
    """
    Mandatory minimum case (Section 16): correct an event from M=4.8,
    H=70.0 to M=6.2, H=15.0. The priority must change from 2 to 3.
    """
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    catalogo.alta_evento(30, 4.8, 70.0, 500.0, 500.0,
                          datetime(2026, 9, 7, 10, 0, 0), "EST-01", zonas, RELOJ)
    evento_inicial, _ = catalogo.consultar_evento(30)
    assert evento_inicial.prioridad == 2
    assert evento_inicial.revision == 1

    actualizado = catalogo.corregir_evento(30, zonas, RELOJ, magnitud=6.2, profundidad=15.0)

    assert actualizado.prioridad == 3
    assert actualizado.revision == 2
    assert actualizado.estado_atencion == "pendiente"
    assert actualizado.identificador == 30

    evento_final, _ = catalogo.consultar_evento(30)
    assert evento_final.clave == (3, 6.2, 30)
    assert len(catalogo) == 1  # a second node was never created


def test_correccion_invalida_no_aplica_ningun_cambio():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    catalogo.alta_evento(40, 5.0, 10.0, 500.0, 500.0,
                          datetime(2026, 9, 7, 10, 0, 0), "EST-01", zonas, RELOJ)
    with pytest.raises(ValidacionError):
        catalogo.corregir_evento(40, zonas, RELOJ, magnitud=99.0)  # out of range

    evento, _ = catalogo.consultar_evento(40)
    assert evento.magnitud == 5.0
    assert evento.revision == 1


def test_correccion_sobre_identificador_inexistente():
    catalogo = Catalogo()
    with pytest.raises(ValidacionError):
        catalogo.corregir_evento(999, _zonas_ejemplo(), RELOJ, magnitud=5.0)


# ---------------- mark as reviewed ----------------
def test_marcar_revisado_no_cambia_clave():
    catalogo = Catalogo()
    catalogo.alta_evento(50, 5.0, 10.0, 500.0, 500.0,
                          datetime(2026, 9, 7, 10, 0, 0), "EST-01", _zonas_ejemplo(), RELOJ)
    evento, _ = catalogo.consultar_evento(50)
    clave_antes = evento.clave

    catalogo.marcar_revisado(50)

    evento_despues, _ = catalogo.consultar_evento(50)
    assert evento_despues.estado_atencion == "revisado"
    assert evento_despues.clave == clave_antes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])