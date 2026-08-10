GESTACION_DIAS = {
    "bovino": 285,
    "ovino": 150,
    "caprino": 150,
    "equino": 340,
    "porcino": 114,
}


def dias_gestacion(especie) -> int:
    """Días de gestación según la especie del animal (Bovino por defecto)."""
    if not especie:
        return GESTACION_DIAS["bovino"]
    return GESTACION_DIAS.get(especie.nombre.strip().lower(), GESTACION_DIAS["bovino"])


# Nombre de la cría según especie (para etiquetas de estado "ternero")
CRIA_LABEL = {
    "Bovino": "Ternero",
    "Ovino": "Cordero",
    "Caprino": "Chivo",
    "Equino": "Potro",
    "Porcino": "Lechón",
}


def label_cria(especie_nombre: str) -> str:
    return CRIA_LABEL.get(especie_nombre, "Ternero")


# Etiquetas de las raciones de alimentación (kg/animal/día) por especie.
# Los estados reproductivos (gestante/lactante/vacía/semental) son genéricos;
# solo los estados de cría cambian de nombre según la especie.
ESTADOS_RACION_BASE = {
    "gestante": "Gestante",
    "lactante": "Lactante",
    "vacia": "Vacía",
    "semental": "Semental",
}


def estados_labels_racion(especie_nombre: str) -> dict:
    cria = label_cria(especie_nombre)
    return {
        **ESTADOS_RACION_BASE,
        "ternero_lactante": f"{cria} lactante",
        "ternero_destete": f"{cria} post-destete",
    }
