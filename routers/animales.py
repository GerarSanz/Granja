from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import date
from database import get_db
from auth import get_current_user
from models.animal import Animal, EstadoAnimal, SexoAnimal
from models.lote import Lote
from models.reproduccion import Reproduccion
from models.usuario import Usuario

router = APIRouter(prefix="/animales", tags=["animales"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def lista_animales(
    request: Request,
    estado: str = None,
    sexo: str = None,
    lote_id: int = None,
    buscar: str = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    q = db.query(Animal).filter(Animal.fecha_baja.is_(None))
    if estado:
        q = q.filter(Animal.estado == estado)
    if sexo:
        q = q.filter(Animal.sexo == sexo)
    if lote_id:
        q = q.filter(Animal.lote_id == lote_id)
    if buscar:
        q = q.filter(or_(Animal.crotal.contains(buscar), Animal.nombre.contains(buscar)))
    animales = q.order_by(Animal.crotal).all()
    lotes = db.query(Lote).all()
    return templates.TemplateResponse("animales/lista.html", {
        "request": request,
        "animales": animales,
        "lotes": lotes,
        "estados": EstadoAnimal,
        "filtro_estado": estado,
        "filtro_sexo": sexo,
        "filtro_lote": lote_id,
        "buscar": buscar,
        "current_user": current_user,
    })


@router.get("/nuevo", response_class=HTMLResponse)
def nuevo_animal_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lotes = db.query(Lote).all()
    hembras = db.query(Animal).filter(Animal.sexo == SexoAnimal.hembra, Animal.fecha_baja.is_(None)).all()
    machos = db.query(Animal).filter(Animal.sexo == SexoAnimal.macho, Animal.fecha_baja.is_(None)).all()
    return templates.TemplateResponse("animales/form.html", {
        "request": request,
        "animal": None,
        "lotes": lotes,
        "hembras": hembras,
        "machos": machos,
        "estados": EstadoAnimal,
        "current_user": current_user,
    })


@router.post("/nuevo")
def crear_animal(
    request: Request,
    crotal: str = Form(...),
    nombre: str = Form(default=""),
    sexo: str = Form(...),
    fecha_nacimiento: str = Form(default=""),
    madre_crotal: str = Form(default=""),
    padre_crotal: str = Form(default=""),
    lote_id: str = Form(default=""),
    estado: str = Form(...),
    peso_entrada: str = Form(default=""),
    fecha_alta: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if db.query(Animal).filter(Animal.crotal == crotal).first():
        lotes = db.query(Lote).all()
        return templates.TemplateResponse("animales/form.html", {
            "request": request, "animal": None, "lotes": lotes,
            "error": f"El crotal {crotal} ya existe", "current_user": current_user,
            "estados": EstadoAnimal,
        }, status_code=400)

    animal = Animal(
        crotal=crotal.strip().upper(),
        nombre=nombre.strip() or None,
        sexo=sexo,
        fecha_nacimiento=date.fromisoformat(fecha_nacimiento) if fecha_nacimiento else None,
        madre_crotal=madre_crotal.strip().upper() or None,
        padre_crotal=padre_crotal.strip().upper() or None,
        lote_id=int(lote_id) if lote_id else None,
        estado=estado,
        peso_entrada=float(peso_entrada) if peso_entrada else None,
        fecha_alta=date.fromisoformat(fecha_alta) if fecha_alta else date.today(),
        observaciones=observaciones.strip() or None,
    )
    db.add(animal)
    db.commit()
    return RedirectResponse(url=f"/animales/{animal.crotal}", status_code=302)


@router.get("/{crotal}", response_class=HTMLResponse)
def ficha_animal(
    crotal: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    animal = db.query(Animal).filter(Animal.crotal == crotal.upper()).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal no encontrado")
    reproducciones = db.query(Reproduccion).filter(
        Reproduccion.animal_crotal == crotal.upper()
    ).order_by(Reproduccion.fecha_cubricion.desc()).all()
    lotes = db.query(Lote).all()
    return templates.TemplateResponse("animales/ficha.html", {
        "request": request,
        "animal": animal,
        "reproducciones": reproducciones,
        "lotes": lotes,
        "current_user": current_user,
    })


@router.post("/{crotal}/editar")
def editar_animal(
    crotal: str,
    nombre: str = Form(default=""),
    estado: str = Form(...),
    lote_id: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    animal = db.query(Animal).filter(Animal.crotal == crotal.upper()).first()
    if not animal:
        raise HTTPException(status_code=404)
    animal.nombre = nombre.strip() or animal.nombre
    animal.estado = estado
    animal.lote_id = int(lote_id) if lote_id else None
    animal.observaciones = observaciones.strip() or None
    db.commit()
    return RedirectResponse(url=f"/animales/{crotal}", status_code=302)


@router.post("/{crotal}/baja")
def dar_baja(
    crotal: str,
    fecha_baja: str = Form(...),
    motivo_baja: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    animal = db.query(Animal).filter(Animal.crotal == crotal.upper()).first()
    if not animal:
        raise HTTPException(status_code=404)
    animal.fecha_baja = date.fromisoformat(fecha_baja)
    animal.motivo_baja = motivo_baja
    animal.estado = EstadoAnimal.vendido if "venta" in motivo_baja.lower() else EstadoAnimal.baja
    db.commit()
    return RedirectResponse(url="/animales", status_code=302)
