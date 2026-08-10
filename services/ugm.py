from datetime import date

# Tabla de correspondencia de UGM (coeficientes oficiales por especie)
# Bovino/Ovino/Caprino: coeficiente distinto según sea joven o adulto.
# Equino: coeficiente único (la tabla oficial no distingue por edad).
UGM_COEFICIENTES = {
    "bovino": {"corte_meses": 24, "joven": 0.65, "adulto": 1.00},
    "ovino": {"corte_meses": 12, "joven": 0.05, "adulto": 0.17},
    "caprino": {"corte_meses": 12, "joven": 0.04, "adulto": 0.15},
    "equino": {"corte_meses": None, "fijo": 0.42},
}
UGM_DEFECTO = UGM_COEFICIENTES["bovino"]


def ugm_animal(animal, hoy: date = None) -> float:
    """Coeficiente UGM de un animal según su especie y edad (tabla de correspondencia oficial)."""
    hoy = hoy or date.today()
    especie_nombre = animal.especie.nombre.strip().lower() if animal.especie else "bovino"
    coef = UGM_COEFICIENTES.get(especie_nombre, UGM_DEFECTO)

    if coef.get("corte_meses") is None:
        return coef["fijo"]
    if not animal.fecha_nacimiento:
        return coef["adulto"]
    edad_meses = (hoy - animal.fecha_nacimiento).days / 30.44
    return coef["joven"] if edad_meses < coef["corte_meses"] else coef["adulto"]


def ugm_total(animales, hoy: date = None) -> float:
    """Suma de UGM de una lista de animales."""
    hoy = hoy or date.today()
    return sum(ugm_animal(a, hoy) for a in animales)


def densidad_ugm_ha(animales, hectareas: float, hoy: date = None) -> float | None:
    """UGM/ha de una parcela dado el conjunto de animales que la ocupan."""
    if not hectareas:
        return None
    return ugm_total(animales, hoy) / hectareas
