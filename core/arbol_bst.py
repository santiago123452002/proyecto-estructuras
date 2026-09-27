from .nodo import Nodo


class ArbolBST:
    """
    Árbol binario de búsqueda "puro", SIN balanceo.

    Se usa como árbol de comparación frente al AVL: la sección 12 del
    enunciado pide insertar la misma secuencia de eventos, con el mismo
    comparador, en un AVL y en este BST, y luego comparar altura, hojas
    y comparaciones realizadas.

    No delega nada a bibliotecas de árboles: toda la lógica está aquí.
    """

    def __init__(self):
        self.raiz = None
        self._cantidad = 0

    def __len__(self):
        return self._cantidad

    def insertar(self, elemento):
        """Inserta un elemento nuevo siguiendo la clave K. Devuelve el
        nodo creado. No maneja duplicados de identificador: esa gestión
        (confirmación/corrección/conflicto) pertenece a la capa de
        negocio, no al árbol."""
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
        """Devuelve (nodo, nodos_visitados). nodo es None si no existe."""
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
        """Altura calculada recorriendo el árbol. Vacío = -1, hoja = 0."""
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