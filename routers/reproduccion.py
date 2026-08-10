from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date, timedelta
from database import get_db
from auth import get_current_user
from models.animal import Animal, EstadoAnimal, SexoAnimal
from models.reproduccion import Reproduccion, TipoParto
from models.usuario import Usuario
from config import get_settings
from services.especies import dias_gestacion

router = APIRouter(prefix="/reproduccion", tags=["reproduccion"])
templates = Jinja2Templates(directory="templates")
settings = get_settings()


@router.get("", response_class=HTMLResponse)
def lista_reproduccion(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()
    proximos_partos = db.query(Reproduccion).filter(
        Reproduccion.parto_fecha.is_(None),
        Reproduccion.fecha_parto_estimada.isnot(None),
        Reproduccion.fecha_parto_estimada >= hoy,
    ).order_by(Reproduccion.fecha_parto_estimada).all()

    partos_recientes = db.query(Reproduccion).filter(
        Reproduccion.parto_fecha.isnot(None),
    ).order_by(Reproduccion.parto_fecha.desc()).limit(20).all()

    pendientes_destete = db.query(Reproduccion).filter(
        Reproduccion.parto_fecha.isnot(None),
        Reproduccion.destete_fecha.is_(None),
        Reproduccion.ternero_vivo == 1,
    ).all()

    vacas_vacias = db.query(Animal).filter(
        Animal.sexo == SexoAnimal.hembra,
        Animal.estado == EstadoAnimal.vacia,
        Animal.fecha_baja.is_(None),
    ).all()

    return templates.TemplateResponse("reproduccion/lista.html", {
        "request": request,
        "proximos_partos": proximos_partos,
        "partos_recientes": partos_recientes,
        "pendientes_destete": pendientes_destete,
        "vacas_vacias": vacas_vacias,
        "hoy": hoy,
        "current_user": current_user,
    })


@router.get("/cubricion/nueva", response_class=HTMLResponse)
def nueva_cubricion_form(
    request: Request,
    animal_crotal: str = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hembras = db.query(Animal).filter(
        Animal.sexo == SexoAnimal.hembra,
        Animal.fecha_baja.is_(None),
        Animal.estado.in_([EstadoAnimal.vacia, EstadoAnimal.lactante]),
    ).order_by(Animal.crotal).all()
    toros = db.query(Animal).filter(
        Animal.sexo == SexoAnimal.macho,
        Animal.fecha_baja.is_(None),
    ).order_by(Animal.crotal).all()
    return templates.TemplateResponse("reproduccion/form_cubricion.html", {
        "request": request,
        "hembras": hembras,
        "toros": toros,
        "animal_crotal_preseleccionado": animal_crotal,
        "hoy": date.today().isoformat(),
        "current_user": current_user,
    })


@router.post("/cubricion/nueva")
def registrar_cubricion(
    animal_crotal: str = Form(...),
    toro_crotal: str = Form(default=""),
    fecha_cubricion: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    fecha = date.fromisoformat(fecha_cubricion)
    animal = db.query(Animal).filter(Animal.crotal == animal_crotal.upper()).first()
    dias = dias_gestacion(animal.especie if animal else None)
    rep = Reproduccion(
        animal_crotal=animal_crotal.upper(),
        toro_crotal=toro_crotal.upper() or None,
        fecha_cubricion=fecha,
        fecha_parto_estimada=fecha + timedelta(days=dias),
    )
    db.add(rep)

    if animal:
        animal.estado = EstadoAnimal.gestante
    db.commit()
    return RedirectResponse(url="/reproduccion?guardado=1", status_code=302)


@router.post("/parto/{rep_id}")
def registrar_parto(
    rep_id: int,
    parto_fecha: str = Form(...),
    parto_tipo: str = Form(...),
    ternero_crotal: str = Form(default=""),
    ternero_sexo: str = Form(default=""),
    ternero_peso: str = Form(default=""),
    ternero_vivo: str = Form(default=""),
    parto_observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    rep = db.query(Reproduccion).filter(Reproduccion.id == rep_id).first()
    if not rep:
        raise HTTPException(status_code=404)

    rep.parto_fecha = date.fromisoformat(parto_fecha)
    rep.parto_tipo = parto_tipo
    rep.parto_observaciones = parto_observaciones or None
    rep.ternero_vivo = 1 if ternero_vivo else 0

    if ternero_crotal:
        rep.ternero_crotal = ternero_crotal.strip().upper()
        rep.ternero_sexo = ternero_sexo or None
        rep.ternero_peso_nacimiento = float(ternero_peso) if ternero_peso else None

        # Crear ficha del ternero si no existe
        if not db.query(Animal).filter(Animal.crotal == rep.ternero_crotal).first():
            madre_para_cria = db.query(Animal).filter(Animal.crotal == rep.animal_crotal).first()
            ternero = Animal(
                crotal=rep.ternero_crotal,
                sexo=ternero_sexo or SexoAnimal.macho,
                fecha_nacimiento=rep.parto_fecha,
                madre_crotal=rep.animal_crotal,
                padre_crotal=rep.toro_crotal,
                estado=EstadoAnimal.ternero,
                especie_id=madre_para_cria.especie_id if madre_para_cria else None,
                peso_entrada=float(ternero_peso) if ternero_peso else None,
                fecha_alta=rep.parto_fecha,
                lote_id=madre_para_cria.lote_id if madre_para_cria else None,
            )
            db.add(ternero)

    # Actualizar estado de la madre
    madre = db.query(Animal).filter(Animal.crotal == rep.animal_crotal).first()
    if madre and parto_tipo != "aborto" and ternero_vivo:
        madre.estado = EstadoAnimal.lactante
    elif madre:
        madre.estado = EstadoAnimal.vacia

    db.commit()
    return RedirectResponse(url="/reproduccion?guardado=1", status_code=302)


@router.post("/destete/{rep_id}")
def registrar_destete(
    rep_id: int,
    destete_fecha: str = Form(...),
    destete_peso: str = Form(default=""),
    destete_destino: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    rep = db.query(Reproduccion).filter(Reproduccion.id == rep_id).first()
    if not rep:
        raise HTTPException(status_code=404)

    rep.destete_fecha = date.fromisoformat(destete_fecha)
    rep.destete_peso = float(destete_peso) if destete_peso else None
    rep.destete_destino = destete_destino or None

    # Actualizar estado de madre y ternero
    madre = db.query(Animal).filter(Animal.crotal == rep.animal_crotal).first()
    if madre:
        madre.estado = EstadoAnimal.vacia

    if rep.ternero_crotal:
        ternero = db.query(Animal).filter(Animal.crotal == rep.ternero_crotal).first()
        if ternero:
            ternero.estado = EstadoAnimal.recria

    db.commit()
    return RedirectResponse(url="/reproduccion?guardado=1", status_code=302)
