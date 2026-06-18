from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
from models.maestros import Especie, Raza
from models.usuario import Usuario

router = APIRouter(prefix="/maestros", tags=["maestros"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    especies = db.query(Especie).order_by(Especie.nombre).all()
    razas = db.query(Raza).order_by(Raza.especie_id, Raza.nombre).all()
    return templates.TemplateResponse("maestros/index.html", {
        "request": request,
        "especies": especies,
        "razas": razas,
        "current_user": current_user,
    })


@router.post("/especie/nueva")
def nueva_especie(
    nombre: str = Form(...),
    codigo: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not db.query(Especie).filter(Especie.nombre == nombre.strip()).first():
        db.add(Especie(nombre=nombre.strip(), codigo=codigo.strip() or None))
        db.commit()
    return RedirectResponse(url="/maestros", status_code=302)


@router.post("/especie/{especie_id}/eliminar")
def eliminar_especie(
    especie_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    e = db.query(Especie).filter(Especie.id == especie_id).first()
    if e and not e.razas:
        db.delete(e)
        db.commit()
    return RedirectResponse(url="/maestros", status_code=302)


@router.post("/raza/nueva")
def nueva_raza(
    nombre: str = Form(...),
    especie_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db.add(Raza(nombre=nombre.strip(), especie_id=especie_id))
    db.commit()
    return RedirectResponse(url="/maestros", status_code=302)


@router.post("/raza/{raza_id}/eliminar")
def eliminar_raza(
    raza_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    r = db.query(Raza).filter(Raza.id == raza_id).first()
    if r:
        db.delete(r)
        db.commit()
    return RedirectResponse(url="/maestros", status_code=302)
