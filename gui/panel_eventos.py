from datetime import datetime

from PySide6 import QtWidgets, QtCore

from core import ValidacionError


class PanelEventos(QtWidgets.QWidget):
    """
    Alta, consulta y corrección manual de eventos (sección 6). Esta
    clase es SOLO interfaz: arma el formulario, pinta la tabla, y llama
    a los métodos de `Escenario` -- nunca valida rangos, calcula
    prioridad, ni toca el AVL directamente. Si una operación falla, el
    propio `Escenario`/`Catalogo` ya devolvió un `ValidacionError` con
    el motivo; aquí solo se muestra en un cuadro de diálogo.
    """

    cambio_realizado = QtCore.Signal()  # para que otras pestañas (ej. el árbol) se refresquen

    def __init__(self, escenario, parent=None):
        super().__init__(parent)
        self.escenario = escenario
        self._identificador_seleccionado = None

        layout_principal = QtWidgets.QHBoxLayout(self)

        # ---------------- columna izquierda: formulario + detalle ----------------
        columna_izquierda = QtWidgets.QVBoxLayout()

        grupo_formulario = QtWidgets.QGroupBox("Alta / corrección de evento")
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

        self.campo_estacion = QtWidgets.QLineEdit()
        self.campo_estacion.setPlaceholderText("EST-01")

        formulario.addRow("Identificador:", self.campo_id)
        formulario.addRow("Magnitud:", self.campo_magnitud)
        formulario.addRow("Profundidad (km):", self.campo_profundidad)
        formulario.addRow("Epicentro x (km):", self.campo_x)
        formulario.addRow("Epicentro y (km):", self.campo_y)
        formulario.addRow("Fecha y hora:", self.campo_fecha)
        formulario.addRow("Estación:", self.campo_estacion)

        fila_botones = QtWidgets.QHBoxLayout()
        self.boton_alta = QtWidgets.QPushButton("Dar de alta")
        self.boton_corregir = QtWidgets.QPushButton("Corregir seleccionado")
        self.boton_limpiar = QtWidgets.QPushButton("Limpiar formulario")
        self.boton_corregir.setEnabled(False)
        fila_botones.addWidget(self.boton_alta)
        fila_botones.addWidget(self.boton_corregir)
        fila_botones.addWidget(self.boton_limpiar)
        formulario.addRow(fila_botones)

        self.boton_alta.clicked.connect(self._dar_de_alta)
        self.boton_corregir.clicked.connect(self._corregir_seleccionado)
        self.boton_limpiar.clicked.connect(self._limpiar_formulario)

        columna_izquierda.addWidget(grupo_formulario)

        grupo_detalle = QtWidgets.QGroupBox("Detalle del evento seleccionado")
        layout_detalle = QtWidgets.QVBoxLayout(grupo_detalle)
        self.texto_detalle = QtWidgets.QPlainTextEdit()
        self.texto_detalle.setReadOnly(True)
        layout_detalle.addWidget(self.texto_detalle)

        self.boton_marcar_revisado = QtWidgets.QPushButton("Marcar revisado")
        self.boton_marcar_revisado.setEnabled(False)
        self.boton_marcar_revisado.clicked.connect(self._marcar_revisado_seleccionado)
        layout_detalle.addWidget(self.boton_marcar_revisado)

        columna_izquierda.addWidget(grupo_detalle)
        layout_principal.addLayout(columna_izquierda, stretch=1)

        # ---------------- columna derecha: tabla de eventos activos ----------------
        columna_derecha = QtWidgets.QVBoxLayout()
        columna_derecha.addWidget(QtWidgets.QLabel("Eventos activos"))

        self.tabla = QtWidgets.QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(
            ["ID", "Prioridad", "Magnitud", "Revisión", "Estado", "Estaciones"]
        )
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tabla.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tabla.itemSelectionChanged.connect(self._seleccion_cambio)

        columna_derecha.addWidget(self.tabla)
        layout_principal.addLayout(columna_derecha, stretch=2)

        self.refrescar()

    # ---------------- refresco ----------------

    def refrescar(self):
        """Vuelve a pintar la tabla desde el Catalogo y actualiza el
        panel de detalle. Se llama después de CUALQUIER acción que
        pudiera haber cambiado el catálogo (incluido un deshacer)."""
        catalogo = self.escenario.catalogo
        eventos = [nodo.elemento for nodo in catalogo._indice_por_id.values()]
        eventos.sort(key=lambda e: e.identificador)

        fila_seleccionada_antes = self._identificador_seleccionado

        self.tabla.blockSignals(True)
        self.tabla.setRowCount(0)
        for evento in eventos:
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)
            valores = [
                evento.identificador, evento.prioridad, evento.magnitud,
                evento.revision, evento.estado_atencion, ", ".join(sorted(evento.estaciones)),
            ]
            for columna, valor in enumerate(valores):
                item = QtWidgets.QTableWidgetItem(str(valor))
                item.setData(QtCore.Qt.UserRole, evento.identificador)
                self.tabla.setItem(fila, columna, item)
            if evento.identificador == fila_seleccionada_antes:
                self.tabla.selectRow(fila)
        self.tabla.blockSignals(False)

        if not catalogo.esta_activo(fila_seleccionada_antes):
            self._identificador_seleccionado = None
            self.boton_corregir.setEnabled(False)
            self.boton_marcar_revisado.setEnabled(False)

        self._actualizar_detalle()

    # ---------------- selección externa (ej. desde la vista del árbol) ----------------

    def seleccionar_por_identificador(self, identificador):
        for fila in range(self.tabla.rowCount()):
            item = self.tabla.item(fila, 0)
            if item is not None and item.data(QtCore.Qt.UserRole) == identificador:
                self.tabla.selectRow(fila)
                return

    # ---------------- selección en la tabla ----------------

    def _seleccion_cambio(self):
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            self._identificador_seleccionado = None
        else:
            item = self.tabla.item(filas[0].row(), 0)
            self._identificador_seleccionado = item.data(QtCore.Qt.UserRole)

        hay_seleccion = self._identificador_seleccionado is not None
        self.boton_corregir.setEnabled(hay_seleccion)
        self.boton_marcar_revisado.setEnabled(hay_seleccion)

        self._actualizar_detalle()
        if hay_seleccion:
            self._cargar_formulario_desde_seleccion()

    def _actualizar_detalle(self):
        if self._identificador_seleccionado is None:
            self.texto_detalle.setPlainText("(sin selección)")
            return

        catalogo = self.escenario.catalogo
        evento, nodos_visitados = catalogo.consultar_evento(self._identificador_seleccionado)
        if evento is None:
            self.texto_detalle.setPlainText("(el evento ya no está activo)")
            return

        nodo = catalogo._indice_por_id[self._identificador_seleccionado]
        profundidad_nodo = catalogo.avl.profundidad(nodo.clave)
        factor_balance = catalogo.avl.factor_balance(nodo)
        referencia_id = catalogo.referencia_de(evento.identificador)

        lineas = [
            f"Identificador: {evento.identificador}",
            f"Clave K: {evento.clave}",
            f"Magnitud: {evento.magnitud}    Profundidad del hipocentro: {evento.profundidad} km",
            f"Epicentro: ({evento.epicentro_x}, {evento.epicentro_y})",
            f"En zona poblada: {'sí' if evento.en_zona_poblada else 'no'}",
            f"Prioridad: {evento.prioridad}    Estado de atención: {evento.estado_atencion}",
            f"Revisión vigente: {evento.revision}",
            f"Estaciones con reportes aceptados: {', '.join(sorted(evento.estaciones)) or '(ninguna)'}",
            f"Asociado como réplica de: {referencia_id if referencia_id is not None else '(sin asociación)'}",
            "",
            f"Profundidad del nodo en el AVL: {profundidad_nodo}",
            f"Altura del nodo: {nodo.altura}    Factor de balance: {factor_balance}",
            f"Nodos visitados en la búsqueda por clave: {nodos_visitados}",
        ]
        self.texto_detalle.setPlainText("\n".join(lineas))

    def _cargar_formulario_desde_seleccion(self):
        evento, _ = self.escenario.catalogo.consultar_evento(self._identificador_seleccionado)
        if evento is None:
            return
        self.campo_id.setValue(evento.identificador)
        self.campo_id.setEnabled(False)  # el identificador es inmutable al corregir
        self.campo_magnitud.setValue(evento.magnitud)
        self.campo_profundidad.setValue(evento.profundidad)
        self.campo_x.setValue(evento.epicentro_x)
        self.campo_y.setValue(evento.epicentro_y)
        fecha = QtCore.QDate(evento.fecha_hora.year, evento.fecha_hora.month, evento.fecha_hora.day)
        hora = QtCore.QTime(evento.fecha_hora.hour, evento.fecha_hora.minute, evento.fecha_hora.second)
        self.campo_fecha.setDate(fecha)
        self.campo_fecha.setTime(hora)
        self.campo_estacion.setEnabled(False)  # no aplica al corregir (la estación va en los reportes)

    def _limpiar_formulario(self):
        self.tabla.clearSelection()
        self._identificador_seleccionado = None
        self.campo_id.setEnabled(True)
        self.campo_estacion.setEnabled(True)
        self.campo_id.setValue(self.campo_id.minimum())
        self.campo_magnitud.setValue(0.0)
        self.campo_profundidad.setValue(0.0)
        self.campo_x.setValue(0.0)
        self.campo_y.setValue(0.0)
        self.campo_estacion.clear()
        self.boton_corregir.setEnabled(False)
        self.boton_marcar_revisado.setEnabled(False)
        self._actualizar_detalle()

    # ---------------- acciones ----------------

    def _fecha_hora_del_formulario(self):
        qdt = self.campo_fecha.dateTime()
        return datetime(qdt.date().year(), qdt.date().month(), qdt.date().day(),
                         qdt.time().hour(), qdt.time().minute(), qdt.time().second())

    def _dar_de_alta(self):
        estacion = self.campo_estacion.text().strip() or "EST-01"
        try:
            self.escenario.alta_evento(
                self.campo_id.value(), self.campo_magnitud.value(), self.campo_profundidad.value(),
                self.campo_x.value(), self.campo_y.value(),
                self._fecha_hora_del_formulario(), estacion,
            )
        except ValidacionError as error:
            QtWidgets.QMessageBox.warning(self, "No se pudo dar de alta", str(error))
            return
        self.refrescar()
        self.cambio_realizado.emit()

    def _corregir_seleccionado(self):
        if self._identificador_seleccionado is None:
            return
        try:
            self.escenario.corregir_evento(
                self._identificador_seleccionado,
                magnitud=self.campo_magnitud.value(),
                profundidad=self.campo_profundidad.value(),
                epicentro_x=self.campo_x.value(),
                epicentro_y=self.campo_y.value(),
                fecha_hora=self._fecha_hora_del_formulario(),
            )
        except ValidacionError as error:
            QtWidgets.QMessageBox.warning(self, "No se pudo corregir", str(error))
            return
        self.refrescar()
        self.cambio_realizado.emit()

    def _marcar_revisado_seleccionado(self):
        if self._identificador_seleccionado is None:
            return
        try:
            self.escenario.marcar_revisado(self._identificador_seleccionado)
        except ValidacionError as error:
            QtWidgets.QMessageBox.warning(self, "No se pudo marcar como revisado", str(error))
            return
        self.refrescar()