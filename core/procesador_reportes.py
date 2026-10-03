def procesar_siguiente(cola, catalogo, zonas, reloj_simulacion, balancear=True):
    """
    Procesamiento de un reporte por paso (sección 8). Desencola el
    reporte más antiguo y lo procesa contra el catálogo. `balancear=False`
    corresponde al modo estrés: se aplaza el balanceo del AVL.

    Devuelve (reporte, resultado). Lanza IndexError si la cola está vacía.
    """
    reporte = cola.desencolar()
    resultado = catalogo.procesar_reporte(reporte, zonas, reloj_simulacion, balancear=balancear)
    return reporte, resultado


def procesar_todos(cola, catalogo, zonas, reloj_simulacion, balancear=True):
    """
    Procesamiento continuo (sección 8): resuelve todos los reportes
    pendientes en orden FIFO, cada uno como un paso independiente.
    Devuelve una lista de (reporte, resultado) en el orden en que se
    procesaron. La pausa entre pasos es un asunto de la interfaz gráfica,
    no de esta función.
    """
    resultados = []
    while not cola.esta_vacia():
        resultados.append(procesar_siguiente(cola, catalogo, zonas, reloj_simulacion, balancear))
    return resultados