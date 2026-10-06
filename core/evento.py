from .prioridad import calcular_prioridad

RANGO_MAGNITUD = (-2.0, 10.0)
RANGO_PROFUNDIDAD = (0.0, 700.0)
RANGO_COORDENADA = (0.0, 1000.0)


class ValidacionError(Exception):
    """Raised when any data from an event or operation
    violates a mandatory rule from the statement."""
    pass


def _con_un_decimal(valor, nombre):
    redondeado = round(float(valor), 1)
    if abs(redondeado - valor) > 1e-6:
        raise ValidacionError(f"{nombre} debe tener máximo un decimal.")
    return redondeado


class Evento:
    """
    Active seismic event (section 3). The key K = (priority, magnitude,
    identifier) is ALWAYS derived from the current data through
    `actualizar_prioridad`; it is never assigned directly.
    """

    def __init__(self, identificador, magnitud, profundidad, epicentro_x, epicentro_y,
                 fecha_hora, estacion_origen, revision=1):
        self.identificador = self._validar_identificador(identificador)
        self.magnitud = self._validar_magnitud(magnitud)
        self.profundidad = self._validar_profundidad(profundidad)
        self.epicentro_x = self._validar_coordenada(epicentro_x, "x")
        self.epicentro_y = self._validar_coordenada(epicentro_y, "y")
        self.fecha_hora = fecha_hora  # datetime in UTC
        self.revision = revision
        self.estaciones = {estacion_origen}
        self.estado_atencion = "pendiente"
        self.en_zona_poblada = False   # set by actualizar_prioridad
        self.prioridad = None          # same

    # ---------------- validations (section 3) ----------------

    @staticmethod
    def _validar_identificador(identificador):
        if not isinstance(identificador, int) or not (1 <= identificador <= 999999):
            raise ValidacionError("El identificador debe ser un entero entre 1 y 999999.")
        return identificador

    @staticmethod
    def _validar_magnitud(magnitud):
        if not (RANGO_MAGNITUD[0] <= magnitud <= RANGO_MAGNITUD[1]):
            raise ValidacionError("La magnitud debe estar entre -2.0 y 10.0.")
        return _con_un_decimal(magnitud, "La magnitud")

    @staticmethod
    def _validar_profundidad(profundidad):
        if not (RANGO_PROFUNDIDAD[0] <= profundidad <= RANGO_PROFUNDIDAD[1]):
            raise ValidacionError("La profundidad debe estar entre 0.0 y 700.0 km.")
        return _con_un_decimal(profundidad, "La profundidad")

    @staticmethod
    def _validar_coordenada(valor, nombre_eje):
        if not (RANGO_COORDENADA[0] <= valor <= RANGO_COORDENADA[1]):
            raise ValidacionError(f"La coordenada {nombre_eje} debe estar entre 0.0 y 1000.0 km.")
        return _con_un_decimal(valor, f"La coordenada {nombre_eje}")

    # ---------------- priority and key ----------------

    def actualizar_prioridad(self, en_zona_poblada):
        """Recalculates P from the current data. It must always be called
        whenever magnitude, depth, or epicenter changes."""
        self.en_zona_poblada = en_zona_poblada
        self.prioridad = calcular_prioridad(self.magnitud, self.profundidad, en_zona_poblada)
        return self.prioridad

    @property
    def clave(self):
        if self.prioridad is None:
            raise ValidacionError("No se puede leer la clave sin haber calculado la prioridad.")
        return (self.prioridad, self.magnitud, self.identificador)

    def datos_iguales(self, magnitud, profundidad, epicentro_x, epicentro_y, fecha_hora):
        """
        Section 6: data equality for processing reports refers
        to magnitude, depth, epicenter, and occurrence time — never
        to the report sender or the format of the received text.
        """
        return (self.magnitud == magnitud and self.profundidad == profundidad
                and self.epicentro_x == epicentro_x and self.epicentro_y == epicentro_y
                and self.fecha_hora == fecha_hora)

    def __repr__(self):
        return (f"Evento(id={self.identificador}, M={self.magnitud}, "
                f"P={self.prioridad}, rev={self.revision}, {self.estado_atencion})")