from datetime import datetime

from PySide6 import QtWidgets, QtCore

from core import Zona


class DialogoNuevoEscenario(QtWidgets.QDialog):
    """
    Initial application screen: defines the scenario zones and the
    initial simulation clock. Zone geometry is fixed for the whole
    execution (section 3), so this is requested ONCE, before creating
    the Escenario -- there is intentionally no way to add zones later
    from the rest of the interface.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo escenario — SismoLab AVL")
        self.resize(640, 480)

        self._zonas = []

        layout = QtWidgets.QVBoxLayout(self)

        fila_reloj = QtWidgets.QHBoxLayout()
        fila_reloj.addWidget(QtWidgets.QLabel("Reloj de simulación inicial:"))
        self.campo_reloj = QtWidgets.QDateTimeEdit(QtCore.QDateTime.currentDateTimeUtc())
        self.campo_reloj.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.campo_reloj.setCalendarPopup(True)
        fila_reloj.addWidget(self.campo_reloj)
        fila_reloj.addStretch()
        layout.addLayout(fila_reloj)

        layout.addWidget(QtWidgets.QLabel("Zonas del escenario (quedan fijas durante la ejecución):"))
        self.tabla_zonas = QtWidgets.QTableWidget(0, 6)
        self.tabla_zonas.setHorizontalHeaderLabels(
            ["Nombre", "x_min", "x_max", "y_min", "y_max", "Poblada"]
        )
        self.tabla_zonas.horizontalHeader().setStretchLastSection(True)
        self.tabla_zonas.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.tabla_zonas)

        boton_quitar = QtWidgets.QPushButton("Quitar zona seleccionada")
        boton_quitar.clicked.connect(self._quitar_zona_seleccionada)
        layout.addWidget(boton_quitar)

        grupo = QtWidgets.QGroupBox("Agregar zona")
        formulario = QtWidgets.QFormLayout(grupo)

        self.campo_nombre = QtWidgets.QLineEdit()
        self.campo_x_min = self._crear_spin_coordenada()
        self.campo_x_max = self._crear_spin_coordenada(1000.0)
        self.campo_y_min = self._crear_spin_coordenada()
        self.campo_y_max = self._crear_spin_coordenada(1000.0)
        self.campo_poblada = QtWidgets.QCheckBox("Zona poblada")

        formulario.addRow("Nombre:", self.campo_nombre)
        formulario.addRow("x mínimo (km):", self.campo_x_min)
        formulario.addRow("x máximo (km):", self.campo_x_max)
        formulario.addRow("y mínimo (km):", self.campo_y_min)
        formulario.addRow("y máximo (km):", self.campo_y_max)
        formulario.addRow(self.campo_poblada)

        boton_agregar = QtWidgets.QPushButton("Agregar zona")
        boton_agregar.clicked.connect(self._agregar_zona)
        formulario.addRow(boton_agregar)

        layout.addWidget(grupo)

        botones = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        botones.button(QtWidgets.QDialogButtonBox.Ok).setText("Iniciar escenario")
        botones.accepted.connect(self._confirmar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    @staticmethod
    def _crear_spin_coordenada(valor_inicial=0.0):
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.0, 1000.0)
        spin.setDecimals(1)
        spin.setValue(valor_inicial)
        return spin

    def _agregar_zona(self):
        nombre = self.campo_nombre.text().strip()
        if not nombre:
            QtWidgets.QMessageBox.warning(self, "Falta el nombre", "La zona necesita un nombre.")
            return
        try:
            zona = Zona(
                nombre,
                self.campo_x_min.value(), self.campo_x_max.value(),
                self.campo_y_min.value(), self.campo_y_max.value(),
                self.campo_poblada.isChecked(),
            )
        except ValueError as error:
            QtWidgets.QMessageBox.warning(self, "Zona inválida", str(error))
            return

        self._zonas.append(zona)
        self._repintar_tabla()
        self.campo_nombre.clear()

    def _quitar_zona_seleccionada(self):
        filas = self.tabla_zonas.selectionModel().selectedRows()
        if not filas:
            return
        indice = filas[0].row()
        del self._zonas[indice]
        self._repintar_tabla()

    def _repintar_tabla(self):
        self.tabla_zonas.setRowCount(0)
        for zona in self._zonas:
            fila = self.tabla_zonas.rowCount()
            self.tabla_zonas.insertRow(fila)
            valores = [zona.nombre, zona.x_min, zona.x_max, zona.y_min, zona.y_max,
                       "Sí" if zona.poblada else "No"]
            for columna, valor in enumerate(valores):
                self.tabla_zonas.setItem(fila, columna, QtWidgets.QTableWidgetItem(str(valor)))

    def _confirmar(self):
        if not self._zonas:
            respuesta = QtWidgets.QMessageBox.question(
                self, "Sin zonas",
                "No definiste ninguna zona. Ningún evento podrá caer en zona poblada, así "
                "que la prioridad alta por esa vía nunca ocurrirá. ¿Continuar de todos modos?",
            )
            if respuesta != QtWidgets.QMessageBox.Yes:
                return
        self.accept()

    def reloj_seleccionado(self):
        qdt = self.campo_reloj.dateTime()
        return datetime(qdt.date().year(), qdt.date().month(), qdt.date().day(),
                         qdt.time().hour(), qdt.time().minute(), qdt.time().second())

    def zonas_definidas(self):
        return list(self._zonas)
