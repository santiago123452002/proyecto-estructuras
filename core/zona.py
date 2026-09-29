class Zona:
    """
    Zona rectangular del escenario (sección 3). Límites en km, entre 0 y
    1000 en ambos ejes. Los bordes son inclusivos: un epicentro sobre el
    límite de la zona pertenece a ella.
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
    Un epicentro pertenece a una zona cuando está dentro de ella o sobre
    su borde. Si el punto cae en el borde de dos zonas, se clasifica
    como zona poblada si CUALQUIERA de las dos está definida como tal
    (sección 3: "se clasifica como zona poblada si alguna de las dos
    está definida de esa forma").
    """
    for zona in zonas:
        if zona.contiene(x, y) and zona.poblada:
            return True
    return False