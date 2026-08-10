from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import case
from datetime import date, timedelta

from database import get_db
from auth import get_current_user
from models.tarea import Tarea
from models.usuario import Usuario

router = APIRouter(prefix="/tareas", tags=["tareas"])
templates = Jinja2Templates(directory="templates")

ORDEN_PRIORIDAD = case(
    (Tarea.prioridad == "alta", 0),
    (Tarea.prioridad == "media", 1),
    (Tarea.prioridad == "baja", 2),
    else_=3,
)


@router.get("", response_class=HTMLResponse)
def lista_tareas(
    request: Request,
    estado: str = "pendientes",
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()
    q = db.query(Tarea)
    if estado == "pendientes":
        q = q.filter(Tarea.completada == False)
    elif estado == "completadas":
        q = q.filter(Tarea.completada == True)

    if estado == "completadas":
        tareas = q.order_by(Tarea.fecha_completada.desc()).all()
    else:
        tareas = q.order_by(ORDEN_PRIORIDAD, Tarea.fecha_limite.is_(None), Tarea.fecha_limite).all()

    n_pendientes = db.query(Tarea).filter(Tarea.completada == False).count()

    return templates.TemplateResponse("tareas/lista.html", {
        "request": request,
        "tareas": tareas,
        "estado": estado,
        "n_pendientes": n_pendientes,
        "hoy": hoy,
        "current_user": current_user,
    })


@router.post("/nueva")
def nueva_tarea(
    titulo: str = Form(...),
    descripcion: str = Form(default=""),
    fecha_limite: str = Form(default=""),
    prioridad: str = Form(default="media"),
    es_recurrente: str = Form(default=""),
    periodicidad_dias: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    t = Tarea(
        titulo=titulo.strip(),
        descripcion=descripcion.strip() or None,
        fecha_limite=date.fromisoformat(fecha_limite) if fecha_limite else None,
        prioridad=prioridad or "media",
        es_recurrente=bool(es_recurrente),
        periodicidad_dias=int(periodicidad_dias) if es_recurrente and periodicidad_dias else None,
        fecha_creacion=date.today(),
    )
    db.add(t)
    db.commit()
    return RedirectResponse(url="/tareas?guardado=1", status_code=302)


@router.post("/{tarea_id}/editar")
def editar_tarea(
    tarea_id: int,
    titulo: str = Form(...),
    descripcion: str = Form(default=""),
    fecha_limite: str = Form(default=""),
    prioridad: str = Form(default="media"),
    es_recurrente: str = Form(default=""),
    periodicidad_dias: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    t = db.query(Tarea).filter(Tarea.id == tarea_id).first()
    if not t:
        raise HTTPException(status_code=404)
    t.titulo = titulo.strip()
    t.descripcion = descripcion.strip() or None
    t.fecha_limite = date.fromisoformat(fecha_limite) if fecha_limite else None
    t.prioridad = prioridad or "media"
    t.es_recurrente = bool(es_recurrente)
    t.periodicidad_dias = int(periodicidad_dias) if es_recurrente and periodicidad_dias else None
    db.commit()
    return RedirectResponse(url="/tareas?guardado=1", status_code=302)


@router.post("/{tarea_id}/completar")
def completar_tarea(
    tarea_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    t = db.query(Tarea).filter(Tarea.id == tarea_id).first()
    if not t:
        raise HTTPException(status_code=404)
    hoy = date.today()
    t.completada = True
    t.fecha_completada = hoy

    if t.es_recurrente and t.periodicidad_dias:
        base = t.fecha_limite if t.fecha_limite and t.fecha_limite > hoy else hoy
        db.add(Tarea(
            titulo=t.titulo,
            descripcion=t.descripcion,
            fecha_limite=base + timedelta(days=t.periodicidad_dias),
            prioridad=t.prioridad,
            es_recurrente=True,
            periodicidad_dias=t.periodicidad_dias,
            fecha_creacion=hoy,
        ))
    db.commit()
    return RedirectResponse(url="/tareas", status_code=302)


@router.post("/{tarea_id}/reabrir")
def reabrir_tarea(
    tarea_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    t = db.query(Tarea).filter(Tarea.id == tarea_id).first()
    if t:
        t.completada = False
        t.fecha_completada = None
        db.commit()
    return RedirectResponse(url="/tareas", status_code=302)


@router.post("/{tarea_id}/eliminar")
def eliminar_tarea(
    tarea_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    t = db.query(Tarea).filter(Tarea.id == tarea_id).first()
    if t:
        db.delete(t)
        db.commit()
    return RedirectResponse(url="/tareas", status_code=302)
