class Nodo:
    """
    Generic node for binary search trees (BST and AVL).

    Stores the COMPLETE element (in later phases it will be an
    Event object), not just its key. The element must expose a
    `clave` property comparable with <, >, == (in the project, the tuple
    K = (priority, magnitude, identifier)).

    `padre` is optional but very useful for locating events and for
    building the undo stack later.
    """
 
    def __init__(self, elemento):
        self.elemento = elemento
        self.izquierdo = None
        self.derecho = None
        self.padre = None
        self.altura = 0  # used only by the AVL; the BST ignores it
 
    @property
    def clave(self):
        return self.elemento.clave
 
    def __repr__(self):
        return f"Nodo(clave={self.clave})"