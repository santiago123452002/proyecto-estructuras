"""
Minimum mandatory cases from section 16 of the statement, as ONE
reproducible demonstration file. Each case declares its initial state
and checks the expected result against the obtained one, using Escenario
end to end (not only Catalogo on its own), so it can also serve as a
script for the video tutorial.

The 4 isolated rotation cases (LL/RR/LR/RL) are already covered in
tests/test_arboles.py; here case 4 focuses on the part that file does
not cover: a real burst in stress mode with height differences greater
than 2, and its recovery while keeping identities, order, and
associations.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
import pytest

from core import Zona, Escenario, Catalogo, Reporte, ValidacionError
from core.persistencia import exportar_escenario, construir_escenario_desde_topologia


RELOJ = datetime(2026, 9, 10, 12, 0, 0)


def _zonas_ejemplo():
    return [
        Zona("Ciudad Central", 400.0, 600.0, 400.0, 600.0, poblada=True),
        Zona("Zona Rural", 0.0, 400.0, 0.0, 400.0, poblada=False),
    ]


def _escenario():
    return Escenario(zonas=_zonas_ejemplo(), reloj_simulacion=RELOJ)


# ==================================================================
# Case 1 — Boundaries and ties
# ==================================================================

def test_caso_1_limites_y_empates():
    """
    M = 4.5, M = 6.0, H = 30.0 km, epicenter on the edge of a zone;
    events with equal priority and magnitude to show the tie-break
    by identifier.
    """
    escenario = _escenario()
    fecha = datetime(2026, 9, 10, 9, 0, 0)

    # M=4.5, H=30.0, epicenter EXACTLY on the edge of "Ciudad
    # Central" (x=600.0) -> it belongs to the zone (inclusive bounds) and
    # produces priority 3 (also an inclusive bound, section 4).
    evento_borde = escenario.alta_evento(1, 4.5, 30.0, 600.0, 500.0, fecha, "EST-01")
    assert evento_borde.en_zona_poblada is True
    assert evento_borde.prioridad == 3

    # M=6.0 alone, anywhere -> high priority with no extra conditions
    evento_m6 = escenario.alta_evento(2, 6.0, 700.0, 10.0, 10.0, fecha, "EST-01")
    assert evento_m6.prioridad == 3

    # Tie on priority AND magnitude (both M=5.0, outside a populated zone
    # -> priority 2): the tie-break must be by identifier.
    escenario.alta_evento(3, 5.0, 10.0, 10.0, 10.0, fecha, "EST-01")
    escenario.alta_evento(4, 5.0, 10.0, 10.0, 10.0, fecha, "EST-01")
    evento_3, _ = escenario.catalogo.consultar_evento(3)
    evento_4, _ = escenario.catalogo.consultar_evento(4)
    assert evento_3.clave[:2] == evento_4.clave[:2]  # empatan P y M
    assert evento_3.clave < evento_4.clave            # the smaller id is "smaller" in the tree


# ==================================================================
# Case 2 — Correction and old report
# ==================================================================

def test_caso_2_correccion_y_reporte_antiguo():
    """
    Correct an event from M=4.8/H=70.0 km to M=6.2/H=15.0 km (priority
    2 -> 3). Then receive a LOWER revision and show that no other node
    is created and the correction is not reverted.
    """
    escenario = _escenario()
    fecha = datetime(2026, 9, 10, 9, 0, 0)

    escenario.alta_evento(10, 4.8, 70.0, 500.0, 500.0, fecha, "EST-01")
    evento_inicial, _ = escenario.catalogo.consultar_evento(10)
    assert evento_inicial.prioridad == 2

    escenario.corregir_evento(10, magnitud=6.2, profundidad=15.0)
    evento_corregido, _ = escenario.catalogo.consultar_evento(10)
    assert evento_corregido.prioridad == 3
    assert evento_corregido.revision == 2
    assert len(escenario.catalogo) == 1

    # revision 1 < current revision (2): old report, it is discarded
    escenario.cola.encolar(Reporte(10, 9.0, 5.0, 500.0, 500.0, fecha, 1, "EST-02"))
    _, resultado = escenario.procesar_siguiente_reporte()
    assert resultado.tipo.value == "antiguo"

    evento_final, _ = escenario.catalogo.consultar_evento(10)
    assert evento_final.magnitud == 6.2   # the correction was NOT reverted
    assert evento_final.revision == 2
    assert len(escenario.catalogo) == 1    # a second node was not created


# ==================================================================
# Case 3 — Late report
# ==================================================================

def test_caso_3_reporte_tardio():
    """
    Nearby events of M=5.6 at 10:00 and M=4.2 at 10:20. Then one of
    M=6.1 arrives, which occurred at 09:55 (before the other two, but
    received afterwards). The new candidates and the result of the
    selection policy are shown.
    """
    escenario = _escenario()

    escenario.cola.encolar(Reporte(20, 5.6, 10.0, 500.0, 500.0,
                                    datetime(2026, 9, 10, 10, 0, 0), 1, "EST-01"))
    escenario.cola.encolar(Reporte(21, 4.2, 10.0, 500.0, 500.0,
                                    datetime(2026, 9, 10, 10, 20, 0), 1, "EST-01"))
    escenario.procesar_siguiente_reporte()
    escenario.procesar_siguiente_reporte()

    # it occurred at 09:55 (before the previous two) but is received last
    escenario.cola.encolar(Reporte(22, 6.1, 10.0, 500.0, 500.0,
                                    datetime(2026, 9, 10, 9, 55, 0), 1, "EST-02"))
    reporte, resultado = escenario.procesar_siguiente_reporte()
    assert resultado.tipo.value == "alta_nueva"  # it is registered anyway, even though it arrived "late"
    assert len(escenario.catalogo) == 3

    info_20 = escenario.catalogo.consultar_asociaciones(20)
    info_21 = escenario.catalogo.consultar_asociaciones(21)

    candidatos_20 = {c["identificador"] for c in info_20["candidatos"]}
    candidatos_21 = {c["identificador"] for c in info_21["candidatos"]}
    assert 22 in candidatos_20   # M=6.1 > M=5.6, it occurred earlier, within the default W/R
    assert 22 in candidatos_21   # M=6.1 > M=4.2, it occurred earlier
    assert 20 in candidatos_21   # M=5.6 > M=4.2, it occurred earlier

    # selection policy (higher magnitude first): 22 beats 20 for event 21
    assert info_21["referencia"]["identificador"] == 22
    assert info_20["referencia"]["identificador"] == 22


# ==================================================================
# Case 4 — Rotations and recovery
# ==================================================================

def test_caso_4_rotaciones_y_recuperacion():
    """
    Builds a degraded structure in stress mode (height difference much
    greater than 2), repairs it with recuperar_equilibrio, and shows
    that it keeps identities, order, and associations. The 4 isolated
    balancing cases (LL/RR/LR/RL) are in test_arboles.py.
    """
    escenario = _escenario()
    escenario.cambiar_modo("estres")
    fecha = datetime(2026, 9, 10, 9, 0, 0)

    for i in range(1, 21):  # ascending, same priority/magnitude -> degenerates into a chain
        escenario.cola.encolar(Reporte(i, 5.0, 10.0, 500.0, 500.0, fecha, 1, "EST-01"))
        escenario.procesar_siguiente_reporte()

    assert escenario.catalogo.esta_balanceado() is False
    altura_degradada = escenario.catalogo.avl.altura_total()
    assert altura_degradada > 4  # well above log2(20) ~ 4.3: imbalance >> 2

    ids_antes = sorted(e.identificador for e in escenario.catalogo.avl.recorrido_inorden())
    asociaciones_antes = dict(escenario.catalogo._asociaciones)

    escenario.recuperar_equilibrio()

    assert escenario.catalogo.esta_balanceado() is True
    ids_despues = sorted(e.identificador for e in escenario.catalogo.avl.recorrido_inorden())
    assert ids_antes == ids_despues                          # mismas identidades
    assert len(escenario.catalogo) == 20                     # nothing was lost
    assert escenario.catalogo._asociaciones == asociaciones_antes  # rotations do not touch associations

    # undo returns to the degraded structure (tested in depth in
    # test_deshacer_y_versiones.py; here it is only confirmed that it applies)
    escenario.deshacer()
    assert escenario.catalogo.esta_balanceado() is False
    assert escenario.catalogo.avl.altura_total() == altura_degradada


# ==================================================================
# Case 5 — Mass archive
# ==================================================================

def test_caso_5_archivo_masivo():
    """
    An eligible branch with several events and its tie-break criteria,
    and the situation with no eligible branches. Shows that a branch
    whose root is low priority is not eligible if it contains a
    higher-priority descendant. Undoes the whole archive.
    """
    escenario = _escenario()
    fecha_reciente = datetime(2026, 9, 10, 9, 0, 0)
    fecha_antigua = datetime(2026, 9, 1, 9, 0, 0)

    # Situation with NO eligible branches: the only event is too recent.
    escenario.alta_evento(30, 2.0, 10.0, 500.0, 500.0, fecha_reciente, "EST-01")
    archivados_vacio = escenario.archivar_rama_antigua()
    assert archivados_vacio == []
    assert len(escenario.catalogo) == 1  # nothing was modified

    # Old low-priority events (eligible) + one that is also old but
    # HIGH priority (never eligible, even if it is just as old).
    escenario.alta_evento(31, 1.0, 10.0, 10.0, 10.0, fecha_antigua, "EST-01")
    escenario.alta_evento(32, 1.5, 10.0, 10.0, 10.0, fecha_antigua, "EST-01")
    escenario.alta_evento(33, 9.0, 10.0, 10.0, 10.0, fecha_antigua, "EST-01")

    cantidad_antes = len(escenario.catalogo)
    archivados = escenario.archivar_rama_antigua()

    assert 33 not in archivados            # high priority: never eligible
    assert 30 not in archivados            # demasiado reciente
    assert set(archivados).issubset({31, 32})
    assert len(archivados) >= 1

    # undoing the whole archive restores ALL archived events at once
    escenario.deshacer()
    assert len(escenario.catalogo) == cantidad_antes
    for identificador in archivados:
        assert escenario.catalogo.esta_activo(identificador)
        assert not escenario.catalogo.esta_archivado(identificador)


# ==================================================================
# Case 6 — Persistence and consistency
# ==================================================================

def test_caso_6_persistencia_y_consistencia():
    """
    Saves and recovers a normal topology and one in stress mode. Rejects
    an inconsistent file without altering the current state. Restores a
    version "after restarting" and confirms that undo still works
    normally both for a correction and for a queue step.
    """
    fecha = datetime(2026, 9, 10, 9, 0, 0)

    # --- normal topology: save and recover ---
    escenario_normal = _escenario()
    for i in range(1, 6):
        escenario_normal.alta_evento(40 + i, 5.0, 10.0, 500.0, 500.0, fecha, "EST-01")
    datos_normal = exportar_escenario(escenario_normal)
    reconstruido_normal = construir_escenario_desde_topologia(datos_normal)
    assert len(reconstruido_normal.catalogo) == 5
    assert reconstruido_normal.modo == "normal"

    # --- stress-mode topology: save and recover ---
    escenario_estres = _escenario()
    escenario_estres.cambiar_modo("estres")
    for i in range(1, 6):
        escenario_estres.cola.encolar(Reporte(50 + i, 5.0, 10.0, 500.0, 500.0, fecha, 1, "EST-01"))
        escenario_estres.procesar_siguiente_reporte()
    assert escenario_estres.catalogo.esta_balanceado() is False
    datos_estres = exportar_escenario(escenario_estres)
    reconstruido_estres = construir_escenario_desde_topologia(datos_estres)
    assert reconstruido_estres.modo == "estres"
    assert reconstruido_estres.catalogo.esta_balanceado() is False

    # --- reject an inconsistent file without altering the current state ---
    datos_corruptos = dict(datos_normal)
    datos_corruptos["arbol_activo"] = dict(datos_normal["arbol_activo"])
    datos_corruptos["arbol_activo"]["altura"] = 999  # impossible data, on purpose
    cantidad_antes = len(escenario_normal.catalogo)
    with pytest.raises(ValidacionError):
        escenario_normal.cargar_por_topologia(datos_corruptos)
    assert len(escenario_normal.catalogo) == cantidad_antes  # the previous scenario was not touched

    # --- restore a version "after restarting" ---
    original = _escenario()
    original.alta_evento(60, 5.0, 10.0, 500.0, 500.0, fecha, "EST-01")
    original.guardar_version("punto-de-control")
    original.corregir_evento(60, magnitud=8.0)  # changes made after the save

    # simulates restarting the program: a new Escenario, with only the
    # "persisted" versions brought back
    reiniciado = Escenario(zonas=_zonas_ejemplo(), reloj_simulacion=RELOJ)
    reiniciado.versiones = original.versiones
    reiniciado.restaurar_version("punto-de-control")

    evento_60, _ = reiniciado.catalogo.consultar_evento(60)
    assert evento_60.magnitud == 5.0  # it returned to the saved state, not to "original" after the correction

    # after the restore, undo still works normally:
    # a new correction...
    reiniciado.corregir_evento(60, magnitud=7.0)
    reiniciado.deshacer()
    evento_tras_deshacer_correccion, _ = reiniciado.catalogo.consultar_evento(60)
    assert evento_tras_deshacer_correccion.magnitud == 5.0

    # ...and a queue step.
    reiniciado.cola.encolar(Reporte(61, 4.0, 10.0, 500.0, 500.0, fecha, 1, "EST-02"))
    reiniciado.procesar_siguiente_reporte()
    assert len(reiniciado.catalogo) == 2
    reiniciado.deshacer()
    assert len(reiniciado.catalogo) == 1
    assert len(reiniciado.cola) == 1  # the report discarded by the undo returns to the queue


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
