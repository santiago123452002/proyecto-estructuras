from PySide6 import QtWidgets, QtCore

from core import ValidacionError


class PanelPersistencia(QtWidgets.QWidget):
    """
    Persistencia en JSON (sección 12): guardado estructural completo, y
    los dos modos de carga (por topología y por inserciones). Todo pasa
    por Escenario, que ya se ocupa de leer el archivo, validar todo, y
    conservar el escenario anterior si la carga falla -- esta clase solo
    abre los diálogos de archivo y muestra el resultado.
    """

    cambio_realizado = QtCore.Signal()

    def __init__(self, escenario, parent=None):
        super().__init__(parent)
        self.escenario = escenario
        self.ultimo_resumen_comparacion = None
        self.ultimo_bst_comparacion = None

        layout = QtWidgets.QVBoxLayout(self)

        grupo_guardar = QtWidgets.QGroupBox("Guardado estructural completo")
        layout_guardar = QtWidgets.QVBoxLayout(grupo_guardar)
        layout_guardar.addWidget(QtWidgets.QLabel(
            "Guarda la topología real del árbol activo, el histórico, la cola,\n"
            "el reloj, las zonas, los parámetros, el modo y las métricas."
        ))
        boton_guardar = QtWidgets.QPushButton("Guardar escenario como JSON...")
        boton_guardar.clicked.connect(self._guardar)
        layout_guardar.addWidget(boton_guardar)
        layout.addWidget(grupo_guardar)

        grupo_topologia = QtWidgets.QGroupBox("Carga por topología")
        layout_topologia = QtWidgets.QVBoxLayout(grupo_topologia)
        layout_topologia.addWidget(QtWidgets.QLabel(
            "Reemplaza TODO el escenario actual con lo que hay en el archivo,\n"
            "validando orden, alturas, factores de balance y prioridades.\n"
            "Si el archivo es inválido, el escenario actual NO se modifica."
        ))
        boton_topologia = QtWidgets.QPushButton("Cargar por topología...")
        boton_topologia.clicked.connect(self._cargar_por_topologia)
        layout_topologia.addWidget(boton_topologia)
        layout.addWidget(grupo_topologia)

        grupo_inserciones = QtWidgets.QGroupBox("Carga por inserciones (comparación AVL vs BST)")
        layout_inserciones = QtWidgets.QVBoxLayout(grupo_inserciones)
        layout_inserciones.addWidget(QtWidgets.QLabel(
            "Reemplaza el catálogo activo (NO el histórico ni la cola) insertando\n"
            "una secuencia de eventos, en orden, en un AVL nuevo y en un BST de\n"
            "comparación con el mismo comparador."
        ))
        boton_inserciones = QtWidgets.QPushButton("Cargar por inserciones...")
        boton_inserciones.clicked.connect(self._cargar_por_inserciones)
        layout_inserciones.addWidget(boton_inserciones)

        self.texto_comparacion = QtWidgets.QPlainTextEdit()
        self.texto_comparacion.setReadOnly(True)
        self.texto_comparacion.setPlaceholderText(
            "Aquí se muestra la comparación de altura y hojas entre el AVL y el "
            "BST después de una carga por inserciones."
        )
        layout_inserciones.addWidget(self.texto_comparacion)

        layout.addWidget(grupo_inserciones)
        layout.addStretch()

    def refrescar(self):
        """Este panel no muestra ningún estado que cambie por acciones
        de otras pestañas (solo botones y el último resultado de
        comparación); existe por uniformidad con el resto de paneles."""
        pass

    # ---------------- guardar ----------------

    def _guardar(self):
        ruta, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Guardar escenario", "escenario.json", "Archivos JSON (*.json)"
        )
        if not ruta:
            return
        try:
            self.escenario.guardar_json(ruta)
        except OSError as error:
            QtWidgets.QMessageBox.warning(self, "No se pudo guardar", str(error))
            return
        QtWidgets.QMessageBox.information(self, "Guardado", f"Escenario guardado en:\n{ruta}")

    # ---------------- carga por topología ----------------

    def _cargar_por_topologia(self):
        ruta, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Cargar por topología", "", "Archivos JSON (*.json)"
        )
        if not ruta:
            return
        try:
            self.escenario.cargar_por_topologia(ruta)
        except ValidacionError as error:
            QtWidgets.QMessageBox.warning(
                self, "Archivo inválido",
                f"No se cargó el archivo (el escenario actual no se modificó):\n\n{error}",
            )
            return
        except Exception as error:  # JSON mal formado, archivo no encontrado, etc.
            QtWidgets.QMessageBox.warning(self, "No se pudo leer el archivo", str(error))
            return

        QtWidgets.QMessageBox.information(
            self, "Escenario cargado",
            "Se reemplazó el escenario completo con el contenido del archivo.",
        )
        self.cambio_realizado.emit()

    # ---------------- carga por inserciones ----------------

    def _cargar_por_inserciones(self):
        ruta, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Cargar por inserciones", "", "Archivos JSON (*.json)"
        )
        if not ruta:
            return
        try:
            resumen, bst = self.escenario.cargar_por_inserciones(ruta)
        except ValidacionError as error:
            QtWidgets.QMessageBox.warning(self, "Archivo inválido", str(error))
            return
        except Exception as error:
            QtWidgets.QMessageBox.warning(self, "No se pudo leer el archivo", str(error))
            return

        self.ultimo_resumen_comparacion = resumen
        self.ultimo_bst_comparacion = bst

        texto = (
            f"AVL -> raíz: {resumen['avl']['raiz']}, altura: {resumen['avl']['altura']}, "
            f"hojas: {resumen['avl']['hojas']}, nodos: {resumen['avl']['cantidad']}\n"
            f"BST -> raíz: {resumen['bst']['raiz']}, altura: {resumen['bst']['altura']}, "
            f"hojas: {resumen['bst']['hojas']}, nodos: {resumen['bst']['cantidad']}"
        )
        self.texto_comparacion.setPlainText(texto)
        self.cambio_realizado.emit()
