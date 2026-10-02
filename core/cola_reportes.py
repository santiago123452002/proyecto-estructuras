class _NodoCola:
    __slots__ = ("valor", "siguiente")

    def __init__(self, valor):
        self.valor = valor
        self.siguiente = None


class ColaReportes:
    """
    Cola FIFO de reportes pendientes (sección 2 y 8). Implementada
    explícitamente con una lista enlazada simple propia — NO se delega a
    collections.deque ni a ninguna colección de la biblioteca estándar.

    Se guardan punteros a cabeza y cola, así que encolar y desencolar son
    O(1): ninguna de las dos operaciones recorre la cola. El costo de
    memoria es O(n), un nodo enlazado por cada reporte pendiente.

    Se eligió lista enlazada en vez de una lista de Python con inserción
    al final y extracción por el índice 0, porque extraer por el índice 0
    de una lista de Python es O(n) (hay que recorrer y desplazar todos
    los elementos restantes) — justo el costo que se quiere evitar.
    """

    def __init__(self):
        self._cabeza = None
        self._cola = None
        self._cantidad = 0

    def __len__(self):
        return self._cantidad

    def esta_vacia(self):
        return self._cabeza is None

    def encolar(self, reporte):
        """Agrega un reporte al final de la cola. Costo: O(1)."""
        nodo = _NodoCola(reporte)
        if self._cola is None:
            self._cabeza = nodo
            self._cola = nodo
        else:
            self._cola.siguiente = nodo
            self._cola = nodo
        self._cantidad += 1

    def desencolar(self):
        """Retira y devuelve el reporte más antiguo. Costo: O(1).
        Lanza IndexError si la cola está vacía."""
        if self._cabeza is None:
            raise IndexError("No se puede desencolar: la cola de reportes está vacía.")
        nodo = self._cabeza
        self._cabeza = nodo.siguiente
        if self._cabeza is None:
            self._cola = None
        self._cantidad -= 1
        return nodo.valor

    def ver_orden(self):
        """Lista (sin modificar la cola) de los reportes en orden de
        recepción — para que la interfaz los muestre sin consumirlos."""
        resultado = []
        actual = self._cabeza
        while actual is not None:
            resultado.append(actual.valor)
            actual = actual.siguiente
        return resultado