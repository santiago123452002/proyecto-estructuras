from PySide6 import QtWidgets, QtGui, QtCore

ESCALA = 0.6  # píxeles por km (el plano va de 0 a 1000 km -> 600 px)
RADIO_EVENTO = 8

COLOR_PRIORIDAD = {
    1: QtGui.QColor("#8fbc8f"),
    2: QtGui.QColor("#f0ad4e"),
    3: QtGui.QColor("#d9534f"),
}

COLOR_ZONA_POBLADA = QtGui.QColor(217, 83, 79, 45)
COLOR_ZONA_NO_POBLADA = QtGui.QColor(90, 90, 90, 30)


class _PuntoEvento(QtWidgets.QGraphicsEllipseItem):
    """Círculo clicable que representa un evento en el plano, ubicado en
    su epicentro real."""

    def __init__(self, identificador, x, y, radio, color, al_hacer_clic):
        super().__init__(-radio, -radio, radio * 2, radio * 2)
        self.identificador = identificador
        self._al_hacer_clic = al_hacer_clic
        self.setPos(x, y)
        self.setBrush(QtGui.QBrush(color))
        self.setPen(QtGui.QPen(QtGui.QColor("#000000"), 1.5))
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setZValue(2)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self._al_hacer_clic is not None:
            self._al_hacer_clic(self.identificador)


class PanelPlano(QtWidgets.QWidget):
    """
    Plano geográfico del escenario (sección 15): las zonas (rectángulos
    de 0 a 1000 km en ambos ejes, fijas durante toda la ejecución) y los
    eventos activos ubicados en su epicentro real, coloreados por
    prioridad -- el mismo código de color que la vista del árbol, para
    que sea consistente en toda la aplicación.
    """

    evento_seleccionado = QtCore.Signal(int)

    def __init__(self, escenario, parent=None):
        super().__init__(parent)
        self.escenario = escenario

        layout = QtWidgets.QVBoxLayout(self)

        leyenda = QtWidgets.QHBoxLayout()
        leyenda.addWidget(QtWidgets.QLabel("Prioridad:"))
        for prioridad, nombre in ((3, "Alta"), (2, "Media"), (1, "Baja")):
            cuadro = QtWidgets.QLabel(f"  {nombre}  ")
            cuadro.setStyleSheet(
                f"background-color: {COLOR_PRIORIDAD[prioridad].name()};"
                "border: 1px solid #222; border-radius: 4px;"
            )
            leyenda.addWidget(cuadro)
        leyenda.addSpacing(20)
        leyenda.addWidget(QtWidgets.QLabel("Sombreado rojo = zona poblada"))
        leyenda.addStretch()

        boton_refrescar = QtWidgets.QPushButton("Actualizar")
        boton_refrescar.clicked.connect(self.refrescar)
        leyenda.addWidget(boton_refrescar)
        layout.addLayout(leyenda)

        self.escena = QtWidgets.QGraphicsScene()
        self.vista = QtWidgets.QGraphicsView(self.escena)
        self.vista.setRenderHint(QtGui.QPainter.Antialiasing)
        layout.addWidget(self.vista)

        self.refrescar()

    def refrescar(self):
        self.escena.clear()

        # marco del plano completo (0..1000 km en ambos ejes, sección 3)
        self.escena.addRect(
            0, 0, 1000 * ESCALA, 1000 * ESCALA, QtGui.QPen(QtGui.QColor("#333333"), 2)
        )

        for zona in self.escenario.zonas:
            color = COLOR_ZONA_POBLADA if zona.poblada else COLOR_ZONA_NO_POBLADA
            rect = self.escena.addRect(
                zona.x_min * ESCALA, zona.y_min * ESCALA,
                (zona.x_max - zona.x_min) * ESCALA, (zona.y_max - zona.y_min) * ESCALA,
                QtGui.QPen(QtGui.QColor("#555555"), 1), QtGui.QBrush(color),
            )
            rect.setZValue(0)
            etiqueta = self.escena.addText(zona.nombre)
            etiqueta.setDefaultTextColor(QtGui.QColor("#333333"))
            etiqueta.setPos(zona.x_min * ESCALA + 4, zona.y_min * ESCALA + 2)
            etiqueta.setZValue(1)

        for nodo in self.escenario.catalogo._indice_por_id.values():
            evento = nodo.elemento
            color = COLOR_PRIORIDAD.get(evento.prioridad, QtGui.QColor("#cccccc"))
            item = _PuntoEvento(
                evento.identificador, evento.epicentro_x * ESCALA, evento.epicentro_y * ESCALA,
                RADIO_EVENTO, color, self._evento_clicado,
            )
            item.setToolTip(
                f"Evento {evento.identificador} — M{evento.magnitud}, "
                f"epicentro ({evento.epicentro_x}, {evento.epicentro_y})"
            )
            self.escena.addItem(item)

        if self.escenario.zonas:
            self.vista.setSceneRect(self.escena.itemsBoundingRect().adjusted(-20, -20, 20, 20))
        else:
            self.vista.setSceneRect(-20, -20, 1000 * ESCALA + 40, 1000 * ESCALA + 40)

    def _evento_clicado(self, identificador):
        self.evento_seleccionado.emit(identificador)