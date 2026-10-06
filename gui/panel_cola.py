from datetime import datetime

from PySide6 import QtWidgets, QtCore

from core import Reporte, ValidacionError


class PanelCola(QtWidgets.QWidget):
    """
    Cola de reportes pendientes (sección 8): encolar ráfagas, y
    procesar un reporte por paso o de forma continua CON PAUSA entre
    pasos (con un QTimer, para que se vea avanzar de verdad, no solo
    "procesar todo de golpe"). El modo (normal/estrés) se controla
    desde la barra superior de la ventana principal; aquí solo se lee
    `escenario.modo` para mostrarlo.
    """

    cambio_realizado = QtCore.Signal()

    INTERVALO_PAUSA_MS = 400

    def __init__(self, escenario, parent=None):
        super().__init__(parent)
        self.escenario = escenario

        self._temporizador = QtCore.QTimer(self)
        self._temporizador.setInterval(self.INTERVALO_PAUSA_MS)
        self._temporizador.timeout.connect(self._paso_continuo)

        layout_principal = QtWidgets.QHBoxLayout(self)

        # ---------------- columna izquierda: formulario + procesamiento ----------------
        columna_izquierda = QtWidgets.QVBoxLayout()

        grupo_formulario = QtWidgets.QGroupBox("Encolar reporte")
        formulario = QtWidgets.QFormLayout(grupo_formulario)

        self.campo_id = QtWidgets.QSpinBox()
        self.campo_id.setRange(1, 999999)

        self.campo_magnitud = QtWidgets.QDoubleSpinBox()
        self.campo_magnitud.setRange(-2.0, 10.0)
        self.campo_magnitud.setDecimals(1)
        self.campo_magnitud.setSingleStep(0.1)

        self.campo_profundidad = QtWidgets.QDoubleSpinBox()
        self.campo_profundidad.setRange(0.0, 700.0)
        self.campo_profundidad.setDecimals(1)
        self.campo_profundidad.setSingleStep(0.1)

        self.campo_x = QtWidgets.QDoubleSpinBox()
        self.campo_x.setRange(0.0, 1000.0)
        self.campo_x.setDecimals(1)

        self.campo_y = QtWidgets.QDoubleSpinBox()
        self.campo_y.setRange(0.0, 1000.0)
        self.campo_y.setDecimals(1)

        self.campo_fecha = QtWidgets.QDateTimeEdit(QtCore.QDateTime.currentDateTimeUtc())
        self.campo_fecha.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.campo_fecha.setCalendarPopup(True)

        self.campo_revision = QtWidgets.QSpinBox()
        self.campo_revision.setRange(1, 999999)
        self.campo_revision.setValue(1)

        self.campo_estacion = QtWidgets.QLineEdit()
        self.campo_estacion.setPlaceholderText("EST-01")

        formulario.addRow("Identificador:", self.campo_id)
        formulario.addRow("Magnitud:", self.campo_magnitud)
        formulario.addRow("Profundidad (km):", self.campo_profundidad)
        formulario.addRow("Epicentro x (km):", self.campo_x)
        formulario.addRow("Epicentro y (km):", self.campo_y)
        formulario.addRow("Fecha y hora del sismo:", self.campo_fecha)
        formulario.addRow("Revisión:", self.campo_revision)
        formulario.addRow("Estación:", self.campo_estacion)

        boton_encolar = QtWidgets.QPushButton("Encolar reporte")
        boton_encolar.clicked.connect(self._encolar_reporte)
        formulario.addRow(boton_encolar)

        columna_izquierda.addWidget(grupo_formulario)

        grupo_procesar = QtWidgets.QGroupBox("Procesamiento")
        layout_procesar = QtWidgets.QVBoxLayout(grupo_procesar)

        self.etiqueta_modo = QtWidgets.QLabel()
        layout_procesar.addWidget(self.etiqueta_modo)

        fila_botones = QtWidgets.QHBoxLayout()
        self.boton_procesar_uno = QtWidgets.QPushButton("Procesar siguiente")
        self.boton_procesar_todos = QtWidgets.QPushButton("Procesar todos (con pausa)")
        fila_botones.addWidget(self.boton_procesar_uno)
        fila_botones.addWidget(self.boton_procesar_todos)
        layout_procesar.addLayout(fila_botones)

        self.boton_procesar_uno.clicked.connect(self._procesar_un_paso)
        self.boton_procesar_todos.clicked.connect(self._alternar_procesamiento_continuo)

        layout_procesar.addWidget(QtWidgets.QLabel("Historial de resultados (más reciente al final):"))
        self.texto_resultados = QtWidgets.QPlainTextEdit()
        self.texto_resultados.setReadOnly(True)
        layout_procesar.addWidget(self.texto_resultados)

        columna_izquierda.addWidget(grupo_procesar)
        layout_principal.addLayout(columna_izquierda, stretch=1)

        # ---------------- columna derecha: cola en orden de recepción ----------------
        columna_derecha = QtWidgets.QVBoxLayout()
        columna_derecha.addWidget(QtWidgets.QLabel("Cola de reportes pendientes (orden de recepción, FIFO)"))

        self.tabla = QtWidgets.QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(
            ["Posición", "ID evento", "Revisión", "Estación", "Magnitud", "Fecha del sismo"]
        )
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        columna_derecha.addWidget(self.tabla)

        layout_principal.addLayout(columna_derecha, stretch=1)

        self.refrescar()

    # ---------------- refresco ----------------

    def refrescar(self):
        self.etiqueta_modo.setText(
            f"Modo actual: {self.escenario.modo}"
            + (" — las altas/correcciones NO se rebalancean automáticamente"
               if self.escenario.modo == "estres" else "")
        )

        self.tabla.setRowCount(0)
        for posicion, reporte in enumerate(self.escenario.cola.ver_orden(), start=1):
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)
            valores = [
                posicion, reporte.identificador, reporte.revision, reporte.estacion,
                reporte.magnitud, reporte.fecha_hora,
            ]
            for columna, valor in enumerate(valores):
                self.tabla.setItem(fila, columna, QtWidgets.QTableWidgetItem(str(valor)))

    # ---------------- encolar ----------------

    def _fecha_hora_del_formulario(self):
        qdt = self.campo_fecha.dateTime()
        return datetime(qdt.date().year(), qdt.date().month(), qdt.date().day(),
                         qdt.time().hour(), qdt.time().minute(), qdt.time().second())

    def _encolar_reporte(self):
        estacion = self.campo_estacion.text().strip()
        if not estacion:
            QtWidgets.QMessageBox.warning(self, "Falta la estación", "Indica qué estación envía el reporte.")
            return
        reporte = Reporte(
            self.campo_id.value(), self.campo_magnitud.value(), self.campo_profundidad.value(),
            self.campo_x.value(), self.campo_y.value(), self._fecha_hora_del_formulario(),
            self.campo_revision.value(), estacion,
        )
        self.escenario.cola.encolar(reporte)
        self.refrescar()

    # ---------------- procesar un paso ----------------

    def _describir_resultado(self, reporte, resultado, rotaciones_producidas):
        texto = (
            f"Estación {reporte.estacion} -> evento {reporte.identificador} "
            f"(revisión {reporte.revision}): {resultado.tipo.value.upper()}\n"
            f"   {resultado.mensaje}"
        )
        detalle = ", ".join(f"{caso}={cantidad}" for caso, cantidad in rotaciones_producidas.items() if cantidad)
        texto += f"\n   Rotaciones producidas: {detalle if detalle else 'ninguna'}"
        return texto

    def _procesar_un_paso(self):
        """Procesa EXACTAMENTE un reporte (sección 8: 'los reportes de
        cada paso se resuelven completamente antes del siguiente').
        Devuelve True si procesó algo, False si la cola ya estaba vacía."""
        if self.escenario.cola.esta_vacia():
            QtWidgets.QMessageBox.information(self, "Cola vacía", "No hay reportes pendientes por procesar.")
            return False

        casos_antes = dict(self.escenario.catalogo.avl.contador_casos)
        try:
            reporte, resultado = self.escenario.procesar_siguiente_reporte()
        except ValidacionError as error:
            QtWidgets.QMessageBox.warning(self, "No se pudo procesar el reporte", str(error))
            return False
        casos_despues = self.escenario.catalogo.avl.contador_casos
        rotaciones_producidas = {caso: casos_despues[caso] - casos_antes[caso] for caso in casos_antes}

        self.texto_resultados.appendPlainText(self._describir_resultado(reporte, resultado, rotaciones_producidas))
        self.refrescar()
        self.cambio_realizado.emit()
        return True

    # ---------------- procesamiento continuo con pausa ----------------

    def _alternar_procesamiento_continuo(self):
        if self._temporizador.isActive():
            self._detener_procesamiento_continuo()
            return

        if self.escenario.cola.esta_vacia():
            QtWidgets.QMessageBox.information(self, "Cola vacía", "No hay reportes pendientes por procesar.")
            return

        self.boton_procesar_todos.setText("Detener")
        self.boton_procesar_uno.setEnabled(False)
        self._temporizador.start()

    def _detener_procesamiento_continuo(self):
        self._temporizador.stop()
        self.boton_procesar_todos.setText("Procesar todos (con pausa)")
        self.boton_procesar_uno.setEnabled(True)

    def _paso_continuo(self):
        """Se llama cada INTERVALO_PAUSA_MS mientras el temporizador esté
        activo -- así 'procesar todos' se ve avanzar de verdad, con
        pausa entre pasos, en vez de resolverse todo de un golpe."""
        if self.escenario.cola.esta_vacia():
            self._detener_procesamiento_continuo()
            return
        self._procesar_un_paso()