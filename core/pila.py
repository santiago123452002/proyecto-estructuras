class _NodoPila:
    __slots__ = ("valor", "siguiente")

    def __init__(self, valor, siguiente=None):
        self.valor = valor
        self.siguiente = siguiente


class Pila:
    """
    Pila LIFO (sección 2 y 13) implementada explícitamente con una lista
    enlazada simple propia — NO se usa collections.deque ni el
    list.append/pop de Python, aunque tendrían el mismo costo asintótico.

    Apilar y desapilar son O(1): ambas operaciones solo tocan la cima,
    nunca recorren la pila. Costo de memoria: O(n), un nodo enlazado por
    elemento apilado (en Escenario, cada elemento es una copia completa
    del estado operativo — ver Escenario._capturar_estado).
    """

    def __init__(self):
        self._cima = None
        self._cantidad = 0

    def __len__(self):
        return self._cantidad

    def esta_vacia(self):
        return self._cima is None

    def apilar(self, valor):
        """Agrega `valor` a la cima. Costo: O(1)."""
        self._cima = _NodoPila(valor, self._cima)
        self._cantidad += 1

    def desapilar(self):
        """Retira y devuelve el valor en la cima. Costo: O(1).
        Lanza IndexError si la pila está vacía."""
        if self._cima is None:
            raise IndexError("No se puede desapilar: la pila está vacía.")
        nodo = self._cima
        self._cima = nodo.siguiente
        self._cantidad -= 1
        return nodo.valor

    def ver_cima(self):
        """Consulta el valor en la cima sin retirarlo. Costo: O(1)."""
        if self._cima is None:
            raise IndexError("No se puede consultar: la pila está vacía.")
        return self._cima.valor