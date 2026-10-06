from PySide6 import QtWidgets, QtGui

from .dibujo_arbol import dibujar_en_escena


class PanelComparacionBST(QtWidgets.QWidget):
    """
    Comparative view AVL vs BST (section 15). The displayed BST is
    the one from the last "load by insertions" (section 12, Persistence
    tab) -- both trees were built using the SAME sequence and the SAME
    comparator, which is exactly what makes the comparison valid. The
    AVL being drawn is the current active catalog (which may have
    changed since that load if you performed more operations).
    """

    def __init__(self, escenario, panel_persistencia, parent=None):
        super().__init__(parent)
        self.escenario = escenario
        self.panel_persistencia = panel_persistencia

        layout = QtWidgets.QVBoxLayout(self)

        self.etiqueta_resumen = QtWidgets.QLabel()
        fuente_negrita = self.etiqueta_resumen.font()
        fuente_negrita.setBold(True)
        self.etiqueta_resumen.setFont(fuente_negrita)
        layout.addWidget(self.etiqueta_resumen)

        layout_arboles = QtWidgets.QHBoxLayout()

        columna_avl = QtWidgets.QVBoxLayout()
        columna_avl.addWidget(QtWidgets.QLabel("AVL (catálogo activo actual, balanceado)"))
        self.escena_avl = QtWidgets.QGraphicsScene()
        self.vista_avl = QtWidgets.QGraphicsView(self.escena_avl)
        self.vista_avl.setRenderHint(QtGui.QPainter.Antialiasing)
        columna_avl.addWidget(self.vista_avl)
        layout_arboles.addLayout(columna_avl)

        columna_bst = QtWidgets.QVBoxLayout()
        columna_bst.addWidget(QtWidgets.QLabel("BST (misma secuencia de inserción, SIN balanceo)"))
        self.escena_bst = QtWidgets.QGraphicsScene()
        self.vista_bst = QtWidgets.QGraphicsView(self.escena_bst)
        self.vista_bst.setRenderHint(QtGui.QPainter.Antialiasing)
        columna_bst.addWidget(self.vista_bst)
        layout_arboles.addLayout(columna_bst)

        layout.addLayout(layout_arboles)

        boton_refrescar = QtWidgets.QPushButton("Actualizar comparación")
        boton_refrescar.clicked.connect(self.refrescar)
        layout.addWidget(boton_refrescar)

        self.refrescar()

    def refrescar(self):
        avl = self.escenario.catalogo.avl
        dibujar_en_escena(self.escena_avl, avl.raiz)
        self.vista_avl.setSceneRect(self.escena_avl.itemsBoundingRect().adjusted(-30, -30, 30, 30))

        resumen = self.panel_persistencia.ultimo_resumen_comparacion
        bst = self.panel_persistencia.ultimo_bst_comparacion

        if bst is None:
            self.escena_bst.clear()
            self.escena_bst.addText(
                "(todavía no has hecho una 'carga por inserciones'\nen la pestaña Persistencia)"
            )
            self.etiqueta_resumen.setText(
                f"AVL actual -> altura: {avl.altura_total()}, hojas: {avl.contar_hojas()}, "
                f"nodos: {len(avl)}"
            )
            return

        dibujar_en_escena(self.escena_bst, bst.raiz)
        self.vista_bst.setSceneRect(self.escena_bst.itemsBoundingRect().adjusted(-30, -30, 30, 30))

        self.etiqueta_resumen.setText(
            f"Última carga por inserciones ({resumen['avl']['cantidad']} eventos) -> "
            f"AVL: altura {resumen['avl']['altura']}, hojas {resumen['avl']['hojas']}   |   "
            f"BST: altura {resumen['bst']['altura']}, hojas {resumen['bst']['hojas']}"
        )