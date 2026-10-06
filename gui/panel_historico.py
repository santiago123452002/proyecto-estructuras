from PySide6 import QtWidgets, QtCore

from core import ValidacionError


class PanelHistorico(QtWidgets.QWidget):
    """
    Individual deletion and archiving of old subtrees (sections 6 and
    10), plus the history table (archived and deleted events, section
    10: "the history keeps their data and identities").
    """

    cambio_realizado = QtCore.Signal()

    def __init__(self, escenario, parent=None):
        super().__init__(parent)
        self.escenario = escenario

        layout_principal = QtWidgets.QHBoxLayout(self)
        columna_izquierda = QtWidgets.QVBoxLayout()

        # ---------------- individual deletion ----------------
        grupo_eliminar = QtWidgets.QGroupBox("Eliminación individual (sección 6)")
        layout_eliminar = QtWidgets.QFormLayout(grupo_eliminar)

        self.campo_id_eliminar = QtWidgets.QSpinBox()
        self.campo_id_eliminar.setRange(1, 999999)
        layout_eliminar.addRow("Identificador:", self.campo_id_eliminar)

        boton_eliminar = QtWidgets.QPushButton("Eliminar evento")
        boton_eliminar.clicked.connect(self._eliminar_evento)
        layout_eliminar.addRow(boton_eliminar)

        layout_eliminar.addRow(QtWidgets.QLabel(
            "Retira SOLO este evento; sus descendientes en el AVL\n"
            "permanecen activos. El identificador queda retirado y\n"
            "no puede reutilizarse ni reactivarse por reporte."
        ))

        columna_izquierda.addWidget(grupo_eliminar)

        # ---------------- mass archive ----------------
        grupo_archivo = QtWidgets.QGroupBox("Archivar rama de eventos antiguos (sección 10)")
        layout_archivo = QtWidgets.QFormLayout(grupo_archivo)

        self.campo_t_horas = QtWidgets.QDoubleSpinBox()
        self.campo_t_horas.setRange(0.1, 100000.0)
        self.campo_t_horas.setDecimals(1)
        layout_archivo.addRow("T (horas):", self.campo_t_horas)

        boton_configurar_t = QtWidgets.QPushButton("Aplicar T")
        boton_configurar_t.clicked.connect(self._configurar_t)
        layout_archivo.addRow(boton_configurar_t)

        self.campo_w = QtWidgets.QDoubleSpinBox()
        self.campo_r = QtWidgets.QDoubleSpinBox()
        for campo in (self.campo_w, self.campo_r):
            campo.setRange(0.1, 100000.0)
            campo.setDecimals(1)
        self.campo_l = QtWidgets.QSpinBox()
        self.campo_l.setRange(0, 100000)
        layout_archivo.addRow("W (horas):", self.campo_w)
        layout_archivo.addRow("R (km):", self.campo_r)
        layout_archivo.addRow("L (profundidad):", self.campo_l)
        boton_wrl = QtWidgets.QPushButton("Aplicar W, R y L")
        boton_wrl.clicked.connect(self._configurar_w_r_l)
        layout_archivo.addRow(boton_wrl)

        boton_archivar = QtWidgets.QPushButton("Archivar rama elegible")
        boton_archivar.clicked.connect(self._archivar_rama)
        layout_archivo.addRow(boton_archivar)

        layout_archivo.addRow(QtWidgets.QLabel(
            "Elegible: TODO el subárbol tiene prioridad baja y\n"
            "antigüedad > T horas. Entre las ramas elegibles se toma\n"
            "la de más nodos; empates: mayor profundidad de la raíz,\n"
            "luego mayor identificador de la raíz."
        ))

        self.texto_resultado_archivo = QtWidgets.QPlainTextEdit()
        self.texto_resultado_archivo.setReadOnly(True)
        self.texto_resultado_archivo.setMaximumHeight(90)
        layout_archivo.addRow(self.texto_resultado_archivo)

        columna_izquierda.addWidget(grupo_archivo)
        columna_izquierda.addStretch()
        layout_principal.addLayout(columna_izquierda, stretch=1)

        # ---------------- history table ----------------
        columna_derecha = QtWidgets.QVBoxLayout()
        columna_derecha.addWidget(QtWidgets.QLabel("Histórico (archivados y eliminados)"))

        self.tabla = QtWidgets.QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(
            ["ID", "Estado", "Prioridad", "Magnitud", "Revisión", "Fecha del sismo"]
        )
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        columna_derecha.addWidget(self.tabla)

        layout_principal.addLayout(columna_derecha, stretch=2)

        self.refrescar()

    # ---------------- refresh ----------------

    def refrescar(self):
        catalogo = self.escenario.catalogo

        self.campo_t_horas.blockSignals(True)
        self.campo_t_horas.setValue(catalogo.t_horas)
        self.campo_t_horas.blockSignals(False)
        self.campo_w.setValue(catalogo.w_horas)
        self.campo_r.setValue(catalogo.r_km)
        self.campo_l.setValue(catalogo.l_profundidad)

        filas = [(evento, "archivado") for evento in catalogo._archivados.values()]
        filas += [(evento, "eliminado") for evento in catalogo._eliminados.values()]
        filas.sort(key=lambda par: par[0].identificador)

        self.tabla.setRowCount(0)
        for evento, estado in filas:
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)
            valores = [evento.identificador, estado, evento.prioridad, evento.magnitud,
                       evento.revision, evento.fecha_hora]
            for columna, valor in enumerate(valores):
                self.tabla.setItem(fila, columna, QtWidgets.QTableWidgetItem(str(valor)))

    # ---------------- actions ----------------

    def _eliminar_evento(self):
        identificador = self.campo_id_eliminar.value()
        if not self.escenario.catalogo.esta_activo(identificador):
            QtWidgets.QMessageBox.warning(
                self, "No se pudo eliminar",
                f"El identificador {identificador} no corresponde a un evento activo.",
            )
            return

        respuesta = QtWidgets.QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Eliminar el evento {identificador}? Sus descendientes en el AVL seguirán "
            "activos; el identificador queda retirado y no se puede reutilizar.",
        )
        if respuesta != QtWidgets.QMessageBox.Yes:
            return

        try:
            self.escenario.eliminar_evento(identificador)
        except ValidacionError as error:
            QtWidgets.QMessageBox.warning(self, "No se pudo eliminar", str(error))
            return

        self.refrescar()
        self.cambio_realizado.emit()

    def _configurar_t(self):
        try:
            self.escenario.configurar_t_horas(self.campo_t_horas.value())
        except ValidacionError as error:
            QtWidgets.QMessageBox.warning(self, "T inválido", str(error))
            return
        self.refrescar()
        self.cambio_realizado.emit()

    def _configurar_w_r_l(self):
        try:
            self.escenario.configurar_w_r_l(
                self.campo_w.value(), self.campo_r.value(), self.campo_l.value(),
            )
        except ValidacionError as error:
            QtWidgets.QMessageBox.warning(self, "Parámetro inválido", str(error))
            return
        self.refrescar()
        self.cambio_realizado.emit()

    def _archivar_rama(self):
        seleccion = self.escenario.catalogo.seleccionar_rama_antigua(self.escenario.reloj_simulacion)
        if seleccion is None:
            self.texto_resultado_archivo.setPlainText(
                "No hay ninguna rama elegible en este momento (todos los eventos activos "
                "son de prioridad media/alta, o no tienen suficiente antigüedad)."
            )
            return

        identificadores = ", ".join(str(i) for i in seleccion["identificadores"])
        respuesta = QtWidgets.QMessageBox.question(
            self, "Confirmar archivo",
            f"Se archivarán {seleccion['cantidad']} evento(s): {identificadores}.\n"
            f"Criterio: mayor cantidad de nodos ({seleccion['cantidad']}); "
            f"en empate, mayor profundidad de la raíz ({seleccion['profundidad_raiz']}); "
            f"si persiste, mayor identificador de la raíz ({seleccion['id_raiz']}).\n\n"
            "¿Archivar esta rama?",
        )
        if respuesta != QtWidgets.QMessageBox.Yes:
            return

        archivados = self.escenario.archivar_rama_antigua()
        self.texto_resultado_archivo.setPlainText(
            f"Se archivaron {len(archivados)} evento(s): {', '.join(str(i) for i in archivados)}"
        )
        self.refrescar()
        self.cambio_realizado.emit()