from .nodo import Nodo


class ArbolAVL:
    """
    Árbol AVL implementado desde cero (sin bibliotecas de árboles).

    Es la estructura central del catálogo activo de eventos (sección 2
    del enunciado). La clave de cada nodo es K = (prioridad, magnitud,
    identificador); la comparación lexicográfica la implementa el propio
    elemento almacenado (la clase Evento), este árbol solo usa <, ==, >
    sobre esa clave.

    Convención de alturas (sección 14): árbol vacío = -1, hoja = 0.
    Factor de balance = altura(izquierdo) - altura(derecho).

    Soporta balanceo diferido (modo estrés, sección 8): `insertar` y
    `eliminar` reciben un parámetro `balancear`. Con `balancear=False`
    se conserva el orden BST pero no se rotan los nodos, así que el
    árbol puede dejar de cumplir la propiedad AVL. `recuperar_equilibrio`
    restaura la propiedad AVL completa después.
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
        """Giro simple a la derecha. `y` es la raíz del subárbol desbalanceado."""
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
        """Giro simple a la izquierda. `x` es la raíz del subárbol desbalanceado."""
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
        Recalcula la altura de `nodo` y aplica rotaciones hasta que su
        factor de balance quede en {-1, 0, 1}. Se usa un bucle (no un
        único "if") porque en modo estrés pueden acumularse varias
        inserciones/eliminaciones sin rotar, y un solo giro no siempre
        alcanza a corregir una diferencia de altura mayor que 2 (sección
        8). Cada iteración dentro del bucle SÍ corresponde exactamente a
        un caso LL/RR/LR/RL para las métricas de la sección 14.

        Devuelve la nueva raíz de este subárbol.
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
        """Inserta un elemento nuevo. Si `balancear` es True (modo
        normal) mantiene la propiedad AVL; si es False (modo estrés)
        conserva el orden BST pero no rota. Devuelve el nodo insertado."""
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
        """Devuelve (nodo, nodos_visitados). nodo es None si no existe.
        `nodos_visitados` es el costo simulado de la sección 9: para un
        evento existente equivale a su profundidad + 1."""
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
        """Profundidad del nodo con esa clave (raíz = 0), o None si no existe."""
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
        """Elimina el nodo con esa clave. Con `balancear=True` reequilibra;
        con `balancear=False` (modo estrés) conserva el orden pero no rota.
        Devuelve True si existía, False si no se encontró."""
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

    # ---------------- recuperación global (modo estrés, sección 8) ----------------
    #
    # Algoritmo de Day-Stout-Warren (1986), adaptado a esta clase. Usa
    # EXCLUSIVAMENTE rotaciones -- nunca se vacía el árbol ni se
    # reconstruye desde una lista aparte, como exige el enunciado -- y
    # corrige diferencias de altura arbitrariamente grandes en dos fases:
    #
    #   Fase 1 ("vid"): convierte el árbol en una cadena que solo usa
    #   enlaces derechos (recorre los nodos en el mismo orden que un
    #   inorden), mediante rotaciones simples a la derecha repetidas.
    #
    #   Fase 2 ("compresión"): aplica una serie de rotaciones simples a
    #   la izquierda sobre esa cadena para convertirla en un árbol casi
    #   perfectamente balanceado (un árbol completo de m = 2^k - 1 nodos,
    #   más los n - m nodos sobrantes distribuidos en el último nivel).
    #
    # Cada rotación preserva el orden BST por construcción, así que el
    # resultado conserva exactamente las mismas claves en el mismo orden
    # relativo. El algoritmo hace un número acotado de rotaciones por
    # nodo en cada fase (a lo sumo una vez que un nodo deja de tener
    # hijo izquierdo permanece así en la Fase 1; la Fase 2 hace como
    # máximo O(log n) pasadas), así que el costo total es O(n) y por lo
    # tanto siempre termina.

    class _NodoPseudo:
        """Cabecera temporal (no forma parte del árbol real) que le da
        a las Fases 1 y 2 un lugar uniforme donde 'colgar' la raíz real,
        para no tener que tratar el caso de la raíz como especial."""
        __slots__ = ("derecho",)

        def __init__(self, derecho):
            self.derecho = derecho

    def recuperar_equilibrio(self):
        """
        Restaura la propiedad AVL en TODO el árbol, incluso si existen
        diferencias de altura mayores que 2 (acumuladas durante el modo
        estrés). Devuelve True si el árbol quedó balanceado.

        Las rotaciones no crean ni destruyen nodos, así que cualquier
        índice externo por identificador (ver Catalogo) sigue siendo
        válido después de llamar a este método, sin necesidad de
        reconstruirlo.
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
        """Fase 1: convierte el árbol colgado de `pseudo.derecho` en una
        cadena de enlaces derechos, usando solo rotaciones simples a la
        derecha. No toca `padre` ni `altura`: eso se recalcula una sola
        vez al final, en `_reconstruir_metadatos`."""
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
        """Fase 2: aplica `conteo` rotaciones simples a la izquierda a
        lo largo de la cadena colgada de `pseudo.derecho`."""
        escaner = pseudo
        for _ in range(conteo):
            hijo = escaner.derecho
            escaner.derecho = hijo.derecho
            escaner = escaner.derecho
            hijo.derecho = escaner.izquierdo
            escaner.izquierdo = hijo
            self.contador_rotaciones_recuperacion += 1

    def _reconstruir_metadatos(self, nodo, padre):
        """Recorrido único en postorden para recalcular `padre` y
        `altura` de todos los nodos después de la reestructuración de
        `recuperar_equilibrio`. Devuelve la altura de `nodo`."""
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
        """Recorrido BFS (anchura), nivel por nivel (sección 14). Usa una
        cola auxiliar simple con puntero de lectura, para no pagar el
        costo O(n) de sacar por el índice 0 de una lista de Python."""
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
        Devuelve una lista de (nodo, cantidad_nodos, profundidad) para
        CADA nodo cuyo subárbol completo cumple `criterio(evento)` en
        TODOS sus eventos (una hoja también cuenta como subárbol de
        tamaño 1). `criterio` es una función Evento -> bool.

        Un único recorrido postorden, O(n): al llegar a cada nodo ya se
        sabe si sus dos subárboles son completamente elegibles, así que
        basta con combinar esa información con el propio nodo.
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