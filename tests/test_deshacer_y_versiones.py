"""
Pruebas de la Fase 6: Pila LIFO explícita, y Escenario (deshacer sobre
alta/corrección/eliminación/archivo/parámetros/reloj/modo/cola, más
versiones nombradas persistentes) — sección 13.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import pytest

from core import Zona, Escenario, ValidacionError
from core.pila import Pila
from core.reporte import Reporte
from core.resultado_reporte import TipoResultadoReporte


RELOJ = datetime(2026, 9, 10, 12, 0, 0)


def _zonas_ejemplo():
    return [
        Zona("Ciudad Central", 400.0, 600.0, 400.0, 600.0, poblada=True),
        Zona("Zona Rural", 0.0, 400.0, 0.0, 400.0, poblada=False),
    ]


def _escenario():
    return Escenario(zonas=_zonas_ejemplo(), reloj_simulacion=RELOJ)


def _reporte(identificador, magnitud, revision, estacion, fecha_hora=None):
    return Reporte(identificador, magnitud, 10.0, 500.0, 500.0,
                    fecha_hora or datetime(2026, 9, 10, 9, 0, 0), revision, estacion)


# ---------------- Pila (LIFO) ----------------

def test_pila_es_lifo():
    pila = Pila()
    pila.apilar("primero")
    pila.apilar("segundo")
    pila.apilar("tercero")

    assert len(pila) == 3
    assert pila.ver_cima() == "tercero"
    assert pila.desapilar() == "tercero"
    assert pila.desapilar() == "segundo"
    assert len(pila) == 1
    assert pila.desapilar() == "primero"
    assert pila.esta_vacia()


def test_pila_vacia_lanza_error():
    pila = Pila()
    with pytest.raises(IndexError):
        pila.desapilar()
    with pytest.raises(IndexError):
        pila.ver_cima()


# ---------------- deshacer: alta ----------------

def test_deshacer_alta_evento_lo_retira_por_completo():
    escenario = _escenario()
    escenario.alta_evento(100, 6.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    assert len(escenario.catalogo) == 1

    deshecho = escenario.deshacer()

    assert deshecho is True
    assert len(escenario.catalogo) == 0
    assert not escenario.catalogo.identificador_en_uso(100)  # como si nunca hubiera existido


def test_alta_invalida_no_deja_nada_que_deshacer():
    escenario = _escenario()
    with pytest.raises(ValidacionError):
        escenario.alta_evento(101, 99.0, 10.0, 500.0, 500.0,  # magnitud fuera de rango
                               datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    assert escenario.hay_algo_que_deshacer() is False


def test_deshacer_sin_acciones_previas_devuelve_false():
    escenario = _escenario()
    assert escenario.deshacer() is False


# ---------------- deshacer: corrección ----------------

def test_deshacer_correccion_restaura_magnitud_y_revision_anteriores():
    escenario = _escenario()
    escenario.alta_evento(200, 4.8, 70.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.corregir_evento(200, magnitud=6.2, profundidad=15.0)

    evento_tras_correccion, _ = escenario.catalogo.consultar_evento(200)
    assert evento_tras_correccion.prioridad == 3
    assert evento_tras_correccion.revision == 2

    escenario.deshacer()  # deshace la corrección

    evento_restaurado, _ = escenario.catalogo.consultar_evento(200)
    assert evento_restaurado.magnitud == 4.8
    assert evento_restaurado.revision == 1
    assert evento_restaurado.prioridad == 2


# ---------------- deshacer: eliminación y archivo ----------------

def test_deshacer_eliminacion_reactiva_el_evento():
    escenario = _escenario()
    escenario.alta_evento(300, 5.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.eliminar_evento(300)

    assert escenario.catalogo.esta_eliminado(300)
    assert not escenario.catalogo.esta_activo(300)

    escenario.deshacer()

    assert escenario.catalogo.esta_activo(300)
    assert not escenario.catalogo.esta_eliminado(300)


def test_deshacer_archivo_masivo_reactiva_todos_los_eventos_archivados():
    escenario = _escenario()
    fecha_antigua = datetime(2026, 9, 1, 9, 0, 0)
    for identificador in (400, 401, 402):
        escenario.alta_evento(identificador, 2.0, 10.0, 500.0, 500.0, fecha_antigua, "EST-01")

    archivados = escenario.archivar_rama_antigua()
    assert len(archivados) == 3
    assert len(escenario.catalogo) == 0

    escenario.deshacer()

    assert len(escenario.catalogo) == 3
    for identificador in (400, 401, 402):
        assert escenario.catalogo.esta_activo(identificador)
        assert not escenario.catalogo.esta_archivado(identificador)


# ---------------- deshacer: parámetros, reloj y modo ----------------

def test_deshacer_cambio_de_parametros_w_r():
    escenario = _escenario()
    escenario.configurar_asociaciones(w_horas=10.0, r_km=5.0)
    assert escenario.catalogo.w_horas == 10.0

    escenario.deshacer()

    assert escenario.catalogo.w_horas == 48.0  # valor inicial por defecto
    assert escenario.catalogo.r_km == 40.0


def test_deshacer_avance_del_reloj():
    escenario = _escenario()
    nuevo_reloj = RELOJ + timedelta(hours=5)
    escenario.avanzar_reloj(nuevo_reloj)
    assert escenario.reloj_simulacion == nuevo_reloj

    escenario.deshacer()

    assert escenario.reloj_simulacion == RELOJ


def test_avanzar_reloj_hacia_atras_no_deja_nada_que_deshacer():
    escenario = _escenario()
    with pytest.raises(ValidacionError):
        escenario.avanzar_reloj(RELOJ - timedelta(hours=1))
    assert escenario.hay_algo_que_deshacer() is False


def test_deshacer_cambio_de_modo():
    escenario = _escenario()
    escenario.cambiar_modo("estres")
    assert escenario.modo == "estres"

    escenario.deshacer()

    assert escenario.modo == "normal"


# ---------------- deshacer: paso de cola (incluso si se descartó) ----------------

def test_deshacer_paso_de_cola_restablece_posicion_del_reporte():
    """
    Sección 13: deshacer un paso de cola restablece tanto el escenario
    como la posición del reporte en la cola, INCLUSO si ese paso había
    descartado un reporte (revisión antigua, en este caso).
    """
    escenario = _escenario()
    escenario.alta_evento(500, 5.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.corregir_evento(500, magnitud=5.5)  # sube a revisión 2

    escenario.cola.encolar(_reporte(500, 9.0, revision=1, estacion="EST-02"))  # revisión vieja
    assert len(escenario.cola) == 1

    reporte, resultado = escenario.procesar_siguiente_reporte()

    assert resultado.tipo == TipoResultadoReporte.ANTIGUO
    assert escenario.cola.esta_vacia()
    assert escenario.metricas["reportes_procesados"] == 1

    escenario.deshacer()

    assert len(escenario.cola) == 1  # el reporte descartado vuelve a la cola
    assert escenario.cola.ver_orden()[0].identificador == 500
    assert escenario.metricas["reportes_procesados"] == 0


def test_deshacer_paso_de_cola_con_alta_nueva():
    escenario = _escenario()
    escenario.cola.encolar(_reporte(600, 6.0, revision=1, estacion="EST-01"))

    escenario.procesar_siguiente_reporte()
    assert len(escenario.catalogo) == 1
    assert escenario.cola.esta_vacia()

    escenario.deshacer()

    assert len(escenario.catalogo) == 0
    assert len(escenario.cola) == 1


# ---------------- deshacer: recuperación global (modo estrés) ----------------

def test_deshacer_recuperar_equilibrio_regresa_al_arbol_degradado():
    escenario = _escenario()
    escenario.cambiar_modo("estres")
    for i in range(1, 16):
        escenario.cola.encolar(_reporte(700 + i, 5.0, revision=1, estacion="EST-01"))
        escenario.procesar_siguiente_reporte()

    assert escenario.catalogo.esta_balanceado() is False
    altura_degradada = escenario.catalogo.avl.altura_total()

    escenario.recuperar_equilibrio()
    assert escenario.catalogo.esta_balanceado() is True

    escenario.deshacer()

    assert escenario.catalogo.esta_balanceado() is False
    assert escenario.catalogo.avl.altura_total() == altura_degradada


# ---------------- deshacer acciones sucesivas ----------------

def test_deshacer_dos_acciones_sucesivas_en_orden_inverso():
    escenario = _escenario()
    escenario.alta_evento(800, 5.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.alta_evento(801, 6.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    assert len(escenario.catalogo) == 2

    escenario.deshacer()
    assert len(escenario.catalogo) == 1
    assert escenario.catalogo.esta_activo(800)
    assert not escenario.catalogo.esta_activo(801)

    escenario.deshacer()
    assert len(escenario.catalogo) == 0

    assert escenario.deshacer() is False  # ya no queda nada por deshacer


# ---------------- versiones nombradas persistentes ----------------

def test_guardar_y_restaurar_version():
    escenario = _escenario()
    escenario.alta_evento(900, 5.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.guardar_version("antes-de-corregir")

    escenario.corregir_evento(900, magnitud=6.5)
    evento_modificado, _ = escenario.catalogo.consultar_evento(900)
    assert evento_modificado.magnitud == 6.5

    escenario.restaurar_version("antes-de-corregir")

    evento_restaurado, _ = escenario.catalogo.consultar_evento(900)
    assert evento_restaurado.magnitud == 5.0
    assert evento_restaurado.revision == 1


def test_restaurar_version_es_deshacible():
    escenario = _escenario()
    escenario.alta_evento(1000, 5.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.guardar_version("v1")
    escenario.corregir_evento(1000, magnitud=6.5)

    escenario.restaurar_version("v1")
    evento, _ = escenario.catalogo.consultar_evento(1000)
    assert evento.magnitud == 5.0

    escenario.deshacer()  # deshace SOLO la restauración, no la corrección original

    evento_tras_deshacer, _ = escenario.catalogo.consultar_evento(1000)
    assert evento_tras_deshacer.magnitud == 6.5


def test_restaurar_version_inexistente_lanza_error():
    escenario = _escenario()
    with pytest.raises(ValidacionError):
        escenario.restaurar_version("no-existe")


def test_versiones_no_se_contaminan_con_cambios_posteriores():
    escenario = _escenario()
    escenario.alta_evento(1100, 5.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.guardar_version("v1")

    escenario.corregir_evento(1100, magnitud=7.0)
    escenario.restaurar_version("v1")
    escenario.corregir_evento(1100, magnitud=8.0)  # cambia el escenario ACTUAL, no la versión guardada

    escenario.restaurar_version("v1")  # debe volver a dar magnitud 5.0, no 8.0
    evento, _ = escenario.catalogo.consultar_evento(1100)
    assert evento.magnitud == 5.0


def test_listar_versiones():
    escenario = _escenario()
    escenario.alta_evento(1200, 5.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.guardar_version("b")
    escenario.guardar_version("a")
    assert escenario.listar_versiones() == ["a", "b"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
