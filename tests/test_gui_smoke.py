"""
Prueba de humo de la Fase 9 (GUI): confirma que la ventana principal y
sus widgets se construyen sin errores y que refrescar() no revienta,
usando una plataforma Qt "offscreen" (sin necesidad de pantalla).

Se salta automáticamente si PySide6 no está instalado, para no romper
el resto de la suite en un entorno donde solo se corre `core/`.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

PySide6 = pytest.importorskip("PySide6")

from datetime import datetime

from core import Zona, Escenario


RELOJ = datetime(2026, 9, 10, 12, 0, 0)


@pytest.fixture(scope="module")
def app():
    from PySide6 import QtWidgets
    aplicacion = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield aplicacion


@pytest.fixture(autouse=True)
def _sin_dialogos_modales_bloqueantes(monkeypatch):
    """
    QMessageBox.information/warning/question son diálogos MODALES: su
    exec() se queda esperando un clic real. En un entorno sin pantalla
    (como esta suite, con QT_QPA_PLATFORM=offscreen) eso cuelga la
    prueba para siempre. Se reemplazan por versiones que no bloquean,
    ya que lo que se está probando aquí es la lógica que decide mostrar
    el diálogo, no el diálogo en sí.
    """
    from PySide6 import QtWidgets
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QtWidgets.QMessageBox, "question",
                         staticmethod(lambda *a, **k: QtWidgets.QMessageBox.Yes))

def _escenario_con_datos():
    zonas = [Zona("Ciudad Central", 400.0, 600.0, 400.0, 600.0, poblada=True)]
    escenario = Escenario(zonas=zonas, reloj_simulacion=RELOJ)
    escenario.alta_evento(1, 6.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    escenario.alta_evento(2, 4.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    return escenario


def test_panel_eventos_construye_y_refresca(app):
    from gui.panel_eventos import PanelEventos

    escenario = _escenario_con_datos()
    panel = PanelEventos(escenario)

    assert panel.tabla.rowCount() == 2
    panel.refrescar()
    assert panel.tabla.rowCount() == 2


def test_seleccionar_fila_actualiza_el_detalle(app):
    from gui.panel_eventos import PanelEventos

    escenario = _escenario_con_datos()
    panel = PanelEventos(escenario)

    panel.tabla.selectRow(0)
    assert panel._identificador_seleccionado is not None
    assert "Identificador:" in panel.texto_detalle.toPlainText()


def test_ventana_principal_construye_con_las_pestanas(app):
    from gui.ventana_principal import VentanaPrincipal

    escenario = _escenario_con_datos()
    ventana = VentanaPrincipal(escenario)

    assert ventana.pestanas.count() >= 1
    assert ventana.pestanas.tabText(0) == "Eventos"
    assert "Reloj:" in ventana.etiqueta_reloj.text()
    assert "Modo: normal" in ventana.etiqueta_modo.text()


def test_deshacer_desde_la_ventana_refresca_la_tabla(app):
    from gui.ventana_principal import VentanaPrincipal

    escenario = _escenario_con_datos()
    ventana = VentanaPrincipal(escenario)
    assert ventana.panel_eventos.tabla.rowCount() == 2

    escenario.alta_evento(3, 5.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    ventana.panel_eventos.refrescar()
    assert ventana.panel_eventos.tabla.rowCount() == 3

    ventana._deshacer()
    assert ventana.panel_eventos.tabla.rowCount() == 2


def test_dialogo_nuevo_escenario_agrega_y_quita_zonas(app):
    from gui.dialogo_nuevo_escenario import DialogoNuevoEscenario

    dialogo = DialogoNuevoEscenario()
    dialogo.campo_nombre.setText("Zona de prueba")
    dialogo.campo_x_max.setValue(500.0)
    dialogo.campo_y_max.setValue(500.0)
    dialogo.campo_poblada.setChecked(True)
    dialogo._agregar_zona()

    assert len(dialogo.zonas_definidas()) == 1
    assert dialogo.tabla_zonas.rowCount() == 1

    dialogo.tabla_zonas.selectRow(0)
    dialogo._quitar_zona_seleccionada()
    assert len(dialogo.zonas_definidas()) == 0


# ---------------- vista del árbol AVL ----------------

def test_vista_arbol_dibuja_un_nodo_por_evento(app):
    from gui.vista_arbol import VistaArbolAVL

    escenario = _escenario_con_datos()
    vista = VistaArbolAVL(escenario)

    from gui.vista_arbol import _NodoGrafico
    nodos_graficos = [item for item in vista.escena.items() if isinstance(item, _NodoGrafico)]
    assert len(nodos_graficos) == 2
    assert "Nodos: 2" in vista.etiqueta_estado.text()


def test_vista_arbol_arbol_vacio_no_revienta(app):
    from gui.vista_arbol import VistaArbolAVL
    from core import Zona

    escenario = Escenario(zonas=[Zona("Z", 0.0, 1000.0, 0.0, 1000.0, poblada=True)],
                           reloj_simulacion=RELOJ)
    vista = VistaArbolAVL(escenario)
    assert vista.escena.items() != []  # al menos el texto "(árbol vacío...)"


def test_click_en_nodo_emite_senal_con_el_identificador(app):
    from gui.vista_arbol import VistaArbolAVL

    escenario = _escenario_con_datos()
    vista = VistaArbolAVL(escenario)

    recibidos = []
    vista.nodo_seleccionado.connect(recibidos.append)
    vista._nodo_clicado(1)
    assert recibidos == [1]


def test_ventana_principal_tiene_pestana_de_arbol_y_sincroniza_seleccion(app):
    from gui.ventana_principal import VentanaPrincipal

    escenario = _escenario_con_datos()
    ventana = VentanaPrincipal(escenario)

    assert ventana.pestanas.tabText(1) == "Árbol AVL"

    ventana._seleccionar_evento_desde_otra_vista(1)
    assert ventana.pestanas.currentWidget() is ventana.panel_eventos
    assert ventana.panel_eventos._identificador_seleccionado == 1


def test_alta_desde_panel_eventos_refresca_la_vista_del_arbol(app):
    from gui.ventana_principal import VentanaPrincipal

    escenario = _escenario_con_datos()
    ventana = VentanaPrincipal(escenario)

    escenario.alta_evento(3, 5.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-01")
    ventana.panel_eventos.refrescar()
    ventana.panel_eventos.cambio_realizado.emit()

    from gui.vista_arbol import _NodoGrafico
    nodos_graficos = [item for item in ventana.vista_arbol.escena.items() if isinstance(item, _NodoGrafico)]
    assert len(nodos_graficos) == 3


# ---------------- cola de reportes ----------------

def test_panel_cola_encola_y_muestra_en_la_tabla(app):
    from gui.panel_cola import PanelCola

    escenario = _escenario_con_datos()
    panel = PanelCola(escenario)

    panel.campo_id.setValue(1)
    panel.campo_magnitud.setValue(6.0)
    panel.campo_revision.setValue(1)
    panel.campo_estacion.setText("EST-02")
    panel._encolar_reporte()

    assert len(escenario.cola) == 1
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 1).text() == "1"  # columna "ID evento"


def test_panel_cola_encolar_sin_estacion_no_encola(app):
    from gui.panel_cola import PanelCola

    escenario = _escenario_con_datos()
    panel = PanelCola(escenario)
    panel.campo_estacion.setText("")
    panel._encolar_reporte()

    assert len(escenario.cola) == 0


def test_procesar_un_paso_consume_de_la_cola_y_registra_resultado(app):
    from gui.panel_cola import PanelCola
    from core import Reporte

    escenario = _escenario_con_datos()
    panel = PanelCola(escenario)
    escenario.cola.encolar(Reporte(1, 6.5, 10.0, 500.0, 500.0,
                                    datetime(2026, 9, 10, 9, 0, 0), 2, "EST-02"))
    panel.refrescar()

    procesado = panel._procesar_un_paso()

    assert procesado is True
    assert escenario.cola.esta_vacia()
    assert "ACTUALIZADO" in panel.texto_resultados.toPlainText()
    assert "Rotaciones producidas" in panel.texto_resultados.toPlainText()


def test_procesar_un_paso_con_cola_vacia_no_revienta(app):
    from gui.panel_cola import PanelCola

    escenario = _escenario_con_datos()
    panel = PanelCola(escenario)
    assert panel._procesar_un_paso() is False


def test_procesamiento_continuo_drena_toda_la_cola(app):
    """
    Se dispara el temporizador manualmente (en vez de esperar el
    intervalo real) para probar la lógica sin depender de tiempos
    reales en la suite de pruebas.
    """
    from gui.panel_cola import PanelCola
    from core import Reporte

    escenario = _escenario_con_datos()
    panel = PanelCola(escenario)
    for identificador in (10, 11, 12):
        escenario.cola.encolar(Reporte(identificador, 5.0, 10.0, 500.0, 500.0,
                                        datetime(2026, 9, 10, 9, 0, 0), 1, "EST-03"))
    panel.refrescar()

    panel._alternar_procesamiento_continuo()  # arranca el temporizador
    assert panel._temporizador.isActive()
    assert panel.boton_procesar_todos.text() == "Detener"

    for _ in range(5):  # de sobra para drenar 3 reportes
        panel._paso_continuo()

    assert escenario.cola.esta_vacia()
    assert not panel._temporizador.isActive()  # se detuvo solo al vaciarse
    assert panel.boton_procesar_todos.text() == "Procesar todos (con pausa)"


def test_ventana_principal_tiene_pestana_de_cola_y_sincroniza_eventos(app):
    from gui.ventana_principal import VentanaPrincipal
    from core import Reporte

    escenario = _escenario_con_datos()
    ventana = VentanaPrincipal(escenario)
    assert ventana.pestanas.tabText(2) == "Cola de reportes"

    escenario.cola.encolar(Reporte(50, 6.0, 10.0, 500.0, 500.0,
                                    datetime(2026, 9, 10, 9, 0, 0), 1, "EST-01"))
    ventana.panel_cola.refrescar()
    ventana.panel_cola._procesar_un_paso()

    # el evento nuevo debe aparecer también en la pestaña de Eventos y en el árbol
    assert ventana.panel_eventos.tabla.rowCount() == 3
    from gui.vista_arbol import _NodoGrafico
    nodos_graficos = [item for item in ventana.vista_arbol.escena.items() if isinstance(item, _NodoGrafico)]
    assert len(nodos_graficos) == 3


# ---------------- histórico, archivo y eliminación ----------------

def test_panel_historico_eliminar_evento_lo_retira_y_registra(app):
    from gui.panel_historico import PanelHistorico

    escenario = _escenario_con_datos()
    panel = PanelHistorico(escenario)

    panel.campo_id_eliminar.setValue(1)
    panel._eliminar_evento()

    assert escenario.catalogo.esta_eliminado(1)
    assert not escenario.catalogo.esta_activo(1)
    assert panel.tabla.rowCount() == 1
    assert panel.tabla.item(0, 1).text() == "eliminado"


def test_panel_historico_eliminar_id_inexistente_no_revienta(app):
    from gui.panel_historico import PanelHistorico

    escenario = _escenario_con_datos()
    panel = PanelHistorico(escenario)
    panel.campo_id_eliminar.setValue(999)
    panel._eliminar_evento()  # solo debe avisar, no lanzar

    assert escenario.catalogo.esta_activo(1)  # nada se tocó


def test_panel_historico_archivar_rama_sin_elegibles(app):
    from gui.panel_historico import PanelHistorico

    escenario = _escenario_con_datos()  # eventos recientes: nada es elegible
    panel = PanelHistorico(escenario)
    panel._archivar_rama()

    assert "No hay ninguna rama elegible" in panel.texto_resultado_archivo.toPlainText()


def test_panel_historico_archivar_rama_elegible(app):
    from gui.panel_historico import PanelHistorico
    from core import Zona

    zonas = [Zona("Z", 0.0, 1000.0, 0.0, 1000.0, poblada=False)]
    escenario = Escenario(zonas=zonas, reloj_simulacion=RELOJ)
    escenario.alta_evento(1, 2.0, 10.0, 500.0, 500.0,
                           datetime(2026, 9, 1, 9, 0, 0), "EST-01")  # antiguo, prioridad baja

    panel = PanelHistorico(escenario)
    panel._archivar_rama()

    assert "Se archivaron 1 evento(s)" in panel.texto_resultado_archivo.toPlainText()
    assert escenario.catalogo.esta_archivado(1)
    assert panel.tabla.rowCount() == 1


def test_panel_historico_configurar_t(app):
    from gui.panel_historico import PanelHistorico

    escenario = _escenario_con_datos()
    panel = PanelHistorico(escenario)
    panel.campo_t_horas.setValue(10.0)
    panel._configurar_t()

    assert escenario.catalogo.t_horas == 10.0


def test_ventana_principal_tiene_pestana_de_historico_y_sincroniza(app):
    from gui.ventana_principal import VentanaPrincipal

    escenario = _escenario_con_datos()
    ventana = VentanaPrincipal(escenario)
    assert ventana.pestanas.tabText(3) == "Histórico y archivo"

    ventana.panel_historico.campo_id_eliminar.setValue(2)
    ventana.panel_historico._eliminar_evento()

    # debe desaparecer de la tabla de Eventos activos
    assert ventana.panel_eventos.tabla.rowCount() == 1
    from gui.vista_arbol import _NodoGrafico
    nodos_graficos = [item for item in ventana.vista_arbol.escena.items() if isinstance(item, _NodoGrafico)]
    assert len(nodos_graficos) == 1


# ---------------- deshacer visual y versiones ----------------

def test_panel_versiones_muestra_cantidad_de_acciones_pendientes(app):
    from gui.panel_versiones import PanelVersiones

    escenario = _escenario_con_datos()  # 2 altas ya hechas
    panel = PanelVersiones(escenario)

    assert "2" in panel.etiqueta_pila.text()


def test_panel_versiones_deshacer_reduce_el_contador(app):
    from gui.panel_versiones import PanelVersiones

    escenario = _escenario_con_datos()
    panel = PanelVersiones(escenario)

    panel._deshacer()

    assert "1" in panel.etiqueta_pila.text()
    assert len(escenario.catalogo) == 1


def test_panel_versiones_guardar_y_restaurar(app):
    from gui.panel_versiones import PanelVersiones

    escenario = _escenario_con_datos()
    panel = PanelVersiones(escenario)

    panel.campo_nombre.setText("mi-version")
    panel._guardar_version()

    assert panel.lista_versiones.count() == 1
    assert panel.lista_versiones.item(0).text() == "mi-version"

    escenario.corregir_evento(1, magnitud=9.0)
    evento_modificado, _ = escenario.catalogo.consultar_evento(1)
    assert evento_modificado.magnitud == 9.0

    panel.lista_versiones.setCurrentRow(0)
    panel._restaurar_version()

    evento_restaurado, _ = escenario.catalogo.consultar_evento(1)
    assert evento_restaurado.magnitud == 6.0  # volvió al estado guardado


def test_panel_versiones_guardar_sin_nombre_no_agrega(app):
    from gui.panel_versiones import PanelVersiones

    escenario = _escenario_con_datos()
    panel = PanelVersiones(escenario)
    panel.campo_nombre.setText("")
    panel._guardar_version()

    assert panel.lista_versiones.count() == 0


def test_panel_versiones_restaurar_sin_seleccion_no_revienta(app):
    from gui.panel_versiones import PanelVersiones

    escenario = _escenario_con_datos()
    panel = PanelVersiones(escenario)
    panel._restaurar_version()  # no hay nada seleccionado, no debe lanzar


def test_ventana_principal_tiene_pestana_de_versiones_y_sincroniza(app):
    from gui.ventana_principal import VentanaPrincipal

    escenario = _escenario_con_datos()
    ventana = VentanaPrincipal(escenario)
    assert ventana.pestanas.tabText(4) == "Deshacer y versiones"

    ventana.panel_versiones.campo_nombre.setText("v1")
    ventana.panel_versiones._guardar_version()

    escenario.eliminar_evento(1)
    ventana.panel_eventos.refrescar()
    assert ventana.panel_eventos.tabla.rowCount() == 1

    ventana.panel_versiones.lista_versiones.setCurrentRow(0)
    ventana.panel_versiones._restaurar_version()

    # al restaurar la versión, el evento 1 vuelve a estar activo, y eso
    # debe reflejarse también en la pestaña de Eventos
    assert ventana.panel_eventos.tabla.rowCount() == 2


# ---------------- persistencia ----------------

def test_panel_persistencia_guarda_un_archivo_real(app, tmp_path, monkeypatch):
    from gui.panel_persistencia import PanelPersistencia
    from PySide6 import QtWidgets

    ruta = tmp_path / "escenario.json"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName",
                         staticmethod(lambda *a, **k: (str(ruta), "")))

    escenario = _escenario_con_datos()
    panel = PanelPersistencia(escenario)
    panel._guardar()

    assert ruta.exists()
    import json
    contenido = json.loads(ruta.read_text(encoding="utf-8"))
    assert contenido["arbol_activo"] is not None


def test_panel_persistencia_cargar_por_topologia_reemplaza_el_escenario(app, tmp_path, monkeypatch):
    from gui.panel_persistencia import PanelPersistencia
    from PySide6 import QtWidgets

    ruta = tmp_path / "otro_escenario.json"
    otro = _escenario_con_datos()
    otro.alta_evento(99, 5.0, 10.0, 500.0, 500.0, datetime(2026, 9, 10, 9, 0, 0), "EST-09")
    otro.guardar_json(str(ruta))

    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName",
                         staticmethod(lambda *a, **k: (str(ruta), "")))

    escenario = _escenario_con_datos()
    panel = PanelPersistencia(escenario)
    panel.cambio_realizado.connect(lambda: None)  # solo para confirmar que no revienta al emitir
    panel._cargar_por_topologia()

    assert len(escenario.catalogo) == 3  # 1, 2 y 99 del archivo cargado
    assert escenario.catalogo.esta_activo(99)


def test_panel_persistencia_cargar_por_topologia_invalido_no_modifica_nada(app, tmp_path, monkeypatch):
    from gui.panel_persistencia import PanelPersistencia
    from PySide6 import QtWidgets
    import json

    ruta = tmp_path / "corrupto.json"
    ruta.write_text(json.dumps({"zonas": [], "reloj_simulacion": "2026-09-10T12:00:00Z",
                                 "modo": "normal", "arbol_activo": {"evento": {}, "altura": 999,
                                 "factor_balance": 0, "izquierdo": None, "derecho": None},
                                 "historico": {"archivados": [], "eliminados": []}, "cola": []}))

    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName",
                         staticmethod(lambda *a, **k: (str(ruta), "")))

    escenario = _escenario_con_datos()
    panel = PanelPersistencia(escenario)
    panel._cargar_por_topologia()

    assert len(escenario.catalogo) == 2  # no se tocó nada


def test_panel_persistencia_cargar_por_inserciones_muestra_comparacion(app, tmp_path, monkeypatch):
    from gui.panel_persistencia import PanelPersistencia
    from PySide6 import QtWidgets
    import json

    ruta = tmp_path / "inserciones.json"
    eventos = [
        {"identificador": i, "magnitud": 5.0, "profundidad": 10.0,
         "epicentro_x": 500.0, "epicentro_y": 500.0,
         "fecha_hora": "2026-09-10T09:00:00Z", "revision": 1,
         "estaciones": ["EST-01"], "estado_atencion": "pendiente", "prioridad": 3}
        for i in range(1, 8)
    ]
    ruta.write_text(json.dumps({"eventos": eventos}))

    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName",
                         staticmethod(lambda *a, **k: (str(ruta), "")))

    escenario = _escenario_con_datos()
    panel = PanelPersistencia(escenario)
    panel._cargar_por_inserciones()

    assert panel.ultimo_resumen_comparacion is not None
    assert "AVL ->" in panel.texto_comparacion.toPlainText()
    assert "BST ->" in panel.texto_comparacion.toPlainText()
    assert len(escenario.catalogo) == 7


def test_panel_persistencia_cancelar_dialogo_no_hace_nada(app, monkeypatch):
    from gui.panel_persistencia import PanelPersistencia
    from PySide6 import QtWidgets

    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName",
                         staticmethod(lambda *a, **k: ("", "")))  # el usuario cancela

    escenario = _escenario_con_datos()
    panel = PanelPersistencia(escenario)
    panel._guardar()  # no debe lanzar ni hacer nada


def test_ventana_principal_tiene_pestana_de_persistencia(app):
    from gui.ventana_principal import VentanaPrincipal

    escenario = _escenario_con_datos()
    ventana = VentanaPrincipal(escenario)
    assert ventana.pestanas.tabText(5) == "Persistencia"


# ---------------- comparación AVL vs BST ----------------

def test_panel_comparacion_sin_carga_previa_muestra_mensaje(app):
    from gui.panel_persistencia import PanelPersistencia
    from gui.panel_comparacion_bst import PanelComparacionBST

    escenario = _escenario_con_datos()
    panel_persistencia = PanelPersistencia(escenario)
    panel = PanelComparacionBST(escenario, panel_persistencia)

    assert panel.panel_persistencia.ultimo_bst_comparacion is None
    assert "AVL actual ->" in panel.etiqueta_resumen.text()
    assert panel.escena_avl.items() != []  # el AVL actual sí se dibuja


def test_panel_comparacion_dibuja_avl_y_bst_tras_carga_por_inserciones(app, tmp_path, monkeypatch):
    from gui.panel_persistencia import PanelPersistencia
    from gui.panel_comparacion_bst import PanelComparacionBST
    from PySide6 import QtWidgets
    import json

    ruta = tmp_path / "inserciones.json"
    eventos = [
        {"identificador": i, "magnitud": 5.0, "profundidad": 10.0,
         "epicentro_x": 500.0, "epicentro_y": 500.0,
         "fecha_hora": "2026-09-10T09:00:00Z", "revision": 1,
         "estaciones": ["EST-01"], "estado_atencion": "pendiente", "prioridad": 3}
        for i in range(1, 8)
    ]
    ruta.write_text(json.dumps({"eventos": eventos}))
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName",
                         staticmethod(lambda *a, **k: (str(ruta), "")))

    escenario = _escenario_con_datos()
    panel_persistencia = PanelPersistencia(escenario)
    panel_persistencia._cargar_por_inserciones()

    panel = PanelComparacionBST(escenario, panel_persistencia)

    assert "Última carga por inserciones" in panel.etiqueta_resumen.text()
    assert panel.escena_bst.items() != []
    assert panel.escena_avl.items() != []


def test_ventana_principal_tiene_pestana_de_comparacion_y_se_actualiza_al_entrar(app, tmp_path, monkeypatch):
    from gui.ventana_principal import VentanaPrincipal
    from PySide6 import QtWidgets
    import json

    ruta = tmp_path / "inserciones2.json"
    eventos = [
        {"identificador": i, "magnitud": 5.0, "profundidad": 10.0,
         "epicentro_x": 500.0, "epicentro_y": 500.0,
         "fecha_hora": "2026-09-10T09:00:00Z", "revision": 1,
         "estaciones": ["EST-01"], "estado_atencion": "pendiente", "prioridad": 3}
        for i in range(1, 6)
    ]
    ruta.write_text(json.dumps({"eventos": eventos}))
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName",
                         staticmethod(lambda *a, **k: (str(ruta), "")))

    escenario = _escenario_con_datos()
    ventana = VentanaPrincipal(escenario)
    assert ventana.pestanas.tabText(6) == "Comparación AVL vs BST"

    ventana.panel_persistencia._cargar_por_inserciones()

    # todavía no se cambió a esa pestaña: currentChanged se dispara al entrar
    ventana.pestanas.setCurrentWidget(ventana.panel_comparacion)
    assert "Última carga por inserciones" in ventana.panel_comparacion.etiqueta_resumen.text()


# ---------------- plano geográfico ----------------

def test_panel_plano_dibuja_zonas_y_eventos(app):
    from gui.panel_plano import PanelPlano

    escenario = _escenario_con_datos()
    panel = PanelPlano(escenario)

    from gui.panel_plano import _PuntoEvento
    puntos = [item for item in panel.escena.items() if isinstance(item, _PuntoEvento)]
    assert len(puntos) == 2

    from PySide6 import QtWidgets
    rectangulos = [item for item in panel.escena.items() if isinstance(item, QtWidgets.QGraphicsRectItem)]
    # 1 marco del plano completo + 1 por cada zona (una zona en _escenario_con_datos)
    assert len(rectangulos) >= 2


def test_panel_plano_sin_zonas_no_revienta(app):
    from gui.panel_plano import PanelPlano

    escenario = Escenario(zonas=[], reloj_simulacion=RELOJ)
    panel = PanelPlano(escenario)
    assert panel.escena.items() != []  # al menos el marco del plano


def test_click_en_punto_emite_senal_con_el_identificador(app):
    from gui.panel_plano import PanelPlano

    escenario = _escenario_con_datos()
    panel = PanelPlano(escenario)

    recibidos = []
    panel.evento_seleccionado.connect(recibidos.append)
    panel._evento_clicado(2)
    assert recibidos == [2]


def test_ventana_principal_tiene_pestana_de_plano_y_sincroniza_seleccion(app):
    from gui.ventana_principal import VentanaPrincipal

    escenario = _escenario_con_datos()
    ventana = VentanaPrincipal(escenario)
    assert ventana.pestanas.tabText(7) == "Plano geográfico"

    ventana._seleccionar_evento_desde_otra_vista(2)
    assert ventana.pestanas.currentWidget() is ventana.panel_eventos
    assert ventana.panel_eventos._identificador_seleccionado == 2


def test_eliminar_evento_refresca_el_plano(app):
    from gui.ventana_principal import VentanaPrincipal
    from gui.panel_plano import _PuntoEvento

    escenario = _escenario_con_datos()
    ventana = VentanaPrincipal(escenario)

    ventana.panel_historico.campo_id_eliminar.setValue(1)
    ventana.panel_historico._eliminar_evento()

    puntos = [item for item in ventana.panel_plano.escena.items() if isinstance(item, _PuntoEvento)]
    assert len(puntos) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
