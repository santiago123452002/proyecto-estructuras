from datetime import datetime

from PySide6 import QtWidgets, QtCore

from core import ValidacionError

from .panel_eventos import PanelEventos
from .vista_arbol import VistaArbolAVL
from .panel_cola import PanelCola
from .panel_historico import PanelHistorico
from .panel_versiones import PanelVersiones
from .panel_persistencia import PanelPersistencia
from .panel_comparacion_bst import PanelComparacionBST
from .panel_plano import PanelPlano


class VentanaPrincipal(QtWidgets.QMainWindow):
    """
    Main window: a top bar with the scenario's global state (clock,
    mode, undo) that applies to every tab, and a QTabWidget with one
    tab per functional screen. For now only the "Eventos" tab exists;
    the rest (AVL, queue, history, versions, audit, BST comparison,
    geographic map) are added in later steps, each as its own widget.
    """

    def __init__(self, escenario):
        super().__init__()
        self.escenario = escenario
        self.setWindowTitle("SismoLab AVL — Observatorio sísmico simulado")
        self.resize(1150, 720)

        self._crear_barra_estado()

        self.pestanas = QtWidgets.QTabWidget()
        self.setCentralWidget(self.pestanas)

        self.panel_eventos = PanelEventos(self.escenario)
        self.panel_eventos.cambio_realizado.connect(self._al_cambiar_desde_panel_eventos)
        self.pestanas.addTab(self.panel_eventos, "Eventos")

        self.vista_arbol = VistaArbolAVL(self.escenario)
        self.vista_arbol.nodo_seleccionado.connect(self._seleccionar_evento_desde_otra_vista)
        self.pestanas.addTab(self.vista_arbol, "Árbol AVL")

        self.panel_cola = PanelCola(self.escenario)
        self.panel_cola.cambio_realizado.connect(self._al_cambiar_desde_panel_eventos)
        self.pestanas.addTab(self.panel_cola, "Cola de reportes")

        self.panel_historico = PanelHistorico(self.escenario)
        self.panel_historico.cambio_realizado.connect(self._al_cambiar_desde_panel_eventos)
        self.pestanas.addTab(self.panel_historico, "Histórico y archivo")

        self.panel_versiones = PanelVersiones(self.escenario)
        self.panel_versiones.cambio_realizado.connect(self._al_cambiar_desde_panel_eventos)
        self.pestanas.addTab(self.panel_versiones, "Deshacer y versiones")

        self.panel_persistencia = PanelPersistencia(self.escenario)
        self.panel_persistencia.cambio_realizado.connect(self._al_cambiar_desde_panel_eventos)
        self.pestanas.addTab(self.panel_persistencia, "Persistencia")

        self.panel_comparacion = PanelComparacionBST(self.escenario, self.panel_persistencia)
        self.pestanas.addTab(self.panel_comparacion, "Comparación AVL vs BST")

        self.panel_plano = PanelPlano(self.escenario)
        self.panel_plano.evento_seleccionado.connect(self._seleccionar_evento_desde_otra_vista)
        self.pestanas.addTab(self.panel_plano, "Plano geográfico")

        self.pestanas.currentChanged.connect(self._al_cambiar_pestana)

        self._actualizar_barra_estado()

    # ---------------- top bar ----------------

    def _crear_barra_estado(self):
        barra = QtWidgets.QToolBar("Estado del escenario")
        barra.setMovable(False)
        self.addToolBar(barra)

        self.etiqueta_reloj = QtWidgets.QLabel()
        self.etiqueta_modo = QtWidgets.QLabel()
        fuente_negrita = self.etiqueta_reloj.font()
        fuente_negrita.setBold(True)
        self.etiqueta_reloj.setFont(fuente_negrita)
        self.etiqueta_modo.setFont(fuente_negrita)

        barra.addWidget(self.etiqueta_reloj)
        barra.addSeparator()
        barra.addWidget(self.etiqueta_modo)
        barra.addSeparator()

        boton_avanzar_reloj = QtWidgets.QPushButton("Avanzar reloj...")
        boton_avanzar_reloj.clicked.connect(self._avanzar_reloj)
        barra.addWidget(boton_avanzar_reloj)

        boton_modo = QtWidgets.QPushButton("Cambiar modo (normal / estrés)")
        boton_modo.clicked.connect(self._alternar_modo)
        barra.addWidget(boton_modo)

        barra.addSeparator()

        boton_deshacer = QtWidgets.QPushButton("Deshacer")
        boton_deshacer.clicked.connect(self._deshacer)
        barra.addWidget(boton_deshacer)

    def _actualizar_barra_estado(self):
        self.etiqueta_reloj.setText(f"Reloj: {self.escenario.reloj_simulacion}")
        self.etiqueta_modo.setText(f"Modo: {self.escenario.modo}")

    def _refrescar_todo(self):
        self.panel_eventos.refrescar()
        self.vista_arbol.refrescar()
        self.panel_cola.refrescar()
        self.panel_historico.refrescar()
        self.panel_versiones.refrescar()
        self.panel_persistencia.refrescar()
        self.panel_comparacion.refrescar()
        self.panel_plano.refrescar()
        self._actualizar_barra_estado()

    def _al_cambiar_pestana(self, indice):
        """The AVL vs BST comparison is recomputed when entering that
        tab, instead of staying synchronized by signals all the time
        (the AVL can change because of actions on any other tab, and it
        is not worth redrawing two complete trees on every one of them
        if the user is not even looking at this one)."""
        if self.pestanas.widget(indice) is self.panel_comparacion:
            self.panel_comparacion.refrescar()

    def _seleccionar_evento_desde_otra_vista(self, identificador):
        """When a tree node or a point on the geographic map is clicked,
        it jumps to the Eventos tab with that event already selected
        and its detail in view."""
        self.panel_eventos.seleccionar_por_identificador(identificador)
        self.pestanas.setCurrentWidget(self.panel_eventos)

    def _al_cambiar_desde_panel_eventos(self):
        """Any tab that modifies the scenario (Eventos, Cola, Histórico,
        Versiones, Persistencia, and so on) notifies through here so the
        OTHERS stay up to date, without refreshing itself twice
        unnecessarily."""
        remitente = self.sender()
        if remitente is not self.panel_eventos:
            self.panel_eventos.refrescar()
        if remitente is not self.vista_arbol:
            self.vista_arbol.refrescar()
        if remitente is not self.panel_cola:
            self.panel_cola.refrescar()
        if remitente is not self.panel_historico:
            self.panel_historico.refrescar()
        if remitente is not self.panel_versiones:
            self.panel_versiones.refrescar()
        if remitente is not self.panel_persistencia:
            self.panel_persistencia.refrescar()
        if remitente is not self.panel_plano:
            self.panel_plano.refrescar()
        if self.pestanas.currentWidget() is self.panel_comparacion:
            self.panel_comparacion.refrescar()
        self._actualizar_barra_estado()

    # ---------------- bar actions ----------------

    def _avanzar_reloj(self):
        dialogo = QtWidgets.QDialog(self)
        dialogo.setWindowTitle("Avanzar el reloj de simulación")
        layout = QtWidgets.QVBoxLayout(dialogo)
        layout.addWidget(QtWidgets.QLabel(
            "El reloj no puede retroceder. Los eventos con fecha posterior al nuevo\n"
            "reloj serán rechazados por el resto de las operaciones."
        ))

        campo = QtWidgets.QDateTimeEdit(QtCore.QDateTime(self.escenario.reloj_simulacion))
        campo.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        campo.setCalendarPopup(True)
        layout.addWidget(campo)

        botones = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        botones.accepted.connect(dialogo.accept)
        botones.rejected.connect(dialogo.reject)
        layout.addWidget(botones)

        if dialogo.exec() != QtWidgets.QDialog.Accepted:
            return

        qdt = campo.dateTime()
        nuevo_reloj = datetime(qdt.date().year(), qdt.date().month(), qdt.date().day(),
                                qdt.time().hour(), qdt.time().minute(), qdt.time().second())
        try:
            self.escenario.avanzar_reloj(nuevo_reloj)
        except ValidacionError as error:
            QtWidgets.QMessageBox.warning(self, "No se pudo avanzar el reloj", str(error))
            return
        self._refrescar_todo()

    def _alternar_modo(self):
        nuevo_modo = "estres" if self.escenario.modo == "normal" else "normal"
        mensaje = (
            "Vas a pasar a modo ESTRÉS: las próximas altas/correcciones/eliminaciones\n"
            "conservarán el orden pero NO se rebalancearán automáticamente."
            if nuevo_modo == "estres" else
            "Vas a volver a modo NORMAL: las próximas operaciones se rebalancearán\n"
            "automáticamente de nuevo. El árbol actual puede seguir desbalanceado\n"
            "hasta que uses 'Recuperar equilibrio'."
        )
        respuesta = QtWidgets.QMessageBox.question(self, "Cambiar de modo", mensaje)
        if respuesta != QtWidgets.QMessageBox.Yes:
            return
        try:
            self.escenario.cambiar_modo(nuevo_modo)
        except ValidacionError as error:
            QtWidgets.QMessageBox.warning(self, "No se pudo cambiar de modo", str(error))
            return
        self._refrescar_todo()

    def _deshacer(self):
        if not self.escenario.deshacer():
            QtWidgets.QMessageBox.information(self, "Deshacer", "No hay ninguna acción por deshacer.")
            return
        self._refrescar_todo()
