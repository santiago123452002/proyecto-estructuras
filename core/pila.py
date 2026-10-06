class _NodoPila:
    __slots__ = ("valor", "siguiente")

    def __init__(self, valor, siguiente=None):
        self.valor = valor
        self.siguiente = siguiente


class Pila:
    """
    LIFO stack (sections 2 and 13) explicitly implemented with a custom
    singly linked list — collections.deque and Python's list.append/pop
    are NOT used, even though they would have the same asymptotic cost.

    Push and pop are O(1): both operations only access the top,
    and never traverse the stack. Memory cost: O(n), one linked node per
    pushed element (in Escenario, each element is a complete copy
    of the operational state — see Escenario._capturar_estado).
    """

    def __init__(self):
        self._cima = None
        self._cantidad = 0

    def __len__(self):
        return self._cantidad

    def esta_vacia(self):
        return self._cima is None

    def apilar(self, valor):
        """Adds `valor` to the top. Cost: O(1)."""
        self._cima = _NodoPila(valor, self._cima)
        self._cantidad += 1

    def desapilar(self):
        """Removes and returns the value at the top. Cost: O(1).
        Raises IndexError if the stack is empty."""
        if self._cima is None:
            raise IndexError("No se puede desapilar: la pila está vacía.")
        nodo = self._cima
        self._cima = nodo.siguiente
        self._cantidad -= 1
        return nodo.valor

    def ver_cima(self):
        """Returns the value at the top without removing it. Cost: O(1)."""
        if self._cima is None:
            raise IndexError("No se puede consultar: la pila está vacía.")
        return self._cima.valor