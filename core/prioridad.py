def calcular_prioridad(magnitud, profundidad, en_zona_poblada):
    """
    Sección 4 del enunciado. Reglas fijas, evaluadas en este orden,
    con límites inclusivos:

        3 (Alta)  si M >= 6.0
                  o bien (M >= 4.5 y H <= 30.0 y epicentro en zona poblada)
        2 (Media) si no cumple Alta y M >= 4.5
        1 (Baja)  en cualquier otro caso

    La prioridad nunca se introduce manualmente: siempre se deriva de
    los datos vigentes del evento y de la geometría del escenario.
    """
    if magnitud >= 6.0:
        return 3
    if magnitud >= 4.5 and profundidad <= 30.0 and en_zona_poblada:
        return 3
    if magnitud >= 4.5:
        return 2
    return 1