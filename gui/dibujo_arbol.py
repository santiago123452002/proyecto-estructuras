from PySide6 import QtWidgets, QtGui

RADIO_NODO = 16
ESPACIO_X = 44
ESPACIO_Y = 60

COLOR_PRIORIDAD = {
    1: QtGui.QColor("#8fbc8f"),
    2: QtGui.QColor("#f0ad4e"),
    3: QtGui.QColor("#d9534f"),
}


def dibujar_en_escena(escena, raiz):
    """
    Draws any binary tree (any object with .izquierdo, .derecho, and
    .elemento.identificador/.elemento.prioridad attributes, such as an
    AVLTree or BSTTree node) in the given Qt scene. It is used both in the
    AVL-vs-BST comparison view and in any other tree thumbnail that may be
    needed later. This avoids repeating the positioning logic (in-order =
    x, depth = y) in different places.
    """
    escena.clear()
    if raiz is None:
        escena.addText("(árbol vacío)")
        return

    posiciones = {}
    contador = [0]

    def calcular(nodo, profundidad):
        if nodo is None:
            return
        calcular(nodo.izquierdo, profundidad + 1)
        posiciones[nodo] = (contador[0], profundidad)
        contador[0] += 1
        calcular(nodo.derecho, profundidad + 1)

    calcular(raiz, 0)

    def dibujar_lineas(nodo):
        if nodo is None:
            return
        x1, y1 = posiciones[nodo]
        for hijo in (nodo.izquierdo, nodo.derecho):
            if hijo is not None:
                x2, y2 = posiciones[hijo]
                escena.addLine(
                    x1 * ESPACIO_X, y1 * ESPACIO_Y, x2 * ESPACIO_X, y2 * ESPACIO_Y,
                    QtGui.QPen(QtGui.QColor("#888888"), 2),
                )
        dibujar_lineas(nodo.izquierdo)
        dibujar_lineas(nodo.derecho)

    dibujar_lineas(raiz)

    for nodo, (x, y) in posiciones.items():
        color = COLOR_PRIORIDAD.get(nodo.elemento.prioridad, QtGui.QColor("#cccccc"))
        item = escena.addEllipse(
            -RADIO_NODO, -RADIO_NODO, RADIO_NODO * 2, RADIO_NODO * 2,
            QtGui.QPen(QtGui.QColor("#222222"), 2), QtGui.QBrush(color),
        )
        item.setPos(x * ESPACIO_X, y * ESPACIO_Y)
        item.setZValue(1)

        etiqueta = escena.addText(str(nodo.elemento.identificador))
        rect_texto = etiqueta.boundingRect()
        etiqueta.setPos(x * ESPACIO_X - rect_texto.width() / 2, y * ESPACIO_Y - rect_texto.height() / 2)
        etiqueta.setZValue(2)