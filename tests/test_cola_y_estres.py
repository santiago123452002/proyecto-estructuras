"""
Pruebas de la Fase 4: Reporte, ColaReportes (FIFO), la tabla de decisión
de la sección 6 (Catalogo.procesar_reporte) y el modo estrés con
recuperación global del AVL (sección 8).
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


# ---------------- tabla de decisión (sección 6) ----------------

def test_identificador_desconocido_crea_evento_nuevo():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    reporte = _reporte(100, 6.0, revision=3, estacion="EST-01")  # 1ra revisión puede ser > 1

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
    assert len(catalogo) == 1  # nunca se creó un segundo nodo

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

    # repetir la misma confirmación no crea nodos ni duplica estaciones
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

    reporte = _reporte(400, 7.0, revision=1, estacion="EST-02")  # misma revisión, otra magnitud
    resultado = catalogo.procesar_reporte(reporte, zonas, RELOJ)

    assert resultado.tipo == TipoResultadoReporte.CONFLICTO
    evento, _ = catalogo.consultar_evento(400)
    assert evento.magnitud == 5.0  # no se sobrescribió nada


def test_revision_menor_se_descarta_como_antiguo():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    catalogo.corregir_evento  # solo para referencia, no se usa aquí
    catalogo.alta_evento(500, 5.0, 10.0, 500.0, 500.0,
                          datetime(2026, 9, 7, 9, 0, 0), "EST-01", zonas, RELOJ)
    catalogo.corregir_evento(500, zonas, RELOJ, magnitud=5.5)  # sube a revisión 2

    reporte = _reporte(500, 9.0, revision=1, estacion="EST-02")  # revisión vieja
    resultado = catalogo.procesar_reporte(reporte, zonas, RELOJ)

    assert resultado.tipo == TipoResultadoReporte.ANTIGUO
    evento, _ = catalogo.consultar_evento(500)
    assert evento.magnitud == 5.5
    assert evento.revision == 2


# ---------------- reporte tardío (caso de la sección 16) ----------------

def test_reporte_tardio_no_reordena_por_fecha_de_llegada():
    """
    Sección 16: se reciben eventos de M=5.6 a las 10:00 y M=4.2 a las
    10:20; luego llega uno de M=6.1 ocurrido a las 09:55 (antes que los
    otros dos, pero recibido después). El sistema debe registrarlo igual,
    porque cada identificador es un terremoto distinto.
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


# ---------------- identificador eliminado (rechazo, sección 6) ----------------

def test_reporte_a_identificador_eliminado_se_rechaza():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    catalogo.alta_evento(999, 5.0, 10.0, 500.0, 500.0,
                          datetime(2026, 9, 7, 9, 0, 0), "EST-01", zonas, RELOJ)
    catalogo.eliminar_evento(999)  # simula una eliminación ya ocurrida

    reporte = _reporte(999, 5.0, revision=1, estacion="EST-01")
    resultado = catalogo.procesar_reporte(reporte, zonas, RELOJ)

    assert resultado.tipo == TipoResultadoReporte.RECHAZADO_ELIMINADO
    assert len(catalogo) == 0


# ---------------- procesamiento por cola (paso a paso y continuo) ----------------

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
    Ráfaga con alta, confirmación, reporte antiguo y corrección que
    cambia la clave, tal como pide la sección 8.
    """
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    fecha = datetime(2026, 9, 7, 9, 0, 0)
    cola = ColaReportes()

    cola.encolar(_reporte(800, 4.0, revision=1, estacion="EST-01", fecha_hora=fecha))   # alta
    cola.encolar(_reporte(800, 4.0, revision=1, estacion="EST-02", fecha_hora=fecha))   # confirmación
    cola.encolar(_reporte(800, 4.0, revision=1, estacion="EST-03", fecha_hora=fecha))   # confirmación otra vez
    cola.encolar(_reporte(800, 6.5, revision=2, estacion="EST-01", fecha_hora=fecha))   # corrección: cambia clave

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


# ---------------- modo estrés y recuperación (sección 8 y caso de la sección 16) ----------------

def test_modo_estres_permite_desbalance_y_recuperar_equilibrio_lo_corrige():
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    cola = ColaReportes()

    # 20 altas con la misma prioridad/magnitud e identificador ascendente:
    # en modo normal el AVL las balancearía; en modo estrés no se rota,
    # así que degenera en una cadena (diferencia de altura >> 2).
    for i in range(1, 21):
        cola.encolar(_reporte(1000 + i, 5.0, revision=1, estacion="EST-01"))

    procesar_todos(cola, catalogo, zonas, RELOJ, balancear=False)

    assert len(catalogo) == 20
    assert catalogo.esta_balanceado() is False  # degenerado, como se espera en estrés
    assert catalogo.avl.altura_total() == 19    # cadena pura: una rama por cada inserción

    balanceado = catalogo.recuperar_equilibrio()

    assert balanceado is True
    assert catalogo.esta_balanceado() is True
    assert catalogo.avl.altura_total() < 6      # log2(20) ~ 4.3; muy por debajo de 19

    # el orden y la cantidad de eventos se conservan
    claves = [e.clave for e in catalogo.avl.recorrido_inorden()]
    assert claves == sorted(claves)
    assert len(catalogo.avl) == 20

    # el índice por identificador sigue siendo válido: las rotaciones no
    # crean ni destruyen nodos, solo reordenan punteros
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
    assert catalogo.avl.contador_rotaciones_recuperacion == 0  # aún no se ha recuperado

    catalogo.recuperar_equilibrio()

    assert catalogo.avl.contador_rotaciones_recuperacion > 0  # sí tuvo que rotar


def test_alta_manual_normal_no_se_ve_afectada_por_el_modo_estres():
    """El modo estrés solo aplica al procesamiento de reportes por cola;
    las altas manuales (sección 6) siguen balanceando normalmente."""
    catalogo = Catalogo()
    zonas = _zonas_ejemplo()
    for i in range(1, 11):
        catalogo.alta_evento(3000 + i, 5.0, 10.0, 500.0, 500.0,
                              datetime(2026, 9, 7, 9, 0, 0), "EST-01", zonas, RELOJ)
    assert catalogo.esta_balanceado() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])