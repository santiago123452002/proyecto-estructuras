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
    Result of processing a Report against the Catalog, according to the decision table
    in Section 6. `evento` is the resulting event when applicable (new event, update,
    or confirmation); None for rejected reports.
    """

    def __init__(self, tipo, mensaje, evento=None):
        self.tipo = tipo
        self.mensaje = mensaje
        self.evento = evento

    def __repr__(self):
        return f"ResultadoReporte({self.tipo.value}: {self.mensaje})"