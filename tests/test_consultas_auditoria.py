"""
Pruebas de la Fase 8: las 4 consultas de la sección 11 (pendientes,
filtros, asociaciones, acceso costoso), la auditoría "Verificar
estructura" y los indicadores de la sección 14.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import pytest

from core import Zona, Escenario, ValidacionError


RELOJ = datetime(2026, 9, 10, 12, 0, 0)


def _zonas_ejemplo():
    return [
        Zona("Ciudad Central", 400.0, 600.0, 400.0, 600.0, poblada=True),
        Zona("Zona Rural", 0.0, 400.0, 0.0, 400.0, poblada=False),
    ]


def _escenario():
    return Escenario(zonas=_zonas_ejemplo(), reloj_simulacion=RELOJ)


# ---------------- consulta 1: pendientes_top_k ----------------

def test_pendientes_top_k_orden_descendente_y_excluye_revisados():
    escenario = _escenario()
    catalogo = escenario.catalogo
    for i, magnitud in enumerate([6.0, 4.8, 5.5, 6.5, 3.0], start=1):
        escenario.alta_evento(i, magnitud, 10.0, 500.0, 500.0,
                               datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.marcar_revisado(4)  # el de mayor clave queda fuera de "pendientes"

    resultado, visitados = catalogo.pendientes_top_k(2)

    claves = [e.clave for e in resultado]
    assert claves == sorted(claves, reverse=True)  # descendente
    assert all(e.estado_atencion == "pendiente" for e in resultado)
    assert 4 not in [e.identificador for e in resultado]
    assert visitados >= 2


def test_pendientes_top_k_devuelve_todos_si_hay_menos_que_k():
    escenario = _escenario()
    escenario.alta_evento(1, 5.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-01")

    resultado, _ = escenario.catalogo.pendientes_top_k(10)
    assert len(resultado) == 1


def test_pendientes_top_k_rechaza_k_invalido():
    escenario = _escenario()
    with pytest.raises(ValidacionError):
        escenario.catalogo.pendientes_top_k(0)
    with pytest.raises(ValidacionError):
        escenario.catalogo.pendientes_top_k(-3)


# ---------------- consulta 2: buscar_por_filtros ----------------

def test_buscar_por_filtros_combina_magnitud_profundidad_y_fecha():
    escenario = _escenario()
    escenario.alta_evento(1, 5.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 8, 0, 0), "EST-01")
    escenario.alta_evento(2, 7.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.alta_evento(3, 5.0, 200.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.alta_evento(4, 5.0, 10.0, 500.0, 500.0, datetime(2026, 9, 1, 9, 0, 0), "EST-01")

    resultado, visitados = escenario.catalogo.buscar_por_filtros(
        magnitud_min=4.0, magnitud_max=6.0,
        profundidad_max=50.0,
        fecha_inicio=datetime(2026, 9, 5, 0, 0, 0), fecha_fin=RELOJ,
    )
    identificadores = sorted(e.identificador for e in resultado)
    assert identificadores == [1]  # 2 tiene M=7 (fuera), 3 tiene H=200 (fuera), 4 es muy viejo
    assert visitados == 4  # recorrido completo, documentado en el código


def test_buscar_por_filtros_sin_restricciones_devuelve_todo():
    escenario = _escenario()
    for i in range(1, 4):
        escenario.alta_evento(i, 5.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    resultado, _ = escenario.catalogo.buscar_por_filtros()
    assert len(resultado) == 3


# ---------------- consulta 3: consultar_asociaciones ----------------

def test_consultar_asociaciones_indica_activo_o_archivado():
    escenario = _escenario()
    fecha_temprana = datetime(2026, 9, 10, 9, 0, 0)
    escenario.alta_evento(1, 6.5, 10.0, 500.0, 500.0, fecha_temprana, "EST-01")  # A: mayor magnitud, antes
    escenario.alta_evento(2, 5.0, 10.0, 500.0, 500.0, fecha_temprana + timedelta(hours=1), "EST-01")  # B

    info = escenario.catalogo.consultar_asociaciones(2)
    assert info["referencia"]["identificador"] == 1
    assert info["referencia"]["estado"] == "activo"
    assert any(c["identificador"] == 1 for c in info["candidatos"])

    info_de_a = escenario.catalogo.consultar_asociaciones(1)
    assert any(r["identificador"] == 2 for r in info_de_a["referenciado_por"])


def test_consultar_asociaciones_considera_archivados():
    escenario = _escenario()
    fecha_antigua = datetime(2026, 9, 1, 9, 0, 0)
    escenario.alta_evento(1, 2.0, 10.0, 500.0, 500.0, fecha_antigua, "EST-01")
    archivados = escenario.archivar_rama_antigua()
    assert 1 in archivados

    info = escenario.catalogo.consultar_asociaciones(1)  # no debe lanzar error
    assert info["candidatos"] == []


def test_consultar_asociaciones_identificador_inexistente():
    escenario = _escenario()
    with pytest.raises(ValidacionError):
        escenario.catalogo.consultar_asociaciones(999)


# ---------------- consulta 4: acceso costoso ----------------

def test_acceso_costoso_marca_prioridad_alta_mas_alla_del_limite():
    escenario = _escenario()
    escenario.configurar_l_profundidad(0)  # cualquier profundidad > 0 ya cuenta

    for i, magnitud in enumerate([9.0, 8.0, 7.0, 6.5, 6.1, 6.2, 6.3], start=1):
        escenario.alta_evento(i, magnitud, 5.0, 500.0, 500.0,
                               datetime(2026, 9, 10, 9, 0, 0), "EST-01")

    resultado, total_visitados = escenario.catalogo.eventos_prioridad_alta_con_acceso_costoso()
    assert len(resultado) > 0
    for entrada in resultado:
        assert entrada["profundidad"] > 0
        assert entrada["limite"] == 0
        assert entrada["nodos_visitados"] == entrada["profundidad"] + 1
    assert total_visitados > 0


def test_acceso_costoso_vacio_con_limite_alto():
    escenario = _escenario()
    escenario.configurar_l_profundidad(50)
    escenario.alta_evento(1, 9.0, 5.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-01")

    resultado, _ = escenario.catalogo.eventos_prioridad_alta_con_acceso_costoso()
    assert resultado == []


def test_configurar_l_profundidad_rechaza_negativos():
    escenario = _escenario()
    with pytest.raises(ValidacionError):
        escenario.configurar_l_profundidad(-1)


# ---------------- auditoría: verificar_estructura ----------------

def test_verificar_estructura_arbol_sano_no_tiene_errores():
    escenario = _escenario()
    for i in range(1, 11):
        escenario.alta_evento(i, 5.0, 10.0, 500.0, 500.0,
                               datetime(2026, 9, 10, 9, 0, 0), "EST-01")

    reporte = escenario.catalogo.verificar_estructura(modo="normal")
    assert reporte["ok"] is True
    assert reporte["errores"] == []


def test_verificar_estructura_en_modo_estres_reporta_desbalance_esperado_no_error():
    escenario = _escenario()
    escenario.cambiar_modo("estres")
    for i in range(1, 16):
        escenario.cola.encolar(__import__("core").Reporte(
            i, 5.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), 1, "EST-01"
        ))
        escenario.procesar_siguiente_reporte()

    reporte_normal = escenario.catalogo.verificar_estructura(modo="estres")
    assert reporte_normal["ok"] is True  # nada de esto son "errores" en modo estrés
    assert len(reporte_normal["desbalances_esperados"]) > 0

    reporte_como_normal = escenario.catalogo.verificar_estructura(modo="normal")
    assert reporte_como_normal["ok"] is False  # el mismo árbol, evaluado como si debiera estar balanceado


def test_verificar_estructura_detecta_asociacion_rota_manualmente():
    escenario = _escenario()
    escenario.alta_evento(1, 5.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.catalogo._asociaciones[1] = 999  # referencia a un id inexistente, a mano

    reporte = escenario.catalogo.verificar_estructura()
    assert reporte["ok"] is False
    assert any("999" in error for error in reporte["errores"])


# ---------------- indicadores (sección 14) ----------------

def test_generar_indicadores_refleja_conteos_correctos():
    escenario = _escenario()
    escenario.alta_evento(1, 6.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.alta_evento(2, 4.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.corregir_evento(1, magnitud=6.5)
    escenario.marcar_revisado(2)

    indicadores = escenario.generar_indicadores()

    assert indicadores["eventos_activos"] == 2
    assert indicadores["correcciones_aceptadas"] == 1
    assert indicadores["eventos_por_prioridad"][3] == 1  # evento 1: M=6.5
    assert indicadores["eventos_por_prioridad"][1] == 1  # evento 2: M=4.0
    assert indicadores["pendientes_de_atencion"] == 1    # el 2 quedó revisado
    assert set(indicadores["recorrido_inorden"]) == {1, 2}
    assert set(indicadores["recorrido_por_niveles"]) == {1, 2}


def test_generar_indicadores_cuenta_archivos_y_eliminaciones():
    escenario = _escenario()
    fecha_antigua = datetime(2026, 9, 1, 9, 0, 0)
    escenario.alta_evento(1, 2.0, 10.0, 500.0, 500.0, fecha_antigua, "EST-01")
    escenario.archivar_rama_antigua()  # evento 1 es el único nodo: se archiva solo

    escenario.alta_evento(2, 5.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.eliminar_evento(2)

    indicadores = escenario.generar_indicadores()
    assert indicadores["archivos_masivos"] == 1
    assert indicadores["eventos_archivados_total"] == 1
    assert indicadores["eliminaciones"] == 1
    assert indicadores["eventos_activos"] == 0
    assert indicadores["eventos_historicos"] == 2


def test_generar_indicadores_cuenta_reportes_por_tipo():
    escenario = _escenario()
    escenario.alta_evento(1, 5.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.corregir_evento(1, magnitud=5.5)  # revisión -> 2

    from core import Reporte
    escenario.cola.encolar(Reporte(1, 9.0, 10.0, 500.0, 500.0,
                                    datetime(2026, 9, 10, 9, 0, 0), 1, "EST-02"))  # antiguo
    escenario.procesar_siguiente_reporte()
    escenario.cola.encolar(Reporte(1, 9.0, 10.0, 500.0, 500.0,
                                    datetime(2026, 9, 10, 9, 0, 0), 2, "EST-02"))  # conflicto (misma rev, otros datos)
    escenario.procesar_siguiente_reporte()

    indicadores = escenario.generar_indicadores()
    assert indicadores["reportes_descartados"] == 1
    assert indicadores["conflictos"] == 1


def test_metricas_se_deshacen_junto_con_la_accion():
    """
    Los contadores viven dentro de Catalogo, así que quedan incluidos en
    cada snapshot de Escenario -- deshacer una acción también revierte
    su efecto sobre los indicadores.
    """
    escenario = _escenario()
    escenario.alta_evento(1, 5.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    assert escenario.catalogo.metricas["altas_nuevas"] == 1

    escenario.corregir_evento(1, magnitud=6.0)
    assert escenario.catalogo.metricas["correcciones_aceptadas"] == 1

    escenario.deshacer()  # deshace la corrección
    assert escenario.catalogo.metricas["correcciones_aceptadas"] == 0

    escenario.deshacer()  # deshace la alta
    assert escenario.catalogo.metricas["altas_nuevas"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])