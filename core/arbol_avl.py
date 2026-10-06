from .nodo import Nodo


class ArbolAVL:
    """
    AVL Tree implemented from scratch (without tree libraries).

    It is the central structure of the active event catalog (section 2
    of the statement). The key of each node is K = (priority, magnitude,
    identifier); lexicographic comparison is implemented by the stored
    element itself (the Event class), this tree only uses <, ==, >
    comparisons on that key.

    Height convention (section 14): empty tree = -1, leaf = 0.
    Balance factor = height(left) - height(right).

    Supports deferred balancing (stress mode, section 8): `insert` and
    `delete` receive a `balance` parameter. With `balance=False`, the
    BST ordering is preserved but nodes are not rotated, so the tree
    may no longer satisfy the AVL property. `restore_balance`
    restores the complete AVL property afterwards.
"""

    def __init__(self):
        self.raiz = None
        self._cantidad = 0
        # Métricas de la sección 14: casos atendidos y giros elementales.
        # Un caso doble (LR o RL) cuenta como un caso de ese tipo y DOS
        # giros elementales (uno a cada lado); un caso simple (LL o RR)
        # cuenta como un caso de ese tipo y UN giro elemental.
        self.contador_casos = {"LL": 0, "RR": 0, "LR": 0, "RL": 0}
        self.contador_giros_izquierda = 0
        self.contador_giros_derecha = 0
        # Rotaciones de recuperar_equilibrio (Day-Stout-Warren): no
        # encajan en la clasificación LL/RR/LR/RL, que es propia del
        # rebalanceo tras una única inserción o eliminación.
        self.contador_rotaciones_recuperacion = 0

    def __len__(self):
        return self._cantidad

    # ---------------- altura y balance ----------------

    def _altura(self, nodo):
        return nodo.altura if nodo is not None else -1

    def _actualizar_altura(self, nodo):
        nodo.altura = 1 + max(self._altura(nodo.izquierdo), self._altura(nodo.derecho))

    def factor_balance(self, nodo):
        if nodo is None:
            return 0
        return self._altura(nodo.izquierdo) - self._altura(nodo.derecho)

    def esta_balanceado(self):
        """True si TODOS los nodos tienen factor de balance en {-1, 0, 1}."""
        return all(fb in (-1, 0, 1) for fb in self._factores_balance())

    def _factores_balance(self):
        resultado = []

        def recorrer(nodo):
            if nodo is not None:
                resultado.append(self.factor_balance(nodo))
                recorrer(nodo.izquierdo)
                recorrer(nodo.derecho)

        recorrer(self.raiz)
        return resultado

    # ---------------- rotaciones ----------------

    def _rotacion_derecha(self, y):
        """Simple right rotation. `y` is the root of the unbalanced subtree."""
        x = y.izquierdo
        t2 = x.derecho

        x.padre = y.padre
        y.padre = x
        if t2 is not None:
            t2.padre = y

        x.derecho = y
        y.izquierdo = t2

        self._actualizar_altura(y)
        self._actualizar_altura(x)
        self.contador_giros_derecha += 1
        return x

    def _rotacion_izquierda(self, x):
        """Simple left rotation. `x` is the root of the unbalanced subtree."""
        y = x.derecho
        t2 = y.izquierdo

        y.padre = x.padre
        x.padre = y
        if t2 is not None:
            t2.padre = x

        y.izquierdo = x
        x.derecho = t2

        self._actualizar_altura(x)
        self._actualizar_altura(y)
        self.contador_giros_izquierda += 1
        return y

    def _rebalancear(self, nodo):
        """
        Recalculates the height of `node` and applies rotations until its
        balance factor is in {-1, 0, 1}. A loop is used (not a single
        "if") because in stress mode, several insertions/deletions can
        accumulate without rotations, and a single rotation may not be
        enough to correct a height difference greater than 2 (section
        8). Each iteration inside the loop DOES correspond exactly to
                one LL/RR/LR/RL case for the metrics in section 14.

        Returns the new root of this subtree.
    """
        self._actualizar_altura(nodo)
        fb = self.factor_balance(nodo)

        while fb > 1 or fb < -1:
            if fb > 1:
                if self.factor_balance(nodo.izquierdo) < 0:
                    nodo.izquierdo = self._rotacion_izquierda(nodo.izquierdo)
                    nodo.izquierdo.padre = nodo
                    self.contador_casos["LR"] += 1
                else:
                    self.contador_casos["LL"] += 1
                nodo = self._rotacion_derecha(nodo)
            else:
                if self.factor_balance(nodo.derecho) > 0:
                    nodo.derecho = self._rotacion_derecha(nodo.derecho)
                    nodo.derecho.padre = nodo
                    self.contador_casos["RL"] += 1
                else:
                    self.contador_casos["RR"] += 1
                nodo = self._rotacion_izquierda(nodo)

            self._actualizar_altura(nodo)
            fb = self.factor_balance(nodo)

        return nodo

    # ---------------- inserción ----------------

    def insertar(self, elemento, balancear=True):
        """Inserts a new element. If `balancear` is True (normal mode),
        maintains the AVL property; if it is False (stress mode),
        preserves BST ordering but does not rotate. Returns the inserted node."""
        nuevo = Nodo(elemento)
        self.raiz = self._insertar_recursivo(self.raiz, nuevo, balancear)
        self.raiz.padre = None
        self._cantidad += 1
        return nuevo

    def _insertar_recursivo(self, actual, nuevo, balancear):
        if actual is None:
            return nuevo

        if nuevo.clave < actual.clave:
            actual.izquierdo = self._insertar_recursivo(actual.izquierdo, nuevo, balancear)
            actual.izquierdo.padre = actual
        else:
            actual.derecho = self._insertar_recursivo(actual.derecho, nuevo, balancear)
            actual.derecho.padre = actual

        if balancear:
            return self._rebalancear(actual)
        self._actualizar_altura(actual)
        return actual

    # ---------------- búsqueda ----------------

    def buscar_nodo(self, clave):
        """Returns (node, nodes_visited). node is None if it does not exist.
        `nodes_visited` is the simulated cost from section 9: for an existing
        event, it is equal to its depth + 1."""
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

    def profundidad(self, clave):
        """Depth of the node with the given key (root = 0), or None if it does not exist."""
        actual = self.raiz
        prof = 0
        while actual is not None:
            if clave == actual.clave:
                return prof
            elif clave < actual.clave:
                actual = actual.izquierdo
            else:
                actual = actual.derecho
            prof += 1
        return None

    # ---------------- eliminación ----------------

    def eliminar(self, clave, balancear=True):
        """Deletes the node with the given key. With `balancear=True`, it rebalances;
        with `balancear=False` (stress mode), it preserves ordering but does not rotate.
        Returns True if the node existed, False if it was not found."""

        if self.buscar_nodo(clave)[0] is None:
            return False
        self.raiz = self._eliminar_recursivo(self.raiz, clave, balancear)
        if self.raiz is not None:
            self.raiz.padre = None
        self._cantidad -= 1
        return True

    def _eliminar_recursivo(self, nodo, clave, balancear):
        if nodo is None:
            return None

        if clave < nodo.clave:
            nodo.izquierdo = self._eliminar_recursivo(nodo.izquierdo, clave, balancear)
            if nodo.izquierdo is not None:
                nodo.izquierdo.padre = nodo
        elif clave > nodo.clave:
            nodo.derecho = self._eliminar_recursivo(nodo.derecho, clave, balancear)
            if nodo.derecho is not None:
                nodo.derecho.padre = nodo
        else:
            if nodo.izquierdo is None or nodo.derecho is None:
                hijo = nodo.izquierdo if nodo.izquierdo is not None else nodo.derecho
                return hijo
            else:
                sucesor = nodo.derecho
                while sucesor.izquierdo is not None:
                    sucesor = sucesor.izquierdo
                nodo.elemento = sucesor.elemento
                nodo.derecho = self._eliminar_recursivo(nodo.derecho, sucesor.clave, balancear)
                if nodo.derecho is not None:
                    nodo.derecho.padre = nodo

        if balancear:
            return self._rebalancear(nodo)
        self._actualizar_altura(nodo)
        return nodo

    # ---------------- global recovery (stress mode, section 8) ----------------
    #
    # Day-Stout-Warren algorithm (1986), adapted to this class. It uses
    # EXCLUSIVELY rotations -- the tree is never emptied nor rebuilt from
    # a separate list, as required by the statement -- and corrects
    # arbitrarily large height differences in two phases:
    #
    #   Phase 1 ("vine"): converts the tree into a chain using only
    #   right links (traverses the nodes in the same order as an
    #   inorder traversal), using repeated simple right rotations.
    #
    #   Phase 2 ("compression"): applies a series of simple left rotations
    #   to that chain to convert it into an almost perfectly balanced tree
    #   (a complete tree of m = 2^k - 1 nodes, plus the n - m remaining
    #   nodes distributed across the last level).
    #
    # Each rotation preserves BST ordering by construction, so the
    # resulting tree contains exactly the same keys in the same relative
    # order. The algorithm performs a bounded number of rotations per
    # node in each phase (at most once a node loses its left child in
    # Phase 1; Phase 2 performs at most O(log n) passes), so the total
    # cost is O(n) and therefore it always terminates.

    class _NodoPseudo:
        """Temporary header (not part of the actual tree) that gives
        Phases 1 and 2 a uniform place to 'attach' the real root,
        so the root case does not have to be handled separately."""
        __slots__ = ("derecho",)

        def __init__(self, derecho):
            self.derecho = derecho

    def recuperar_equilibrio(self):
        """
        Restores the AVL property throughout the ENTIRE tree, even if there are
        height differences greater than 2 (accumulated during stress mode).
        Returns True if the tree is balanced.

        Rotations do not create or destroy nodes, so any external index by
        identifier (see Catalog) remains valid after calling this method,
        without needing to rebuild it.
        """
        if self.raiz is None:
            return True

        pseudo = ArbolAVL._NodoPseudo(self.raiz)
        self._arbol_a_vid(pseudo)

        n = self._cantidad
        # m = tamaño del árbol completo más grande que cabe en n nodos (2^k - 1)
        m = 1
        while (m * 2) - 1 <= n:
            m *= 2
        m -= 1

        self._comprimir(pseudo, n - m)  # aplana los nodos sobrantes primero
        resto = m
        while resto > 1:
            resto //= 2
            self._comprimir(pseudo, resto)

        self.raiz = pseudo.derecho
        self._reconstruir_metadatos(self.raiz, None)
        return self.esta_balanceado()

    def _arbol_a_vid(self, pseudo):
        """Phase 1: converts the tree attached to `pseudo.derecho` into a
        chain of right links, using only simple right rotations. It does not
        modify `parent` or `height`: these are recalculated only once at the
        end, in `_reconstruir_metadatos`."""
        anterior = pseudo
        actual = anterior.derecho
        while actual is not None:
            if actual.izquierdo is not None:
                hijo = actual.izquierdo
                actual.izquierdo = hijo.derecho
                hijo.derecho = actual
                anterior.derecho = hijo
                actual = hijo
                self.contador_rotaciones_recuperacion += 1
            else:
                anterior = actual
                actual = actual.derecho

    def _comprimir(self, pseudo, conteo):
        """Phase 2: applies `count` simple left rotations along the chain
        attached to `pseudo.derecho`."""
        escaner = pseudo
        for _ in range(conteo):
            hijo = escaner.derecho
            escaner.derecho = hijo.derecho
            escaner = escaner.derecho
            hijo.derecho = escaner.izquierdo
            escaner.izquierdo = hijo
            self.contador_rotaciones_recuperacion += 1

    def _reconstruir_metadatos(self, nodo, padre):
        """Single postorder traversal to recalculate `parent` and
        `height` for all nodes after the restructuring performed by
        `restore_balance`. Returns the height of `node`."""
        if nodo is None:
            return -1
        nodo.padre = padre
        altura_izquierda = self._reconstruir_metadatos(nodo.izquierdo, nodo)
        altura_derecha = self._reconstruir_metadatos(nodo.derecho, nodo)
        nodo.altura = 1 + max(altura_izquierda, altura_derecha)
        return nodo.altura

    # ---------------- recorridos ----------------

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

    def recorrido_por_niveles(self):
        """BFS traversal (breadth-first), level by level (section 14). Uses a
        simple auxiliary queue with a read pointer, avoiding the O(n) cost
        of removing an element at index 0 from a Python list."""
        if self.raiz is None:
            return []
        resultado = []
        cola = [self.raiz]
        indice = 0
        while indice < len(cola):
            nodo = cola[indice]
            indice += 1
            resultado.append(nodo.elemento)
            if nodo.izquierdo is not None:
                cola.append(nodo.izquierdo)
            if nodo.derecho is not None:
                cola.append(nodo.derecho)
        return resultado

    def altura_total(self):
        return self._altura(self.raiz)

    def contar_hojas(self):
        return self._contar_hojas_nodo(self.raiz)

    def _contar_hojas_nodo(self, nodo):
        if nodo is None:
            return 0
        if nodo.izquierdo is None and nodo.derecho is None:
            return 1
        return self._contar_hojas_nodo(nodo.izquierdo) + self._contar_hojas_nodo(nodo.derecho)

    # ---------------- subárboles elegibles (sección 10, archivo) ----------------

    def subarboles_elegibles(self, criterio):
        """
        Returns a list of (node, node_count, depth) for
        EACH node whose complete subtree satisfies `criterion(event)`
        for ALL of its events (a leaf also counts as a subtree of
        size 1). `criterion` is an Event -> bool function.

        A single postorder traversal, O(n): when reaching each node, it is already
        known whether its two subtrees are completely eligible, so it is enough
        to combine that information with the node itself.
        """
        resultado = []

        def recorrer(nodo, profundidad):
            if nodo is None:
                return True, 0
            elegible_izq, cantidad_izq = recorrer(nodo.izquierdo, profundidad + 1)
            elegible_der, cantidad_der = recorrer(nodo.derecho, profundidad + 1)
            elegible_propio = criterio(nodo.elemento)
            elegible_total = elegible_propio and elegible_izq and elegible_der
            cantidad_total = 1 + cantidad_izq + cantidad_der
            if elegible_total:
                resultado.append((nodo, cantidad_total, profundidad))
            return elegible_total, cantidad_total

        recorrer(self.raiz, 0)
        return resultado