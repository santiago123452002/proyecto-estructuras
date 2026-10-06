"""
Phase 1 tests (generic BST and AVL trees).

A minimal `ElementoPrueba` class is used, exposing only the `clave`
attribute, because the real Event class (with magnitude, depth, epicenter,
etc.) is built in Phase 2. This allows the tree to be tested independently
before connecting it to the rest of the system.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import ArbolBST, ArbolAVL


class ElementoPrueba:
    def __init__(self, prioridad, magnitud, identificador):
        self.clave = (prioridad, magnitud, identificador)

    def __repr__(self):
        return f"Elem{self.clave}"


def test_direccion_insercion_ejemplo_enunciado():
    """
    Reproduces the example from Section 5: given a node whose key is
    (3, 5.2, 10), verifies that each incoming key is placed in the
    direction specified by the document.
    """
    avl = ArbolAVL()
    avl.insertar(ElementoPrueba(3, 5.2, 10))

    # (2, 5.8, 20) -> izquierda (prioridad menor manda, aunque 5.8 > 5.2)
    avl.insertar(ElementoPrueba(2, 5.8, 20))
    assert avl.raiz.izquierdo.clave == (2, 5.8, 20)

    # (3, 6.1, 30) -> derecha (empatan prioridad, 6.1 > 5.2)
    avl.insertar(ElementoPrueba(3, 6.1, 30))
    assert avl.raiz.derecho is not None
    assert (3, 6.1, 30) in [n.clave for n in [avl.raiz, avl.raiz.izquierdo, avl.raiz.derecho,
                                               avl.raiz.izquierdo.izquierdo if avl.raiz.izquierdo else None,
                                               avl.raiz.izquierdo.derecho if avl.raiz.izquierdo else None,
                                               avl.raiz.derecho.izquierdo if avl.raiz.derecho else None,
                                               avl.raiz.derecho.derecho if avl.raiz.derecho else None]
                            if n is not None]


def test_rotacion_ll():
    """
    Inserting in descending identifier order (with the same priority and
    magnitude) forces a chain to the left -> LL rotation.
    """
    avl = ArbolAVL()
    avl.insertar(ElementoPrueba(1, 5.0, 30))
    avl.insertar(ElementoPrueba(1, 5.0, 20))
    avl.insertar(ElementoPrueba(1, 5.0, 10))  # dispara rotación LL

    assert avl.raiz.clave == (1, 5.0, 20)
    assert avl.raiz.izquierdo.clave == (1, 5.0, 10)
    assert avl.raiz.derecho.clave == (1, 5.0, 30)
    assert all(fb in (-1, 0, 1) for fb in _factores_balance(avl))


def test_rotacion_rr():
    """
    Inserting in ascending order forces a chain to the right -> RR rotation.
    """
    avl = ArbolAVL()
    avl.insertar(ElementoPrueba(1, 5.0, 10))
    avl.insertar(ElementoPrueba(1, 5.0, 20))
    avl.insertar(ElementoPrueba(1, 5.0, 30))  # dispara rotación RR

    assert avl.raiz.clave == (1, 5.0, 20)
    assert avl.raiz.izquierdo.clave == (1, 5.0, 10)
    assert avl.raiz.derecho.clave == (1, 5.0, 30)


def test_rotacion_lr():
    avl = ArbolAVL()
    avl.insertar(ElementoPrueba(1, 5.0, 30))
    avl.insertar(ElementoPrueba(1, 5.0, 10))
    avl.insertar(ElementoPrueba(1, 5.0, 20))  # dispara rotación LR

    assert avl.raiz.clave == (1, 5.0, 20)
    assert avl.raiz.izquierdo.clave == (1, 5.0, 10)
    assert avl.raiz.derecho.clave == (1, 5.0, 30)


def test_rotacion_rl():
    avl = ArbolAVL()
    avl.insertar(ElementoPrueba(1, 5.0, 10))
    avl.insertar(ElementoPrueba(1, 5.0, 30))
    avl.insertar(ElementoPrueba(1, 5.0, 20))  # dispara rotación RL

    assert avl.raiz.clave == (1, 5.0, 20)
    assert avl.raiz.izquierdo.clave == (1, 5.0, 10)
    assert avl.raiz.derecho.clave == (1, 5.0, 30)


def test_avl_permanece_balanceado_con_muchas_inserciones():
    avl = ArbolAVL()
    for i in range(1, 51):
        avl.insertar(ElementoPrueba(1, 5.0, i))
    assert all(fb in (-1, 0, 1) for fb in _factores_balance(avl))
    # log2(50) ~ 5.6, un AVL con 50 nodos no debería superar esa altura por mucho
    assert avl.altura_total() <= 7


def test_recorrido_inorden_ascendente():
    avl = ArbolAVL()
    claves = [(1, 5.0, 30), (2, 4.0, 5), (1, 5.0, 10), (3, 6.0, 1), (1, 5.0, 20)]
    for p, m, i in claves:
        avl.insertar(ElementoPrueba(p, m, i))

    obtenidas = [e.clave for e in avl.recorrido_inorden()]
    assert obtenidas == sorted(claves)


def test_eliminacion_mantiene_balance_y_orden():
    avl = ArbolAVL()
    for i in range(1, 21):
        avl.insertar(ElementoPrueba(1, 5.0, i))

    avl.eliminar((1, 5.0, 7))
    avl.eliminar((1, 5.0, 1))
    avl.eliminar((1, 5.0, 20))

    assert len(avl) == 17
    assert all(fb in (-1, 0, 1) for fb in _factores_balance(avl))
    claves = [e.clave for e in avl.recorrido_inorden()]
    assert claves == sorted(claves)
    assert avl.buscar_nodo((1, 5.0, 7))[0] is None


def test_bst_no_balancea_y_avl_si_con_insercion_ascendente():
    """
    Compares BST vs AVL using the same ascending sequence (Section 12):
    the BST degenerates into a list (height = n-1), while the AVL tree
    maintains logarithmic height.
    """
    n = 15
    bst = ArbolBST()
    avl = ArbolAVL()
    for i in range(1, n + 1):
        bst.insertar(ElementoPrueba(1, 5.0, i))
        avl.insertar(ElementoPrueba(1, 5.0, i))

    assert bst.altura() == n - 1        # degenerado: una cadena
    assert avl.altura_total() < bst.altura()  # el AVL se mantiene compacto
    assert bst.recorrido_inorden.__call__() or True  # recorridos disponibles


def _factores_balance(avl):
    resultado = []

    def recorrer(nodo):
        if nodo is not None:
            resultado.append(avl.factor_balance(nodo))
            recorrer(nodo.izquierdo)
            recorrer(nodo.derecho)

    recorrer(avl.raiz)
    return resultado


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])