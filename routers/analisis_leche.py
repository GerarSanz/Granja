from datetime import date

from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
from models.usuario import Usuario
from models.analisis_leche import AnalisisLeche
from services.analisis_leche_parser import parsear_pdf_lila
from services.analisis_leche_pdf import guardar_pdf, pdf_url, eliminar_pdf

router = APIRouter(prefix="/analisis-leche", tags=["analisis_leche"])
templates = Jinja2Templates(directory="templates")

# Igual que en la importación de animales: el PDF subido se guarda en memoria
# por usuario entre el preview y la confirmación, para no obligar a
# reseleccionar el fichero al confirmar.
_import_cache: dict[int, bytes] = {}


class AnalisisLecheForm:
    CAMPOS = (
        "numero_informe", "numero_recepcion", "numero_muestra", "descripcion_muestra",
        "producto", "fecha_toma", "fecha_recepcion", "fecha_emision_informe",
        "bactoscan", "celulas_somaticas", "crioscopia", "extracto_seco_magro",
        "materia_grasa", "lactosa", "proteina", "urea", "inhibidores", "observaciones",
    )

    def __init__(
        self,
        numero_informe: str = Form(default=""),
        numero_recepcion: str = Form(default=""),
        numero_muestra: str = Form(default=""),
        descripcion_muestra: str = Form(default=""),
        producto: str = Form(default=""),
        fecha_toma: str = Form(...),
        fecha_recepcion: str = Form(default=""),
        fecha_emision_informe: str = Form(default=""),
        bactoscan: str = Form(default=""),
        celulas_somaticas: str = Form(default=""),
        crioscopia: str = Form(default=""),
        extracto_seco_magro: str = Form(default=""),
        materia_grasa: str = Form(default=""),
        lactosa: str = Form(default=""),
        proteina: str = Form(default=""),
        urea: str = Form(default=""),
        inhibidores: str = Form(default=""),
        observaciones: str = Form(default=""),
    ):
        self.numero_informe = numero_informe or None
        self.numero_recepcion = numero_recepcion or None
        self.numero_muestra = numero_muestra or None
        self.descripcion_muestra = descripcion_muestra or None
        self.producto = producto or None
        self.fecha_toma = date.fromisoformat(fecha_toma)
        self.fecha_recepcion = date.fromisoformat(fecha_recepcion) if fecha_recepcion else None
        self.fecha_emision_informe = date.fromisoformat(fecha_emision_informe) if fecha_emision_informe else None
        self.bactoscan = float(bactoscan) if bactoscan else None
        self.celulas_somaticas = float(celulas_somaticas) if celulas_somaticas else None
        self.crioscopia = float(crioscopia) if crioscopia else None
        self.extracto_seco_magro = float(extracto_seco_magro) if extracto_seco_magro else None
        self.materia_grasa = float(materia_grasa) if materia_grasa else None
        self.lactosa = float(lactosa) if lactosa else None
        self.proteina = float(proteina) if proteina else None
        self.urea = float(urea) if urea else None
        self.inhibidores = inhibidores or None
        self.observaciones = observaciones or None

    def aplicar(self, analisis: AnalisisLeche):
        for campo in self.CAMPOS:
            setattr(analisis, campo, getattr(self, campo))


@router.get("", response_class=HTMLResponse)
def lista_analisis(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    analisis = db.query(AnalisisLeche).order_by(AnalisisLeche.fecha_toma.desc()).all()
    return templates.TemplateResponse("analisis_leche/lista.html", {
        "request": request,
        "analisis": analisis,
        "ultimo": analisis[0] if analisis else None,
        "pdf_urls": {a.id: pdf_url(a.id) for a in analisis},
        "hoy": date.today(),
        "current_user": current_user,
    })


@router.get("/importar", response_class=HTMLResponse)
def importar_form(
    request: Request,
    current_user: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse("analisis_leche/importar.html", {
        "request": request,
        "current_user": current_user,
        "preview": None,
    })


@router.post("/importar/preview", response_class=HTMLResponse)
async def importar_preview(
    request: Request,
    archivo: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_user),
):
    if not archivo.filename.lower().endswith(".pdf"):
        return templates.TemplateResponse("analisis_leche/importar.html", {
            "request": request, "current_user": current_user, "preview": None,
            "error": "El archivo debe ser un PDF.",
        })

    contenido = await archivo.read()
    datos = parsear_pdf_lila(contenido)
    _import_cache[current_user.id] = contenido

    return templates.TemplateResponse("analisis_leche/importar.html", {
        "request": request,
        "current_user": current_user,
        "preview": datos,
        "archivo_nombre": archivo.filename,
        "reconocido": bool(datos.get("numero_informe") and datos.get("fecha_toma")),
    })


@router.post("/importar/confirmar")
def importar_confirmar(
    datos: AnalisisLecheForm = Depends(),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    contenido = _import_cache.pop(current_user.id, None)

    analisis = AnalisisLeche()
    datos.aplicar(analisis)
    db.add(analisis)
    db.commit()
    db.refresh(analisis)

    if contenido:
        guardar_pdf(analisis.id, contenido)

    return RedirectResponse(url="/analisis-leche?guardado=1", status_code=302)


@router.post("/nuevo")
def nuevo_analisis(
    datos: AnalisisLecheForm = Depends(),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    analisis = AnalisisLeche()
    datos.aplicar(analisis)
    db.add(analisis)
    db.commit()
    return RedirectResponse(url="/analisis-leche?guardado=1", status_code=302)


@router.post("/{analisis_id}/editar")
def editar_analisis(
    analisis_id: int,
    datos: AnalisisLecheForm = Depends(),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    analisis = db.query(AnalisisLeche).filter(AnalisisLeche.id == analisis_id).first()
    if not analisis:
        raise HTTPException(status_code=404)
    datos.aplicar(analisis)
    db.commit()
    return RedirectResponse(url="/analisis-leche?guardado=1", status_code=302)


@router.post("/{analisis_id}/eliminar")
def eliminar_analisis(
    analisis_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    analisis = db.query(AnalisisLeche).filter(AnalisisLeche.id == analisis_id).first()
    if analisis:
        db.delete(analisis)
        db.commit()
        eliminar_pdf(analisis_id)
    return RedirectResponse(url="/analisis-leche", status_code=302)
