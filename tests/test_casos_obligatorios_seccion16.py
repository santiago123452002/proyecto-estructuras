"""
Casos mínimos obligatorios de la sección 16 del enunciado, como UN solo
archivo de demostración reproducible. Cada caso declara su estado
inicial y verifica el resultado esperado contra el obtenido, usando
Escenario de punta a punta (no solo Catalogo por separado), para que
sirva también como guion para el videotutorial.

Los 4 casos de rotación (LL/RR/LR/RL) aislados ya están cubiertos en
tests/test_arboles.py; aquí el caso 4 se enfoca en la parte que ese
archivo no cubre: una ráfaga real en modo estrés con diferencias de
altura mayores que 2, y su recuperación conservando identidades, orden
y asociaciones.
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
# Caso 1 — Límites y empates
# ==================================================================

def test_caso_1_limites_y_empates():
    """
    M = 4,5, M = 6,0, H = 30,0 km, epicentro sobre el borde de una zona;
    eventos con igual prioridad y magnitud para evidenciar el desempate
    por identificador.
    """
    escenario = _escenario()
    fecha = datetime(2026, 9, 10, 9, 0, 0)

    # M=4.5, H=30.0, epicentro EXACTAMENTE sobre el borde de "Ciudad
    # Central" (x=600.0) -> pertenece a la zona (límites inclusivos) y
    # produce prioridad 3 (también límite inclusivo, sección 4).
    evento_borde = escenario.alta_evento(1, 4.5, 30.0, 600.0, 500.0, fecha, "EST-01")
    assert evento_borde.en_zona_poblada is True
    assert evento_borde.prioridad == 3

    # M=6.0 solo, en cualquier lugar -> prioridad alta sin condiciones extra
    evento_m6 = escenario.alta_evento(2, 6.0, 700.0, 10.0, 10.0, fecha, "EST-01")
    assert evento_m6.prioridad == 3

    # Empate de prioridad Y magnitud (ambos M=5.0, fuera de zona poblada
    # -> prioridad 2): el desempate debe ser por identificador.
    escenario.alta_evento(3, 5.0, 10.0, 10.0, 10.0, fecha, "EST-01")
    escenario.alta_evento(4, 5.0, 10.0, 10.0, 10.0, fecha, "EST-01")
    evento_3, _ = escenario.catalogo.consultar_evento(3)
    evento_4, _ = escenario.catalogo.consultar_evento(4)
    assert evento_3.clave[:2] == evento_4.clave[:2]  # empatan P y M
    assert evento_3.clave < evento_4.clave            # el de menor id es "menor" en el árbol


# ==================================================================
# Caso 2 — Corrección y reporte antiguo
# ==================================================================

def test_caso_2_correccion_y_reporte_antiguo():
    """
    Corregir un evento de M=4,8/H=70,0 km a M=6,2/H=15,0 km (prioridad
    2 -> 3). Luego recibir una revisión MENOR y demostrar que no se crea
    otro nodo ni se revierte la corrección.
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

    # revisión 1 < revisión vigente (2): reporte antiguo, se descarta
    escenario.cola.encolar(Reporte(10, 9.0, 5.0, 500.0, 500.0, fecha, 1, "EST-02"))
    _, resultado = escenario.procesar_siguiente_reporte()
    assert resultado.tipo.value == "antiguo"

    evento_final, _ = escenario.catalogo.consultar_evento(10)
    assert evento_final.magnitud == 6.2   # la corrección NO se revirtió
    assert evento_final.revision == 2
    assert len(escenario.catalogo) == 1    # no se creó un segundo nodo


# ==================================================================
# Caso 3 — Reporte tardío
# ==================================================================

def test_caso_3_reporte_tardio():
    """
    Eventos cercanos de M=5,6 a las 10:00 y M=4,2 a las 10:20. Luego
    llega uno de M=6,1 ocurrido a las 09:55 (antes que los otros dos,
    pero recibido después). Se muestran los candidatos nuevos y el
    resultado de la política de selección.
    """
    escenario = _escenario()

    escenario.cola.encolar(Reporte(20, 5.6, 10.0, 500.0, 500.0,
                                    datetime(2026, 9, 10, 10, 0, 0), 1, "EST-01"))
    escenario.cola.encolar(Reporte(21, 4.2, 10.0, 500.0, 500.0,
                                    datetime(2026, 9, 10, 10, 20, 0), 1, "EST-01"))
    escenario.procesar_siguiente_reporte()
    escenario.procesar_siguiente_reporte()

    # ocurrió a las 09:55 (antes que los dos anteriores) pero se recibe al final
    escenario.cola.encolar(Reporte(22, 6.1, 10.0, 500.0, 500.0,
                                    datetime(2026, 9, 10, 9, 55, 0), 1, "EST-02"))
    reporte, resultado = escenario.procesar_siguiente_reporte()
    assert resultado.tipo.value == "alta_nueva"  # se registra igual, aunque llegó "tarde"
    assert len(escenario.catalogo) == 3

    info_20 = escenario.catalogo.consultar_asociaciones(20)
    info_21 = escenario.catalogo.consultar_asociaciones(21)

    candidatos_20 = {c["identificador"] for c in info_20["candidatos"]}
    candidatos_21 = {c["identificador"] for c in info_21["candidatos"]}
    assert 22 in candidatos_20   # M=6.1 > M=5.6, ocurrió antes, dentro de W/R por defecto
    assert 22 in candidatos_21   # M=6.1 > M=4.2, ocurrió antes
    assert 20 in candidatos_21   # M=5.6 > M=4.2, ocurrió antes

    # política de selección (mayor magnitud primero): 22 gana sobre 20 para el evento 21
    assert info_21["referencia"]["identificador"] == 22
    assert info_20["referencia"]["identificador"] == 22


# ==================================================================
# Caso 4 — Rotaciones y recuperación
# ==================================================================

def test_caso_4_rotaciones_y_recuperacion():
    """
    Genera una estructura degradada en modo estrés (diferencia de altura
    mucho mayor que 2), la repara con recuperar_equilibrio, y demuestra
    que conserva identidades, orden y asociaciones. Los 4 casos de
    balanceo (LL/RR/LR/RL) aislados están en test_arboles.py.
    """
    escenario = _escenario()
    escenario.cambiar_modo("estres")
    fecha = datetime(2026, 9, 10, 9, 0, 0)

    for i in range(1, 21):  # ascendente, misma prioridad/magnitud -> degenera en cadena
        escenario.cola.encolar(Reporte(i, 5.0, 10.0, 500.0, 500.0, fecha, 1, "EST-01"))
        escenario.procesar_siguiente_reporte()

    assert escenario.catalogo.esta_balanceado() is False
    altura_degradada = escenario.catalogo.avl.altura_total()
    assert altura_degradada > 4  # muy por encima de log2(20) ~ 4.3: desbalance >> 2

    ids_antes = sorted(e.identificador for e in escenario.catalogo.avl.recorrido_inorden())
    asociaciones_antes = dict(escenario.catalogo._asociaciones)

    escenario.recuperar_equilibrio()

    assert escenario.catalogo.esta_balanceado() is True
    ids_despues = sorted(e.identificador for e in escenario.catalogo.avl.recorrido_inorden())
    assert ids_antes == ids_despues                          # mismas identidades
    assert len(escenario.catalogo) == 20                     # nada se perdió
    assert escenario.catalogo._asociaciones == asociaciones_antes  # las rotaciones no tocan asociaciones

    # deshacer regresa a la estructura degradada (probado a fondo en
    # test_deshacer_y_versiones.py; aquí solo se confirma que aplica)
    escenario.deshacer()
    assert escenario.catalogo.esta_balanceado() is False
    assert escenario.catalogo.avl.altura_total() == altura_degradada


# ==================================================================
# Caso 5 — Archivo masivo
# ==================================================================

def test_caso_5_archivo_masivo():
    """
    Rama elegible con varios eventos y sus criterios de desempate, y la
    situación sin ramas elegibles. Evidencia que una rama cuya raíz sea
    de baja prioridad no es elegible si contiene un descendiente de
    prioridad mayor. Deshace el archivo completo.
    """
    escenario = _escenario()
    fecha_reciente = datetime(2026, 9, 10, 9, 0, 0)
    fecha_antigua = datetime(2026, 9, 1, 9, 0, 0)

    # Situación SIN ramas elegibles: el único evento es demasiado reciente.
    escenario.alta_evento(30, 2.0, 10.0, 500.0, 500.0, fecha_reciente, "EST-01")
    archivados_vacio = escenario.archivar_rama_antigua()
    assert archivados_vacio == []
    assert len(escenario.catalogo) == 1  # no se modificó nada

    # Eventos antiguos de prioridad baja (elegibles) + uno antiguo pero
    # de prioridad ALTA (nunca elegible, aunque sea igual de antiguo).
    escenario.alta_evento(31, 1.0, 10.0, 10.0, 10.0, fecha_antigua, "EST-01")
    escenario.alta_evento(32, 1.5, 10.0, 10.0, 10.0, fecha_antigua, "EST-01")
    escenario.alta_evento(33, 9.0, 10.0, 10.0, 10.0, fecha_antigua, "EST-01")

    cantidad_antes = len(escenario.catalogo)
    archivados = escenario.archivar_rama_antigua()

    assert 33 not in archivados            # prioridad alta: nunca elegible
    assert 30 not in archivados            # demasiado reciente
    assert set(archivados).issubset({31, 32})
    assert len(archivados) >= 1

    # deshacer el archivo completo restaura TODOS los eventos archivados a la vez
    escenario.deshacer()
    assert len(escenario.catalogo) == cantidad_antes
    for identificador in archivados:
        assert escenario.catalogo.esta_activo(identificador)
        assert not escenario.catalogo.esta_archivado(identificador)


# ==================================================================
# Caso 6 — Persistencia y consistencia
# ==================================================================

def test_caso_6_persistencia_y_consistencia():
    """
    Guarda y recupera una topología normal y otra en estrés. Rechaza un
    archivo inconsistente sin alterar el estado actual. Restaura una
    versión "después de reiniciar" y confirma que deshacer sigue
    funcionando con normalidad tanto para una corrección como para un
    paso de cola.
    """
    fecha = datetime(2026, 9, 10, 9, 0, 0)

    # --- topología normal: guardar y recuperar ---
    escenario_normal = _escenario()
    for i in range(1, 6):
        escenario_normal.alta_evento(40 + i, 5.0, 10.0, 500.0, 500.0, fecha, "EST-01")
    datos_normal = exportar_escenario(escenario_normal)
    reconstruido_normal = construir_escenario_desde_topologia(datos_normal)
    assert len(reconstruido_normal.catalogo) == 5
    assert reconstruido_normal.modo == "normal"

    # --- topología en modo estrés: guardar y recuperar ---
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

    # --- rechazar un archivo inconsistente sin alterar el estado actual ---
    datos_corruptos = dict(datos_normal)
    datos_corruptos["arbol_activo"] = dict(datos_normal["arbol_activo"])
    datos_corruptos["arbol_activo"]["altura"] = 999  # dato imposible, a propósito
    cantidad_antes = len(escenario_normal.catalogo)
    with pytest.raises(ValidacionError):
        escenario_normal.cargar_por_topologia(datos_corruptos)
    assert len(escenario_normal.catalogo) == cantidad_antes  # el escenario anterior no se tocó

    # --- restaurar una versión "después de reiniciar" ---
    original = _escenario()
    original.alta_evento(60, 5.0, 10.0, 500.0, 500.0, fecha, "EST-01")
    original.guardar_version("punto-de-control")
    original.corregir_evento(60, magnitud=8.0)  # cambios posteriores al guardado

    # simula reiniciar el programa: un Escenario nuevo, con solo las
    # versiones "persistidas" traídas de vuelta
    reiniciado = Escenario(zonas=_zonas_ejemplo(), reloj_simulacion=RELOJ)
    reiniciado.versiones = original.versiones
    reiniciado.restaurar_version("punto-de-control")

    evento_60, _ = reiniciado.catalogo.consultar_evento(60)
    assert evento_60.magnitud == 5.0  # volvió al estado guardado, no al de "original" tras la corrección

    # tras la restauración, deshacer sigue funcionando con normalidad:
    # una corrección nueva...
    reiniciado.corregir_evento(60, magnitud=7.0)
    reiniciado.deshacer()
    evento_tras_deshacer_correccion, _ = reiniciado.catalogo.consultar_evento(60)
    assert evento_tras_deshacer_correccion.magnitud == 5.0

    # ...y un paso de cola.
    reiniciado.cola.encolar(Reporte(61, 4.0, 10.0, 500.0, 500.0, fecha, 1, "EST-02"))
    reiniciado.procesar_siguiente_reporte()
    assert len(reiniciado.catalogo) == 2
    reiniciado.deshacer()
    assert len(reiniciado.catalogo) == 1
    assert len(reiniciado.cola) == 1  # el reporte descartado del deshacer vuelve a la cola


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
