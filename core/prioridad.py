def calcular_prioridad(magnitud, profundidad, en_zona_poblada):
    """
    Section 4 of the statement. Fixed rules, evaluated in this order,
    with inclusive limits:

        3 (High)    if M >= 6.0
                    or (M >= 4.5 and H <= 30.0 and epicenter is in a populated area)
        2 (Medium)  if it does not meet High and M >= 4.5
        1 (Low)     in any other case

    Priority is never entered manually: it is always derived from
    the current event data and the geometry of the scenario.
    """
    if magnitud >= 6.0:
        return 3
    if magnitud >= 4.5 and profundidad <= 30.0 and en_zona_poblada:
        return 3
    if magnitud >= 4.5:
        return 2
    return 1