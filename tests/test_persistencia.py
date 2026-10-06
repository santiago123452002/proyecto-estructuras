"""
Phase 7 tests: complete structural saving, loading by topology (with
full validation), and loading by insertions (AVL vs BST comparison)
— Section 12.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import datetime, timedelta
import pytest

from core import Zona, Escenario, ValidacionError
from core.persistencia import (
    exportar_escenario, construir_escenario_desde_topologia,
    construir_arboles_por_insercion, guardar_json, leer_json,
)
from core.serializacion import fecha_a_texto, texto_a_fecha, evento_a_dict, nodo_a_dict


RELOJ = datetime(2026, 9, 10, 12, 0, 0)


def _zonas_ejemplo():
    return [
        Zona("Ciudad Central", 400.0, 600.0, 400.0, 600.0, poblada=True),
        Zona("Zona Rural", 0.0, 400.0, 0.0, 400.0, poblada=False),
    ]


def _escenario_con_datos():
    escenario = Escenario(zonas=_zonas_ejemplo(), reloj_simulacion=RELOJ)
    escenario.alta_evento(100, 6.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.alta_evento(101, 4.0, 10.0, 200.0, 200.0,
                           datetime(2026, 9, 10, 8, 0, 0), "EST-01")
    escenario.alta_evento(102, 5.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 7, 0, 0), "EST-02")
    return escenario


# ---------------- dates ----------------
def test_fecha_a_texto_y_de_vuelta():
    fecha = datetime(2026, 9, 7, 10, 0, 0)
    texto = fecha_a_texto(fecha)
    assert texto == "2026-09-07T10:00:00Z"
    assert texto_a_fecha(texto) == fecha


def test_texto_a_fecha_formato_invalido():
    with pytest.raises(ValidacionError):
        texto_a_fecha("no es una fecha")


# ---------------- structural saving: complete round-trip ----------------
def test_exportar_e_importar_reproduce_el_mismo_escenario():
    original = _escenario_con_datos()
    original.eliminar_evento(101)
    original.configurar_asociaciones(w_horas=10.0, r_km=5.0)

    datos = exportar_escenario(original)
# confirm that it is actually JSON-serializable, not just that it "looks" like a dict
    texto = json.dumps(datos)
    datos_releidos = json.loads(texto)

    reconstruido = construir_escenario_desde_topologia(datos_releidos)

    assert len(reconstruido.catalogo) == len(original.catalogo)
    assert reconstruido.catalogo.esta_eliminado(101)
    assert reconstruido.catalogo.w_horas == 10.0
    assert reconstruido.catalogo.r_km == 5.0
    assert reconstruido.reloj_simulacion == original.reloj_simulacion
    assert reconstruido.modo == original.modo

    evento_original, _ = original.catalogo.consultar_evento(100)
    evento_reconstruido, _ = reconstruido.catalogo.consultar_evento(100)
    assert evento_reconstruido.clave == evento_original.clave
    assert evento_reconstruido.magnitud == evento_original.magnitud
    assert evento_reconstruido.estaciones == evento_original.estaciones


def test_exportar_incluye_cola_en_orden_original():
    from core.reporte import Reporte
    escenario = _escenario_con_datos()
    escenario.cola.encolar(Reporte(200, 5.0, 10.0, 500.0, 500.0,
                                    datetime(2026, 9, 10, 9, 0, 0), 1, "EST-01"))
    escenario.cola.encolar(Reporte(201, 6.0, 10.0, 500.0, 500.0,
                                    datetime(2026, 9, 10, 9, 0, 0), 1, "EST-02"))

    datos = exportar_escenario(escenario)
    reconstruido = construir_escenario_desde_topologia(datos)

    orden_original = [r.identificador for r in escenario.cola.ver_orden()]
    orden_reconstruido = [r.identificador for r in reconstruido.cola.ver_orden()]
    assert orden_reconstruido == orden_original == [200, 201]


# ---------------- topology loading: validations ----------------
def test_carga_por_topologia_rechaza_prioridad_almacenada_incorrecta():
    escenario = _escenario_con_datos()
    datos = exportar_escenario(escenario)
    # manually corrupt the stored priority of the first event
    datos["arbol_activo"]["evento"]["prioridad"] = 1

    with pytest.raises(ValidacionError):
        construir_escenario_desde_topologia(datos)


def test_carga_por_topologia_rechaza_altura_almacenada_incorrecta():
    escenario = _escenario_con_datos()
    datos = exportar_escenario(escenario)
    datos["arbol_activo"]["altura"] = 99

    with pytest.raises(ValidacionError):
        construir_escenario_desde_topologia(datos)


def test_carga_por_topologia_rechaza_identificador_duplicado():
    escenario = _escenario_con_datos()
    datos = exportar_escenario(escenario)
    # duplicate the root's identifier inside its own child
    nodo_raiz = datos["arbol_activo"]
    hijo = nodo_raiz["izquierdo"] or nodo_raiz["derecho"]
    if hijo is not None:
        hijo["evento"]["identificador"] = nodo_raiz["evento"]["identificador"]
        with pytest.raises(ValidacionError):
            construir_escenario_desde_topologia(datos)


def test_carga_por_topologia_rechaza_desbalance_en_modo_normal():
    """
    An ordered but unbalanced topology can only be loaded with
    stress mode enabled (Section 12).
    """
    # manual chain of 3 nodes, deliberately unbalanced (without using
    # the AVL to build it, since it ALWAYS balances)
    zonas_json = []
    evento_a = {
        "identificador": 1, "magnitud": 1.0, "profundidad": 10.0,
        "epicentro_x": 500.0, "epicentro_y": 500.0,
        "fecha_hora": "2026-09-10T09:00:00Z", "revision": 1,
        "estaciones": ["EST-01"], "estado_atencion": "pendiente", "prioridad": 1,
    }
    evento_b = dict(evento_a, identificador=2)
    evento_c = dict(evento_a, identificador=3)

    nodo_c = {"evento": evento_c, "altura": 0, "factor_balance": 0, "izquierdo": None, "derecho": None}
    nodo_b = {"evento": evento_b, "altura": 1, "factor_balance": -1, "izquierdo": None, "derecho": nodo_c}
    nodo_a = {"evento": evento_a, "altura": 2, "factor_balance": -2, "izquierdo": None, "derecho": nodo_b}

    datos = {
        "zonas": zonas_json,
        "reloj_simulacion": "2026-09-10T12:00:00Z",
        "modo": "normal",
        "parametros": {"w_horas": 48.0, "r_km": 40.0, "t_horas": 72.0},
        "metricas": {},
        "arbol_activo": nodo_a,
        "historico": {"archivados": [], "eliminados": []},
        "cola": [],
    }

    with pytest.raises(ValidacionError):
        construir_escenario_desde_topologia(datos)

    datos["modo"] = "estres"
    reconstruido = construir_escenario_desde_topologia(datos)  # now it is accepted
    assert len(reconstruido.catalogo) == 3
    assert reconstruido.catalogo.esta_balanceado() is False


def test_carga_por_topologia_rechaza_orden_bst_roto():
    zonas_json = []
    evento_a = {
        "identificador": 1, "magnitud": 1.0, "profundidad": 10.0,
        "epicentro_x": 500.0, "epicentro_y": 500.0,
        "fecha_hora": "2026-09-10T09:00:00Z", "revision": 1,
        "estaciones": ["EST-01"], "estado_atencion": "pendiente", "prioridad": 1,
    }
    # magnitude 9.0 -> priority 3, placed as the LEFT child of a node
# with priority 1: violates BST ordering (left should be smaller)
    evento_b = dict(evento_a, identificador=2, magnitud=9.0, prioridad=3)

    nodo_b = {"evento": evento_b, "altura": 0, "factor_balance": 0, "izquierdo": None, "derecho": None}
    nodo_a = {"evento": evento_a, "altura": 1, "factor_balance": 1, "izquierdo": nodo_b, "derecho": None}

    datos = {
        "zonas": zonas_json,
        "reloj_simulacion": "2026-09-10T12:00:00Z",
        "modo": "normal",
        "parametros": {"w_horas": 48.0, "r_km": 40.0, "t_horas": 72.0},
        "metricas": {},
        "arbol_activo": nodo_a,
        "historico": {"archivados": [], "eliminados": []},
        "cola": [],
    }

    with pytest.raises(ValidacionError):
        construir_escenario_desde_topologia(datos)


def test_carga_por_topologia_rechaza_identificador_duplicado_en_activo_e_historico():
    escenario = _escenario_con_datos()
    datos = exportar_escenario(escenario)
    # put in "archived" an event with the same ID as the active root
    datos["historico"]["archivados"] = [dict(datos["arbol_activo"]["evento"])]

    with pytest.raises(ValidacionError):
        construir_escenario_desde_topologia(datos)


def test_escenario_cargar_por_topologia_conserva_el_anterior_si_falla():
    escenario = _escenario_con_datos()
    datos_validos = exportar_escenario(escenario)

    otro = _escenario_con_datos()
    otro.alta_evento(999, 6.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-03")
    cantidad_antes = len(otro.catalogo)

    datos_corruptos = dict(datos_validos)
    datos_corruptos["arbol_activo"] = dict(datos_validos["arbol_activo"])
    datos_corruptos["arbol_activo"]["altura"] = 999  # invalid

    with pytest.raises(ValidacionError):
        otro.cargar_por_topologia(datos_corruptos)

    assert len(otro.catalogo) == cantidad_antes  # nothing was touched
    assert otro.catalogo.esta_activo(999)


def test_escenario_cargar_por_topologia_reemplaza_y_es_deshacible():
    escenario = _escenario_con_datos()
    escenario.alta_evento(999, 6.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-03")
    cantidad_original = len(escenario.catalogo)

    otro = _escenario_con_datos()  # 3 events, distinct identifiers
    datos_otro = exportar_escenario(otro)

    escenario.cargar_por_topologia(datos_otro)
    assert len(escenario.catalogo) == 3
    assert not escenario.catalogo.esta_activo(999)

    escenario.deshacer()
    assert len(escenario.catalogo) == cantidad_original
    assert escenario.catalogo.esta_activo(999)


# ---------------- insertion loading: AVL vs BST comparison ----------------

def test_carga_por_inserciones_compara_avl_balanceado_contra_bst_degenerado():
    zonas = _zonas_ejemplo()
    eventos_json = [
        {
            "identificador": i, "magnitud": 5.0, "profundidad": 10.0,
            "epicentro_x": 500.0, "epicentro_y": 500.0,
            "fecha_hora": "2026-09-10T09:00:00Z", "revision": 1,
            "estaciones": ["EST-01"], "estado_atencion": "pendiente", "prioridad": 3,
        }
        for i in range(1, 16)  # ascending -> BST degenerates
    ]

    avl, bst, resumen = construir_arboles_por_insercion(eventos_json, zonas)

    assert resumen["bst"]["altura"] == 14      # pure chain
    assert resumen["avl"]["altura"] < 5        # log2(15) ~ 3.9
    assert resumen["avl"]["cantidad"] == resumen["bst"]["cantidad"] == 15
    assert avl.esta_balanceado() is True


def test_carga_por_inserciones_rechaza_identificador_duplicado():
    zonas = _zonas_ejemplo()
    eventos_json = [
        {"identificador": 1, "magnitud": 5.0, "profundidad": 10.0,
         "epicentro_x": 500.0, "epicentro_y": 500.0,
         "fecha_hora": "2026-09-10T09:00:00Z", "revision": 1,
         "estaciones": ["EST-01"], "estado_atencion": "pendiente", "prioridad": 2},
        {"identificador": 1, "magnitud": 6.0, "profundidad": 10.0,  # repeated ID
         "epicentro_x": 500.0, "epicentro_y": 500.0,
         "fecha_hora": "2026-09-10T09:00:00Z", "revision": 1,
         "estaciones": ["EST-01"], "estado_atencion": "pendiente", "prioridad": 3},
    ]
    with pytest.raises(ValidacionError):
        construir_arboles_por_insercion(eventos_json, zonas)


def test_escenario_cargar_por_inserciones_reemplaza_solo_el_catalogo():
    escenario = _escenario_con_datos()
    escenario.cola.encolar(__import__("core").Reporte(
        1, 5.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), 1, "EST-01"
    ))

    eventos_json = [
        {"identificador": 500, "magnitud": 6.0, "profundidad": 10.0,
         "epicentro_x": 500.0, "epicentro_y": 500.0,
         "fecha_hora": "2026-09-10T09:00:00Z", "revision": 1,
         "estaciones": ["EST-09"], "estado_atencion": "pendiente", "prioridad": 3},
    ]

    resumen, bst = escenario.cargar_por_inserciones({"eventos": eventos_json})

    assert len(escenario.catalogo) == 1
    assert escenario.catalogo.esta_activo(500)
    assert not escenario.catalogo.esta_activo(100)  # the previous catalog was replaced
    assert len(escenario.cola) == 1                  # the queue is NOT touched by this load
    assert resumen["avl"]["cantidad"] == 1


# ---------------- actual file reading/writing ----------------

def test_guardar_y_leer_json_en_disco(tmp_path):
    escenario = _escenario_con_datos()
    ruta = tmp_path / "escenario_prueba.json"

    escenario.guardar_json(str(ruta))
    assert ruta.exists()

    datos = leer_json(str(ruta))
    reconstruido = construir_escenario_desde_topologia(datos)
    assert len(reconstruido.catalogo) == len(escenario.catalogo)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])