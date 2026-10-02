class Reporte:
    """
    Datos crudos que llegan de una estación (sección 6, "Procesamiento de
    reportes recibidos"). A diferencia de un Evento, un Reporte NO se
    valida ni se le calcula prioridad al crearlo: puede traer un
    identificador desconocido, repetir una revisión, o traer datos que
    entran en conflicto con el evento vigente. Esa decisión se toma al
    procesarlo contra el catálogo (ver Catalogo.procesar_reporte).
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