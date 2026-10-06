def procesar_siguiente(cola, catalogo, zonas, reloj_simulacion, balancear=True):
    """
    Processing one report per step (section 8). Dequeues the
    oldest report and processes it against the catalog. `balancear=False`
    corresponds to stress mode: AVL balancing is postponed.

    Returns (report, result). Raises IndexError if the queue is empty.
    """
    reporte = cola.desencolar()
    resultado = catalogo.procesar_reporte(reporte, zonas, reloj_simulacion, balancear=balancear)
    return reporte, resultado


def procesar_todos(cola, catalogo, zonas, reloj_simulacion, balancear=True):
    """
    Continuous processing (section 8): processes all pending reports
    in FIFO order, each one as an independent step.
    Returns a list of (report, result) in the order in which they
    were processed. The pause between steps is a matter for the graphical
    interface, not this function.
    """
    resultados = []
    while not cola.esta_vacia():
        resultados.append(procesar_siguiente(cola, catalogo, zonas, reloj_simulacion, balancear))
    return resultados