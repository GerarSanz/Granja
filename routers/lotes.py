from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date
from database import get_db
from auth import get_current_user
from models.lote import Lote, Parcela, OcupacionParcela, AsignacionToro
from models.animal import Animal
from models.usuario import Usuario

router = APIRouter(prefix="/lotes", tags=["lotes"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def lista_lotes(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()
    lotes = db.query(Lote).all()
    parcelas = db.query(Parcela).all()

    # Ocupación actual por lote
    ocupaciones_activas = db.query(OcupacionParcela).filter(
        OcupacionParcela.fecha_salida.is_(None)
    ).all()

    # Toros actualmente en lotes
    toros_activos = db.query(AsignacionToro).filter(
        AsignacionToro.fecha_salida.is_(None)
    ).all()

    # Conteo de animales por lote
    conteo_lotes = {}
    for lote in lotes:
        conteo_lotes[lote.id] = db.query(Animal).filter(
            Animal.lote_id == lote.id,
            Animal.fecha_baja.is_(None),
        ).count()

    animales_sin_lote = db.query(Animal).filter(
        Animal.lote_id.is_(None),
        Animal.fecha_baja.is_(None),
    ).all()

    toros = db.query(Animal).filter(
        Animal.sexo == "macho",
        Animal.fecha_baja.is_(None),
    ).all()

    return templates.TemplateResponse("lotes/lista.html", {
        "request": request,
        "lotes": lotes,
        "parcelas": parcelas,
        "ocupaciones_activas": ocupaciones_activas,
        "toros_activos": toros_activos,
        "conteo_lotes": conteo_lotes,
        "animales_sin_lote": animales_sin_lote,
        "toros": toros,
        "hoy": hoy,
        "current_user": current_user,
    })


@router.post("/nuevo")
def crear_lote(
    nombre: str = Form(...),
    descripcion: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lote = Lote(nombre=nombre, descripcion=descripcion or None)
    db.add(lote)
    db.commit()
    return RedirectResponse(url="/lotes", status_code=302)


@router.post("/parcela/nueva")
def crear_parcela(
    nombre: str = Form(...),
    hectareas: float = Form(...),
    referencia_catastral: str = Form(default=""),
    municipio: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    p = Parcela(
        nombre=nombre,
        hectareas=hectareas,
        referencia_catastral=referencia_catastral or None,
        municipio=municipio or None,
    )
    db.add(p)
    db.commit()
    return RedirectResponse(url="/lotes", status_code=302)


@router.post("/ocupacion/nueva")
def nueva_ocupacion(
    lote_id: int = Form(...),
    parcela_id: int = Form(...),
    fecha_entrada: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Cerrar ocupación anterior del lote en otra parcela si existe
    prev = db.query(OcupacionParcela).filter(
        OcupacionParcela.lote_id == lote_id,
        OcupacionParcela.fecha_salida.is_(None),
    ).first()
    if prev:
        prev.fecha_salida = date.fromisoformat(fecha_entrada)

    oc = OcupacionParcela(
        lote_id=lote_id,
        parcela_id=parcela_id,
        fecha_entrada=date.fromisoformat(fecha_entrada),
    )
    db.add(oc)
    db.commit()
    return RedirectResponse(url="/lotes", status_code=302)


@router.post("/toro/asignar")
def asignar_toro(
    toro_crotal: str = Form(...),
    lote_id: int = Form(...),
    fecha_entrada: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Cerrar asignación anterior del toro si existe
    prev = db.query(AsignacionToro).filter(
        AsignacionToro.toro_crotal == toro_crotal.upper(),
        AsignacionToro.fecha_salida.is_(None),
    ).first()
    if prev:
        prev.fecha_salida = date.fromisoformat(fecha_entrada)

    at = AsignacionToro(
        toro_crotal=toro_crotal.upper(),
        lote_id=lote_id,
        fecha_entrada=date.fromisoformat(fecha_entrada),
    )
    db.add(at)
    db.commit()
    return RedirectResponse(url="/lotes", status_code=302)


@router.post("/toro/{asignacion_id}/retirar")
def retirar_toro(
    asignacion_id: int,
    fecha_salida: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    at = db.query(AsignacionToro).filter(AsignacionToro.id == asignacion_id).first()
    if at:
        at.fecha_salida = date.fromisoformat(fecha_salida)
        db.commit()
    return RedirectResponse(url="/lotes", status_code=302)
