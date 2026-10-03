from enum import Enum


class TipoResultadoReporte(Enum):
    ALTA_NUEVA = "alta_nueva"
    ACTUALIZADO = "actualizado"
    CONFIRMADO = "confirmado"
    CONFLICTO = "conflicto"
    ANTIGUO = "antiguo"
    RECHAZADO_INVALIDO = "rechazado_invalido"
    RECHAZADO_ELIMINADO = "rechazado_eliminado"


class ResultadoReporte:
    """
    Resultado de procesar un Reporte contra el Catalogo, según la tabla
    de decisión de la sección 6. `evento` es el evento resultante cuando
    aplica (alta, actualización, confirmación); None en los rechazos.
    """

    def __init__(self, tipo, mensaje, evento=None):
        self.tipo = tipo
        self.mensaje = mensaje
        self.evento = evento

    def __repr__(self):
        return f"ResultadoReporte({self.tipo.value}: {self.mensaje})"