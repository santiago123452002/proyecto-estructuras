from datetime import datetime

from PySide6 import QtWidgets, QtCore

from core import ValidacionError


class PanelConsultas(QtWidgets.QWidget):
    """Section 11 queries. Reads the catalog and reports nodes visited."""

    def __init__(self, escenario, parent=None):
        super().__init__(parent)
        self.escenario = escenario

        layout = QtWidgets.QVBoxLayout(self)

        fila_k = QtWidgets.QHBoxLayout()
        self.campo_k = QtWidgets.QSpinBox()
        self.campo_k.setRange(1, 999999)
        self.campo_k.setValue(5)
        boton_k = QtWidgets.QPushButton("Pendientes top-k")
        boton_k.clicked.connect(self._pendientes)
        fila_k.addWidget(QtWidgets.QLabel("k:"))
        fila_k.addWidget(self.campo_k)
        fila_k.addWidget(boton_k)
        fila_k.addStretch()
        layout.addLayout(fila_k)

        fila_filtros = QtWidgets.QHBoxLayout()
        self.usar_magnitud = QtWidgets.QCheckBox("Magnitud")
        self.campo_mag_min = QtWidgets.QDoubleSpinBox()
        self.campo_mag_max = QtWidgets.QDoubleSpinBox()
        for campo in (self.campo_mag_min, self.campo_mag_max):
            campo.setRange(-2.0, 10.0)
            campo.setDecimals(1)
        self.campo_mag_min.setValue(-2.0)
        self.campo_mag_max.setValue(10.0)
        self.usar_profundidad = QtWidgets.QCheckBox("H máx.")
        self.campo_profundidad = QtWidgets.QDoubleSpinBox()
        self.campo_profundidad.setRange(0.0, 700.0)
        self.campo_profundidad.setDecimals(1)
        self.campo_profundidad.setValue(700.0)
        self.usar_fechas = QtWidgets.QCheckBox("Fechas")
        self.campo_fecha_ini = QtWidgets.QDateTimeEdit(QtCore.QDateTime.currentDateTime())
        self.campo_fecha_fin = QtWidgets.QDateTimeEdit(QtCore.QDateTime.currentDateTime())
        for campo in (self.campo_fecha_ini, self.campo_fecha_fin):
            campo.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            campo.setCalendarPopup(True)
        boton_filtros = QtWidgets.QPushButton("Buscar por filtros")
        boton_filtros.clicked.connect(self._filtros)
        fila_filtros.addWidget(self.usar_magnitud)
        fila_filtros.addWidget(self.campo_mag_min)
        fila_filtros.addWidget(self.campo_mag_max)
        fila_filtros.addWidget(self.usar_profundidad)
        fila_filtros.addWidget(self.campo_profundidad)
        fila_filtros.addWidget(self.usar_fechas)
        fila_filtros.addWidget(self.campo_fecha_ini)
        fila_filtros.addWidget(self.campo_fecha_fin)
        fila_filtros.addWidget(boton_filtros)
        layout.addLayout(fila_filtros)

        fila_id = QtWidgets.QHBoxLayout()
        self.campo_id = QtWidgets.QSpinBox()
        self.campo_id.setRange(1, 999999)
        boton_asoc = QtWidgets.QPushButton("Asociaciones")
        boton_asoc.clicked.connect(self._asociaciones)
        boton_costoso = QtWidgets.QPushButton("Acceso costoso")
        boton_costoso.clicked.connect(self._acceso_costoso)
        fila_id.addWidget(QtWidgets.QLabel("ID:"))
        fila_id.addWidget(self.campo_id)
        fila_id.addWidget(boton_asoc)
        fila_id.addWidget(boton_costoso)
        fila_id.addStretch()
        layout.addLayout(fila_id)

        self.texto = QtWidgets.QPlainTextEdit()
        self.texto.setReadOnly(True)
        layout.addWidget(self.texto)

    def refrescar(self):
        pass

    def _fecha(self, campo):
        qdt = campo.dateTime()
        return datetime(qdt.date().year(), qdt.date().month(), qdt.date().day(),
                        qdt.time().hour(), qdt.time().minute(), qdt.time().second())

    def _mostrar(self, titulo, lineas, visitados):
        cuerpo = "\n".join(lineas) if lineas else "(sin resultados)"
        self.texto.setPlainText(f"{titulo}\nNodos del AVL examinados: {visitados}\n\n{cuerpo}")

    def _pendientes(self):
        try:
            eventos, visitados = self.escenario.catalogo.pendientes_top_k(self.campo_k.value())
        except ValidacionError as error:
            QtWidgets.QMessageBox.warning(self, "Consulta", str(error))
            return
        lineas = [f"ID {e.identificador}  K={e.clave}  {e.estado_atencion}" for e in eventos]
        self._mostrar(f"Primeros {self.campo_k.value()} pendientes por K descendente", lineas, visitados)

    def _filtros(self):
        magnitud_min = self.campo_mag_min.value() if self.usar_magnitud.isChecked() else None
        magnitud_max = self.campo_mag_max.value() if self.usar_magnitud.isChecked() else None
        profundidad_max = self.campo_profundidad.value() if self.usar_profundidad.isChecked() else None
        fecha_inicio = self._fecha(self.campo_fecha_ini) if self.usar_fechas.isChecked() else None
        fecha_fin = self._fecha(self.campo_fecha_fin) if self.usar_fechas.isChecked() else None
        eventos, visitados = self.escenario.catalogo.buscar_por_filtros(
            magnitud_min=magnitud_min, magnitud_max=magnitud_max,
            profundidad_max=profundidad_max, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
        )
        lineas = [
            f"ID {e.identificador}  M={e.magnitud}  H={e.profundidad}  {e.fecha_hora}"
            for e in eventos
        ]
        self._mostrar("Eventos dentro de los filtros", lineas, visitados)

    def _asociaciones(self):
        identificador = self.campo_id.value()
        try:
            info = self.escenario.catalogo.consultar_asociaciones(identificador)
        except ValidacionError as error:
            QtWidgets.QMessageBox.warning(self, "Consulta", str(error))
            return
        candidatos = ", ".join(
            f"{c['identificador']} ({c['estado']})" for c in info["candidatos"]
        ) or "(ninguno)"
        referencia = info["referencia"]
        referencia_txt = (
            f"{referencia['identificador']} ({referencia['estado']})" if referencia else "(sin asociación)"
        )
        usan = ", ".join(
            f"{c['identificador']} ({c['estado']})" for c in info["referenciado_por"]
        ) or "(ninguno)"
        activos = len(self.escenario.catalogo)
        self.texto.setPlainText(
            f"Asociaciones del evento {identificador}\n"
            f"Nodos del AVL examinados: la consulta usa identidades, no un recorrido por K "
            f"({activos} eventos activos en el árbol).\n\n"
            f"Candidatos: {candidatos}\n"
            f"Referencia elegida: {referencia_txt}\n"
            f"Eventos que lo usan como referencia: {usan}"
        )

    def _acceso_costoso(self):
        entradas, visitados = self.escenario.catalogo.eventos_prioridad_alta_con_acceso_costoso()
        lineas = [
            f"ID {e['identificador']}  profundidad {e['profundidad']} > L={e['limite']}  "
            f"nodos visitados por clave: {e['nodos_visitados']}"
            for e in entradas
        ]
        self._mostrar("Prioridad alta con acceso costoso", lineas, visitados)
