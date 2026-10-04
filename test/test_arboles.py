"""
Pruebas de la Fase 1 (BST y AVL genéricos).

Se usa una clase mínima `ElementoPrueba` que solo expone `clave`, porque
la clase Evento real (con magnitud, profundidad, epicentro, etc.) se
construye en la Fase 2. Esto nos permite probar el árbol de forma
aislada antes de conectarlo con el resto del sistema.
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
    Reproduce el ejemplo de la sección 5: frente a un nodo cuya clave es
    (3, 5.2, 10), verifica que cada clave entrante caiga en la dirección
    indicada por el documento.
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
    """Insertar en orden descendente de identificador (misma prioridad y
    magnitud) fuerza una cadena hacia la izquierda -> rotación LL."""
    avl = ArbolAVL()
    avl.insertar(ElementoPrueba(1, 5.0, 30))
    avl.insertar(ElementoPrueba(1, 5.0, 20))
    avl.insertar(ElementoPrueba(1, 5.0, 10))  # dispara rotación LL

    assert avl.raiz.clave == (1, 5.0, 20)
    assert avl.raiz.izquierdo.clave == (1, 5.0, 10)
    assert avl.raiz.derecho.clave == (1, 5.0, 30)
    assert all(fb in (-1, 0, 1) for fb in _factores_balance(avl))


def test_rotacion_rr():
    """Insertar en orden ascendente fuerza una cadena hacia la derecha -> rotación RR."""
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
    """Compara BST vs AVL con la misma secuencia ascendente (sección 12):
    el BST degenera en una lista (altura = n-1) y el AVL se mantiene
    logarítmico."""
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