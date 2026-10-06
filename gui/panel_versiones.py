from PySide6 import QtWidgets, QtCore

from core import ValidacionError


class PanelVersiones(QtWidgets.QWidget):
    """
    La pila de deshacer (sección 13) ya tiene su botón en la barra
    superior, visible desde cualquier pestaña; aquí se ve además cuántas
    acciones hay pendientes por deshacer. El resto de este panel son las
    versiones nombradas persistentes: guardarlas, listarlas y
    restaurarlas -- independientes de la pila de deshacer, pero
    restaurar una versión es, en sí misma, una acción que se puede
    deshacer.
    """

    cambio_realizado = QtCore.Signal()

    def __init__(self, escenario, parent=None):
        super().__init__(parent)
        self.escenario = escenario

        layout = QtWidgets.QVBoxLayout(self)

        grupo_deshacer = QtWidgets.QGroupBox("Deshacer")
        layout_deshacer = QtWidgets.QHBoxLayout(grupo_deshacer)
        self.etiqueta_pila = QtWidgets.QLabel()
        layout_deshacer.addWidget(self.etiqueta_pila)
        layout_deshacer.addStretch()
        boton_deshacer = QtWidgets.QPushButton("Deshacer última acción")
        boton_deshacer.clicked.connect(self._deshacer)
        layout_deshacer.addWidget(boton_deshacer)
        layout.addWidget(grupo_deshacer)

        grupo_versiones = QtWidgets.QGroupBox("Versiones nombradas persistentes")
        layout_versiones = QtWidgets.QVBoxLayout(grupo_versiones)

        fila_guardar = QtWidgets.QHBoxLayout()
        self.campo_nombre = QtWidgets.QLineEdit()
        self.campo_nombre.setPlaceholderText("nombre de la versión")
        fila_guardar.addWidget(self.campo_nombre)
        boton_guardar = QtWidgets.QPushButton("Guardar versión actual")
        boton_guardar.clicked.connect(self._guardar_version)
        fila_guardar.addWidget(boton_guardar)
        layout_versiones.addLayout(fila_guardar)

        self.lista_versiones = QtWidgets.QListWidget()
        layout_versiones.addWidget(self.lista_versiones)

        boton_restaurar = QtWidgets.QPushButton("Restaurar versión seleccionada")
        boton_restaurar.clicked.connect(self._restaurar_version)
        layout_versiones.addWidget(boton_restaurar)

        layout_versiones.addWidget(QtWidgets.QLabel(
            "Restaurar una versión es, en sí misma, una acción que se puede deshacer.\n"
            "Las versiones NO incluyen la pila de deshacer ni otras versiones."
        ))

        layout.addWidget(grupo_versiones)
        layout.addStretch()

        self.refrescar()

    # ---------------- refresco ----------------

    def refrescar(self):
        cantidad = len(self.escenario._pila_deshacer)
        self.etiqueta_pila.setText(
            f"Acciones disponibles para deshacer: {cantidad}"
            if cantidad else "No hay ninguna acción por deshacer."
        )

        seleccion_actual = None
        item_seleccionado = self.lista_versiones.currentItem()
        if item_seleccionado is not None:
            seleccion_actual = item_seleccionado.text()

        self.lista_versiones.clear()
        for nombre in self.escenario.listar_versiones():
            self.lista_versiones.addItem(nombre)

        if seleccion_actual is not None:
            coincidencias = self.lista_versiones.findItems(seleccion_actual, QtCore.Qt.MatchExactly)
            if coincidencias:
                self.lista_versiones.setCurrentItem(coincidencias[0])

    # ---------------- acciones ----------------

    def _deshacer(self):
        if not self.escenario.deshacer():
            QtWidgets.QMessageBox.information(self, "Deshacer", "No hay ninguna acción por deshacer.")
            return
        self.refrescar()
        self.cambio_realizado.emit()

    def _guardar_version(self):
        nombre = self.campo_nombre.text().strip()
        if not nombre:
            QtWidgets.QMessageBox.warning(self, "Falta el nombre", "Ponle un nombre a la versión.")
            return

        ya_existia = nombre in self.escenario.listar_versiones()
        self.escenario.guardar_version(nombre)
        self.campo_nombre.clear()
        self.refrescar()
        if ya_existia:
            QtWidgets.QMessageBox.information(
                self, "Versión sobrescrita", f"Ya existía una versión llamada '{nombre}'; se reemplazó."
            )

    def _restaurar_version(self):
        item = self.lista_versiones.currentItem()
        if item is None:
            QtWidgets.QMessageBox.information(self, "Restaurar versión", "Selecciona una versión de la lista.")
            return
        try:
            self.escenario.restaurar_version(item.text())
        except ValidacionError as error:
            QtWidgets.QMessageBox.warning(self, "No se pudo restaurar", str(error))
            return
        self.refrescar()
        self.cambio_realizado.emit()
