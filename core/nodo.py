class Nodo:
    """
    Nodo genérico para árboles binarios de búsqueda (BST y AVL).
 
    Guarda el elemento COMPLETO (en fases posteriores será un objeto
    Evento), no solo su clave. El elemento debe exponer una propiedad
    `clave` comparable con <, >, == (en el proyecto, la tupla
    K = (prioridad, magnitud, identificador)).
 
    `padre` es opcional pero muy útil para localizar eventos y para
    construir la pila de deshacer más adelante.
    """
 
    def __init__(self, elemento):
        self.elemento = elemento
        self.izquierdo = None
        self.derecho = None
        self.padre = None
        self.altura = 0  # solo lo usa el AVL; el BST lo ignora
 
    @property
    def clave(self):
        return self.elemento.clave
 
    def __repr__(self):
        return f"Nodo(clave={self.clave})"