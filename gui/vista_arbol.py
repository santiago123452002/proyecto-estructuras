from PySide6 import QtWidgets, QtGui, QtCore

RADIO_NODO = 22
ESPACIO_X = 60
ESPACIO_Y = 80

COLOR_PRIORIDAD = {
    1: QtGui.QColor("#8fbc8f"),   # baja: verde suave
    2: QtGui.QColor("#f0ad4e"),   # media: naranja
    3: QtGui.QColor("#d9534f"),   # alta: rojo
}


class _NodoGrafico(QtWidgets.QGraphicsEllipseItem):
    """Clickable circle representing an AVL node in the scene."""

    def __init__(self, identificador, x, y, radio, color, acceso_costoso, al_hacer_clic):
        super().__init__(-radio, -radio, radio * 2, radio * 2)
        self.identificador = identificador
        self._al_hacer_clic = al_hacer_clic
        self.setPos(x, y)
        self.setBrush(QtGui.QBrush(color))

        pluma = QtGui.QPen(QtGui.QColor("#222222"), 2)
        if acceso_costoso:
            # Marks a "costly access" (Section 9): a visual feature DISTINCT from
            # the color (which already encodes priority), so both signals are not
            # confused — dashed, black, and thicker border.
            pluma.setStyle(QtCore.Qt.DashLine)
            pluma.setColor(QtGui.QColor("#000000"))
            pluma.setWidth(3)
        self.setPen(pluma)

        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setZValue(1)
        self.setToolTip(f"Evento {identificador}")

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self._al_hacer_clic is not None:
            self._al_hacer_clic(self.identificador)


class VistaArbolAVL(QtWidgets.QWidget):
    """
    Draws the active AVL tree exactly as it currently exists: the horizontal
    position of each node follows the in-order traversal (matching the
    ascending order of K), while the vertical position represents its actual
    depth. This way, the image shows the real topology rather than an
    invented "pretty" layout.

    The COLOR represents the priority; a thicker dashed border marks the
    "costly access" from Section 9. These are intentionally two different
    visual signals, as required by the specification.
    """

    nodo_seleccionado = QtCore.Signal(int)

    def __init__(self, escenario, parent=None):
        super().__init__(parent)
        self.escenario = escenario

        layout = QtWidgets.QVBoxLayout(self)

        fila_superior = QtWidgets.QHBoxLayout()
        self.etiqueta_estado = QtWidgets.QLabel()
        fila_superior.addWidget(self.etiqueta_estado)
        fila_superior.addStretch()

        boton_recuperar = QtWidgets.QPushButton("Recuperar equilibrio")
        boton_recuperar.clicked.connect(self._recuperar_equilibrio)
        fila_superior.addWidget(boton_recuperar)

        boton_verificar = QtWidgets.QPushButton("Verificar estructura")
        boton_verificar.clicked.connect(self._verificar_estructura)
        fila_superior.addWidget(boton_verificar)

        layout.addLayout(fila_superior)

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
        leyenda.addWidget(QtWidgets.QLabel("Borde punteado grueso = acceso costoso (sección 9)"))
        leyenda.addStretch()
        layout.addLayout(leyenda)

        self.escena = QtWidgets.QGraphicsScene()
        self.vista = QtWidgets.QGraphicsView(self.escena)
        self.vista.setRenderHint(QtGui.QPainter.Antialiasing)
        layout.addWidget(self.vista)

        self.refrescar()

    def refrescar(self):
        catalogo = self.escenario.catalogo
        avl = catalogo.avl

        balanceado = catalogo.esta_balanceado()
        self.etiqueta_estado.setText(
            f"Nodos: {len(avl)}    Altura: {avl.altura_total()}    "
            f"Balanceado: {'sí' if balanceado else 'NO (modo estrés o pendiente de recuperar)'}"
        )

        self.escena.clear()
        if avl.raiz is None:
            self.escena.addText("(árbol vacío — da de alta algún evento primero)")
            return

        accesos_costosos, _ = catalogo.eventos_prioridad_alta_con_acceso_costoso()
        ids_acceso_costoso = {entrada["identificador"] for entrada in accesos_costosos}

        posiciones = {}
        contador = [0]

        def calcular_posiciones(nodo, profundidad):
            if nodo is None:
                return
            calcular_posiciones(nodo.izquierdo, profundidad + 1)
            posiciones[nodo] = (contador[0], profundidad)
            contador[0] += 1
            calcular_posiciones(nodo.derecho, profundidad + 1)

        calcular_posiciones(avl.raiz, 0)

        def dibujar_lineas(nodo):
            if nodo is None:
                return
            x1, y1 = posiciones[nodo]
            for hijo in (nodo.izquierdo, nodo.derecho):
                if hijo is not None:
                    x2, y2 = posiciones[hijo]
                    self.escena.addLine(
                        x1 * ESPACIO_X, y1 * ESPACIO_Y,
                        x2 * ESPACIO_X, y2 * ESPACIO_Y,
                        QtGui.QPen(QtGui.QColor("#888888"), 2),
                    )
            dibujar_lineas(nodo.izquierdo)
            dibujar_lineas(nodo.derecho)

        dibujar_lineas(avl.raiz)  # las líneas van primero, para quedar detrás de los nodos

        for nodo, (x, y) in posiciones.items():
            evento = nodo.elemento
            color = COLOR_PRIORIDAD.get(evento.prioridad, QtGui.QColor("#cccccc"))
            acceso_costoso = evento.identificador in ids_acceso_costoso

            item = _NodoGrafico(
                evento.identificador, x * ESPACIO_X, y * ESPACIO_Y, RADIO_NODO,
                color, acceso_costoso, self._nodo_clicado,
            )
            self.escena.addItem(item)

            etiqueta = self.escena.addText(str(evento.identificador))
            etiqueta.setDefaultTextColor(QtGui.QColor("#000000"))
            rect_texto = etiqueta.boundingRect()
            etiqueta.setPos(x * ESPACIO_X - rect_texto.width() / 2,
                             y * ESPACIO_Y - rect_texto.height() / 2)
            etiqueta.setZValue(2)

        self.vista.setSceneRect(self.escena.itemsBoundingRect().adjusted(-40, -40, 40, 40))

    def _nodo_clicado(self, identificador):
        self.nodo_seleccionado.emit(identificador)

    def _recuperar_equilibrio(self):
        balanceado = self.escenario.recuperar_equilibrio()
        self.refrescar()
        QtWidgets.QMessageBox.information(
            self, "Recuperar equilibrio",
            "El árbol quedó balanceado." if balanceado
            else "El árbol sigue sin balancear (revisa 'Verificar estructura').",
        )

    def _verificar_estructura(self):
        reporte = self.escenario.catalogo.verificar_estructura(modo=self.escenario.modo)
        if reporte["ok"]:
            texto = "No se encontraron errores de estructura."
            if reporte.get("desbalances_esperados"):
                texto += (f"\n\n{len(reporte['desbalances_esperados'])} nodo(s) con desbalance "
                          "esperado en modo estrés (no es un error).")
        else:
            texto = "Se encontraron problemas:\n\n" + "\n".join(f"• {error}" for error in reporte["errores"])
        QtWidgets.QMessageBox.information(self, "Verificar estructura", texto)