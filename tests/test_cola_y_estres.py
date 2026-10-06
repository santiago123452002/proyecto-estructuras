"""
Phase 4 tests: Report, ColaReportes (FIFO), the decision table
from Section 6 (Catalogo.procesar_reporte), and stress mode with
global AVL recovery (Section 8).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
import pytest

from core import Zona, Catalogo, ValidacionError
from core.reporte import Reporte
from core.cola_reportes import ColaReportes
from core.resultado_reporte import TipoResultadoReporte
from core.procesador_reportes import procesar_siguiente, procesar_todos


RELOJ = datetime(2026, 9, 7, 12, 0, 0)


def _zonas_ejemplo():
    return [
        Zona("Ciudad Central", 400.0, 600.0, 400.0, 600.0, poblada=True),
        Zona("Zona Rural", 0.0, 400.0, 0.0, 400.0, poblada=False),
    ]


def _reporte(identificador, magnitud, revision, estacion, profundidad=10.0,
             x=500.0, y=500.0, fecha_hora=None):
    return Reporte(identificador, magnitud, profundidad, x, y,
                    fecha_hora or datetime(2026, 9, 7, 10, 0, 0), revision, estacion)


# ---------------- ColaReportes (FIFO) ----------------
def test_cola_mantiene_orden_fifo():
    cola = ColaReportes()
    cola.encolar("A")
    cola.encolar("B")
    cola.encolar("C")

    assert len(cola) == 3
    assert cola.desencolar() == "A"
    assert cola.desencolar() == "B"
    assert len(cola) == 1
    assert cola.ver_orden() == ["C"]
    assert cola.desencolar() == "C"
    assert cola.esta_vacia()


def test_cola_vacia_lanza_error():
    cola = ColaReportes()
    with pytest.raises(IndexError):
        cola.desencolar()


# ---------------- decision table (Section 6) ----------------
def test_identificador_desconocido_crea_evento_nuevo():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    reporte = _reporte(100, 6.0, revision=3, estacion="EST-01")  # first review can be > 1

    resultado = catalogo.procesar_reporte(reporte, zonas, RELOJ)

    assert resultado.tipo == TipoResultadoReporte.ALTA_NUEVA
    assert resultado.evento.revision == 3
    assert resultado.evento.prioridad == 3
    assert len(catalogo) == 1


def test_revision_mayor_sustituye_datos_y_recalcula_prioridad():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    catalogo.alta_evento(200, 4.0, 10.0, 500.0, 500.0,
                          datetime(2026, 9, 7, 9, 0, 0), "EST-01", zonas, RELOJ)

    reporte = _reporte(200, 6.5, revision=2, estacion="EST-02")
    resultado = catalogo.procesar_reporte(reporte, zonas, RELOJ)

    assert resultado.tipo == TipoResultadoReporte.ACTUALIZADO
    assert resultado.evento.revision == 2
    assert resultado.evento.prioridad == 3
    assert len(catalogo) == 1 # never created a second node

    evento, _ = catalogo.consultar_evento(200)
    assert evento.magnitud == 6.5


def test_igual_revision_e_iguales_datos_confirma_y_agrega_estacion():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    fecha = datetime(2026, 9, 7, 9, 0, 0)
    catalogo.alta_evento(300, 5.0, 10.0, 500.0, 500.0, fecha, "EST-01", zonas, RELOJ)

    reporte = _reporte(300, 5.0, revision=1, estacion="EST-02", fecha_hora=fecha)
    resultado = catalogo.procesar_reporte(reporte, zonas, RELOJ)

    assert resultado.tipo == TipoResultadoReporte.CONFIRMADO
    evento, _ = catalogo.consultar_evento(300)
    assert evento.estaciones == {"EST-01", "EST-02"}
    assert len(catalogo) == 1

    # repeating the same confirmation does not create nodes or duplicate stations
    resultado2 = catalogo.procesar_reporte(
        _reporte(300, 5.0, revision=1, estacion="EST-02", fecha_hora=fecha), zonas, RELOJ
    )
    assert resultado2.tipo == TipoResultadoReporte.CONFIRMADO
    evento2, _ = catalogo.consultar_evento(300)
    assert evento2.estaciones == {"EST-01", "EST-02"}


def test_igual_revision_y_datos_distintos_es_conflicto():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    catalogo.alta_evento(400, 5.0, 10.0, 500.0, 500.0,
                          datetime(2026, 9, 7, 9, 0, 0), "EST-01", zonas, RELOJ)

    reporte = _reporte(400, 7.0, revision=1, estacion="EST-02")  # same revision, different magnitude
    resultado = catalogo.procesar_reporte(reporte, zonas, RELOJ)

    assert resultado.tipo == TipoResultadoReporte.CONFLICTO
    evento, _ = catalogo.consultar_evento(400)
    assert evento.magnitud == 5.0  # nothing was overwritten


def test_revision_menor_se_descarta_como_antiguo():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    catalogo.corregir_evento  
    catalogo.alta_evento(500, 5.0, 10.0, 500.0, 500.0,
                          datetime(2026, 9, 7, 9, 0, 0), "EST-01", zonas, RELOJ)
    catalogo.corregir_evento(500, zonas, RELOJ, magnitud=5.5)  

    reporte = _reporte(500, 9.0, revision=1, estacion="EST-02")  
    resultado = catalogo.procesar_reporte(reporte, zonas, RELOJ)

    assert resultado.tipo == TipoResultadoReporte.ANTIGUO
    evento, _ = catalogo.consultar_evento(500)
    assert evento.magnitud == 5.5
    assert evento.revision == 2


# ---------------- reporte tardío (caso de la sección 16) ----------------

def test_reporte_tardio_no_reordena_por_fecha_de_llegada():
    """
    Section 16: events of M=5.6 at 10:00 and M=4.2 at
    10:20; then one of M=6.1 arrives, which occurred at 09:55 (before the
    other two, but was received later). The system must register it anyway,
    because each identifier represents a different earthquake.
    """
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()

    catalogo.procesar_reporte(
        _reporte(601, 5.6, revision=1, estacion="EST-01", fecha_hora=datetime(2026, 9, 7, 10, 0)),
        zonas, RELOJ,
    )
    catalogo.procesar_reporte(
        _reporte(602, 4.2, revision=1, estacion="EST-01", fecha_hora=datetime(2026, 9, 7, 10, 20)),
        zonas, RELOJ,
    )
    resultado_tardio = catalogo.procesar_reporte(
        _reporte(603, 6.1, revision=1, estacion="EST-02", fecha_hora=datetime(2026, 9, 7, 9, 55)),
        zonas, RELOJ,
    )

    assert resultado_tardio.tipo == TipoResultadoReporte.ALTA_NUEVA
    assert len(catalogo) == 3


# ---------------- deleted identifier (rejection, Section 6) ----------------
def test_reporte_a_identificador_eliminado_se_rechaza():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    catalogo.alta_evento(999, 5.0, 10.0, 500.0, 500.0,
                          datetime(2026, 9, 7, 9, 0, 0), "EST-01", zonas, RELOJ)
    catalogo.eliminar_evento(999)  # simulates a deletion that already occurred

    reporte = _reporte(999, 5.0, revision=1, estacion="EST-01")
    resultado = catalogo.procesar_reporte(reporte, zonas, RELOJ)

    assert resultado.tipo == TipoResultadoReporte.RECHAZADO_ELIMINADO
    assert len(catalogo) == 0


# ---------------- queue processing (step-by-step and continuous) ----------------
def test_procesar_siguiente_consume_un_reporte_a_la_vez():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    cola = ColaReportes()
    cola.encolar(_reporte(700, 5.0, revision=1, estacion="EST-01"))
    cola.encolar(_reporte(701, 6.0, revision=1, estacion="EST-01"))

    reporte, resultado = procesar_siguiente(cola, catalogo, zonas, RELOJ)
    assert reporte.identificador == 700
    assert resultado.tipo == TipoResultadoReporte.ALTA_NUEVA
    assert len(cola) == 1
    assert len(catalogo) == 1


def test_procesar_todos_resuelve_una_rafaga_completa():
    """
    Burst with new event, confirmation, old report, and correction that
    changes the key, as required by Section 8.
    """
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    fecha = datetime(2026, 9, 7, 9, 0, 0)
    cola = ColaReportes()

    cola.encolar(_reporte(800, 4.0, revision=1, estacion="EST-01", fecha_hora=fecha))   # new event
    cola.encolar(_reporte(800, 4.0, revision=1, estacion="EST-02", fecha_hora=fecha))   # confirmation
    cola.encolar(_reporte(800, 4.0, revision=1, estacion="EST-03", fecha_hora=fecha))   # confirmation again
    cola.encolar(_reporte(800, 6.5, revision=2, estacion="EST-01", fecha_hora=fecha))   # correction: changes key

    resultados = procesar_todos(cola, catalogo, zonas, RELOJ)

    tipos = [resultado.tipo for _, resultado in resultados]
    assert tipos == [
        TipoResultadoReporte.ALTA_NUEVA,
        TipoResultadoReporte.CONFIRMADO,
        TipoResultadoReporte.CONFIRMADO,
        TipoResultadoReporte.ACTUALIZADO,
    ]
    assert cola.esta_vacia()
    evento, _ = catalogo.consultar_evento(800)
    assert evento.prioridad == 3
    assert evento.revision == 2
    assert len(catalogo) == 1


# ---------------- stress mode and recovery (Section 8 and case from Section 16) ----------------
def test_modo_estres_permite_desbalance_y_recuperar_equilibrio_lo_corrige():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    cola = ColaReportes()

    # 20 new events with the same priority/magnitude and ascending identifier:
    # in normal mode the AVL would balance them; in stress mode there are no rotations,
    # so it degenerates into a chain (height difference >> 2).
    for i in range(1, 21):
        cola.encolar(_reporte(1000 + i, 5.0, revision=1, estacion="EST-01"))

    procesar_todos(cola, catalogo, zonas, RELOJ, balancear=False)

    assert len(catalogo) == 20
    assert catalogo.esta_balanceado() is False  # degenerate, as expected in stress mode
    assert catalogo.avl.altura_total() == 19    # pure chain: one branch per insertion

    balanceado = catalogo.recuperar_equilibrio()

    assert balanceado is True
    assert catalogo.esta_balanceado() is True
    assert catalogo.avl.altura_total() < 6      # log2(20) ~ 4.3; far below 19

    # the order and number of events are preserved
    claves = [e.clave for e in catalogo.avl.recorrido_inorden()]
    assert claves == sorted(claves)
    assert len(catalogo.avl) == 20

    # the identifier index remains valid: rotations do not
    # create or destroy nodes, they only rearrange pointers
    evento, visitados = catalogo.consultar_evento(1010)
    assert evento is not None
    assert evento.identificador == 1010
    assert visitados <= 6


def test_recuperar_equilibrio_registra_rotaciones_de_recuperacion():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    cola = ColaReportes()
    for i in range(1, 16):
        cola.encolar(_reporte(2000 + i, 5.0, revision=1, estacion="EST-01"))

    procesar_todos(cola, catalogo, zonas, RELOJ, balancear=False)
    assert catalogo.avl.contador_rotaciones_recuperacion == 0  # recovery has not yet been performed

    catalogo.recuperar_equilibrio()

    assert catalogo.avl.contador_rotaciones_recuperacion > 0  # it did have to rotate


def test_alta_manual_normal_no_se_ve_afectada_por_el_modo_estres():
    """Stress mode only applies to processing reports through the queue;
    manual insertions (Section 6) continue to balance normally."""
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    for i in range(1, 11):
        catalogo.alta_evento(3000 + i, 5.0, 10.0, 500.0, 500.0,
                              datetime(2026, 9, 7, 9, 0, 0), "EST-01", zonas, RELOJ)
    assert catalogo.esta_balanceado() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])