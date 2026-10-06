class Reporte:
    """
    Raw data received from a station (section 6, "Processing
    received reports"). Unlike an Event, a Report is NOT
    validated and its priority is not calculated when it is created:
    it may contain an unknown identifier, repeat a revision, or contain
    data that conflicts with the current event. That decision is made when
    it is processed against the catalog (see Catalogo.procesar_reporte).
    """

    def __init__(self, identificador, magnitud, profundidad, epicentro_x, epicentro_y,
                 fecha_hora, revision, estacion):
        self.identificador = identificador
        self.magnitud = magnitud
        self.profundidad = profundidad
        self.epicentro_x = epicentro_x
        self.epicentro_y = epicentro_y
        self.fecha_hora = fecha_hora
        self.revision = revision
        self.estacion = estacion

    def __repr__(self):
        return f"Reporte(id={self.identificador}, rev={self.revision}, estacion={self.estacion})"