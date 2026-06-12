"""
Exportaciones a formatos oficiales: SITRAN, ARCA/Cuaderno de campo
"""
import csv
import io
from datetime import date
from sqlalchemy.orm import Session
from models.animal import Animal, EstadoAnimal
from models.sanidad import Tratamiento
from models.reproduccion import Reproduccion


def exportar_altas_sitran(db: Session, desde: date = None, hasta: date = None) -> str:
    """Genera CSV de altas de animales en formato SITRAN."""
    q = db.query(Animal).filter(Animal.fecha_alta.isnot(None))
    if desde:
        q = q.filter(Animal.fecha_alta >= desde)
    if hasta:
        q = q.filter(Animal.fecha_alta <= hasta)
    animales = q.all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "CROTAL", "FECHA_NACIMIENTO", "FECHA_ALTA", "SEXO",
        "RAZA", "CROTAL_MADRE", "CROTAL_PADRE", "OBSERVACIONES"
    ])
    for a in animales:
        writer.writerow([
            a.crotal,
            a.fecha_nacimiento.strftime("%d/%m/%Y") if a.fecha_nacimiento else "",
            a.fecha_alta.strftime("%d/%m/%Y") if a.fecha_alta else "",
            "H" if a.sexo == "hembra" else "M",
            a.raza or "Asturiana de la Montaña",
            a.madre_crotal or "",
            a.padre_crotal or "",
            a.observaciones or "",
        ])
    return output.getvalue()


def exportar_bajas_sitran(db: Session, desde: date = None, hasta: date = None) -> str:
    """Genera CSV de bajas de animales en formato SITRAN."""
    q = db.query(Animal).filter(Animal.fecha_baja.isnot(None))
    if desde:
        q = q.filter(Animal.fecha_baja >= desde)
    if hasta:
        q = q.filter(Animal.fecha_baja <= hasta)
    animales = q.all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["CROTAL", "FECHA_BAJA", "MOTIVO", "ESTADO_FINAL"])
    for a in animales:
        writer.writerow([
            a.crotal,
            a.fecha_baja.strftime("%d/%m/%Y"),
            a.motivo_baja or "",
            a.estado,
        ])
    return output.getvalue()


def exportar_cuaderno_arca(db: Session, desde: date = None, hasta: date = None) -> str:
    """
    Genera CSV del cuaderno de campo para ARCA/REGEPA.
    Incluye tratamientos con principio activo, dosis, veterinario y tiempo de espera.
    """
    q = db.query(Tratamiento).order_by(Tratamiento.fecha.desc())
    if desde:
        q = q.filter(Tratamiento.fecha >= desde)
    if hasta:
        q = q.filter(Tratamiento.fecha <= hasta)
    tratamientos = q.all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "FECHA", "CROTAL_ANIMAL", "MEDICAMENTO", "PRINCIPIO_ACTIVO",
        "DOSIS", "VIA_ADMINISTRACION", "DIAS_ESPERA", "FECHA_FIN_ESPERA",
        "VETERINARIO", "NUM_RECETA", "ES_ECOLOGICO", "OBSERVACIONES"
    ])
    for t in tratamientos:
        writer.writerow([
            t.fecha.strftime("%d/%m/%Y"),
            t.animal_crotal,
            t.medicamento,
            t.principio_activo or "",
            t.dosis or "",
            t.via_administracion or "",
            t.dias_tiempo_espera,
            t.fecha_fin_espera.strftime("%d/%m/%Y") if t.fecha_fin_espera else "",
            t.veterinario or "",
            t.num_receta or "",
            "SI" if t.es_ecologico else "NO",
            t.observaciones or "",
        ])
    return output.getvalue()


def exportar_censo_actual(db: Session) -> str:
    """Lista del censo actual para PAC/declaraciones."""
    animales = db.query(Animal).filter(Animal.fecha_baja.is_(None)).order_by(Animal.crotal).all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "CROTAL", "NOMBRE", "SEXO", "ESTADO", "FECHA_NACIMIENTO",
        "RAZA", "LOTE", "MADRE", "PADRE"
    ])
    for a in animales:
        writer.writerow([
            a.crotal,
            a.nombre or "",
            a.sexo,
            a.estado,
            a.fecha_nacimiento.strftime("%d/%m/%Y") if a.fecha_nacimiento else "",
            a.raza or "",
            a.lote.nombre if a.lote else "",
            a.madre_crotal or "",
            a.padre_crotal or "",
        ])
    return output.getvalue()
