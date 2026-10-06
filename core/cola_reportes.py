class _NodoCola:
    __slots__ = ("valor", "siguiente")

    def __init__(self, valor):
        self.valor = valor
        self.siguiente = None


class ColaReportes:
    """
    FIFO queue of pending reports (sections 2 and 8). Explicitly implemented
    with a custom singly linked list — NOT delegated to
    collections.deque or any standard library collection.

    Head and tail pointers are stored, so enqueue and dequeue are
    O(1): neither operation traverses the queue. The memory cost is
    O(n), one linked node for each pending report.

    A linked list was chosen instead of a Python list with insertion
    at the end and removal at index 0, because removing at index 0
    from a Python list is O(n) (all remaining elements must be
    traversed and shifted) — exactly the cost we want to avoid.
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
        """Adds a report to the end of the queue. Cost: O(1)."""
        nodo = _NodoCola(reporte)
        if self._cola is None:
            self._cabeza = nodo
            self._cola = nodo
        else:
            self._cola.siguiente = nodo
            self._cola = nodo
        self._cantidad += 1

    def desencolar(self):
        """Removes and returns the oldest report. Cost: O(1).
        Raises IndexError if the queue is empty."""
        if self._cabeza is None:
            raise IndexError("No se puede desencolar: la cola de reportes está vacía.")
        nodo = self._cabeza
        self._cabeza = nodo.siguiente
        if self._cabeza is None:
            self._cola = None
        self._cantidad -= 1
        return nodo.valor

    def ver_orden(self):
        """List (without modifying the queue) of the reports in
        reception order — so the interface can display them without consuming them."""
        resultado = []
        actual = self._cabeza
        while actual is not None:
            resultado.append(actual.valor)
            actual = actual.siguiente
        return resultado