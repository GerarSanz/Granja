from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from config import get_settings
from models.queseria import LoteQueso, EtapaQueso
from models.animal import Animal
from services.animal_foto import foto_url

router = APIRouter(prefix="/trazabilidad", tags=["trazabilidad"])
templates = Jinja2Templates(directory="templates")

TIPO_LABEL = {
    "fresco": "Fresco",
    "tierno": "Tierno",
    "semicurado": "Semicurado",
    "curado": "Curado",
    "afuega_el_pitu": "Afuega'l Pitu",
    "otro": "Queso artesano",
}


@router.get("/{codigo}", response_class=HTMLResponse)
def ficha_publica(codigo: str, request: Request, db: Session = Depends(get_db)):
    lote = db.query(LoteQueso).filter(LoteQueso.codigo == codigo.upper()).first()
    if not lote or lote.etapa != EtapaQueso.listo:
        raise HTTPException(status_code=404)

    settings = get_settings()
    dias_curacion_reales = None
    if lote.fecha_inicio_curacion and lote.fecha_listo:
        dias_curacion_reales = (lote.fecha_listo - lote.fecha_inicio_curacion).days

    crotales = [c.strip() for c in (lote.animales_crotales or "").split(",") if c.strip()]
    animales = db.query(Animal).filter(Animal.crotal.in_(crotales)).all() if crotales else []
    vacas_origen = [{"animal": a, "foto_url": foto_url(a.crotal)} for a in animales]

    return templates.TemplateResponse("trazabilidad/ficha.html", {
        "request": request,
        "lote": lote,
        "tipo_label": TIPO_LABEL.get(lote.tipo_queso, lote.tipo_queso),
        "dias_curacion_reales": dias_curacion_reales,
        "vacas_origen": vacas_origen,
        "explotacion_nombre": settings.EXPLOTACION_NOMBRE,
    })
