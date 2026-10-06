from .nodo import Nodo


class ArbolBST:
    """
    Pure binary search tree, WITHOUT balancing.

    It is used as a comparison tree against the AVL: section 12 of the
    statement requires inserting the same sequence of events, with the same
    comparator, into an AVL and this BST, and then comparing height, leaves,
    and comparisons performed.

    It does not delegate anything to tree libraries: all the logic is here.
    """

    def __init__(self):
        self.raiz = None
        self._cantidad = 0

    def __len__(self):
        return self._cantidad

    def insertar(self, elemento):
        """Inserts a new element following key K. Returns the
        created node. It does not handle duplicate identifiers: that management
        (confirmation/correction/conflict) belongs to the business layer,
        not to the tree."""
        nuevo = Nodo(elemento)
        if self.raiz is None:
            self.raiz = nuevo
            self._cantidad += 1
            return nuevo

        actual = self.raiz
        while True:
            if nuevo.clave < actual.clave:
                if actual.izquierdo is None:
                    actual.izquierdo = nuevo
                    nuevo.padre = actual
                    break
                actual = actual.izquierdo
            else:
                if actual.derecho is None:
                    actual.derecho = nuevo
                    nuevo.padre = actual
                    break
                actual = actual.derecho
        self._cantidad += 1
        return nuevo

    def buscar_nodo(self, clave):
        """Returns (node, nodes_visited). node is None if it does not exist."""
        actual = self.raiz
        visitados = 0
        while actual is not None:
            visitados += 1
            if clave == actual.clave:
                return actual, visitados
            elif clave < actual.clave:
                actual = actual.izquierdo
            else:
                actual = actual.derecho
        return None, visitados

    def altura(self):
        """Height calculated by traversing the tree. Empty = -1, leaf = 0."""
        return self._altura_nodo(self.raiz)

    def _altura_nodo(self, nodo):
        if nodo is None:
            return -1
        return 1 + max(self._altura_nodo(nodo.izquierdo), self._altura_nodo(nodo.derecho))

    def contar_hojas(self):
        return self._contar_hojas_nodo(self.raiz)

    def _contar_hojas_nodo(self, nodo):
        if nodo is None:
            return 0
        if nodo.izquierdo is None and nodo.derecho is None:
            return 1
        return self._contar_hojas_nodo(nodo.izquierdo) + self._contar_hojas_nodo(nodo.derecho)

    def recorrido_inorden(self):
        resultado = []
        self._inorden(self.raiz, resultado)
        return resultado

    def _inorden(self, nodo, resultado):
        if nodo is not None:
            self._inorden(nodo.izquierdo, resultado)
            resultado.append(nodo.elemento)
            self._inorden(nodo.derecho, resultado)

    def recorrido_preorden(self):
        resultado = []
        self._preorden(self.raiz, resultado)
        return resultado

    def _preorden(self, nodo, resultado):
        if nodo is not None:
            resultado.append(nodo.elemento)
            self._preorden(nodo.izquierdo, resultado)
            self._preorden(nodo.derecho, resultado)

    def recorrido_postorden(self):
        resultado = []
        self._postorden(self.raiz, resultado)
        return resultado

    def _postorden(self, nodo, resultado):
        if nodo is not None:
            self._postorden(nodo.izquierdo, resultado)
            self._postorden(nodo.derecho, resultado)
            resultado.append(nodo.elemento)