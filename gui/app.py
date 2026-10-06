import sys

from PySide6 import QtWidgets

from core import Escenario

from .dialogo_nuevo_escenario import DialogoNuevoEscenario
from .ventana_principal import VentanaPrincipal


def ejecutar():
    app = QtWidgets.QApplication(sys.argv)

    dialogo = DialogoNuevoEscenario()
    if dialogo.exec() != QtWidgets.QDialog.Accepted:
        return

    escenario = Escenario(
        zonas=dialogo.zonas_definidas(),
        reloj_simulacion=dialogo.reloj_seleccionado(),
    )

    ventana = VentanaPrincipal(escenario)
    ventana.show()

    sys.exit(app.exec())
