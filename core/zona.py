class Zona:
    """
    Rectangular zone of the scenario (Section 3). Boundaries are given in km,
    between 0 and 1000 on both axes. The boundaries are inclusive: an epicenter
    located on the boundary of the zone belongs to that zone.
    """

    def __init__(self, nombre, x_min, x_max, y_min, y_max, poblada):
        if x_min > x_max or y_min > y_max:
            raise ValueError("Los límites de la zona son inválidos (mínimo mayor que máximo).")
        self.nombre = nombre
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.poblada = poblada

    def contiene(self, x, y):
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max

    def __repr__(self):
        tipo = "poblada" if self.poblada else "no poblada"
        return f"Zona({self.nombre}, {tipo})"


def pertenece_a_zona_poblada(x, y, zonas):
    """
    An epicenter belongs to a zone when it is inside the zone or located on
    its boundary. If the point lies on the boundary of two zones, it is
    classified as a populated zone if EITHER of the two zones is defined
    as populated (Section 3: "it is classified as a populated zone if either
    one is defined as such").
    """
    for zona in zonas:
        if zona.contiene(x, y) and zona.poblada:
            return True
    return False