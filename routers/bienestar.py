from datetime import date

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
from models.bienestar import (
    AuditoriaBienestar, IndicadorBienestar,
    TipoAuditoriaBienestar, CategoriaBienestar, INDICADORES_DEFECTO,
)
from models.lote import Lote
from models.usuario import Usuario

router = APIRouter(prefix="/bienestar", tags=["bienestar"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def lista_bienestar(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    auditorias = db.query(AuditoriaBienestar).order_by(AuditoriaBienestar.fecha.desc()).all()
    ultima = auditorias[0] if auditorias else None
    acciones_abiertas = db.query(IndicadorBienestar).filter(
        IndicadorBienestar.accion_correctora.isnot(None),
        IndicadorBienestar.accion_resuelta == False,
    ).count()

    return templates.TemplateResponse("bienestar/lista.html", {
        "request": request,
        "auditorias": auditorias,
        "ultima": ultima,
        "acciones_abiertas": acciones_abiertas,
        "hoy": date.today(),
        "current_user": current_user,
    })


@router.get("/nueva", response_class=HTMLResponse)
def nueva_auditoria_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lotes = db.query(Lote).order_by(Lote.nombre).all()
    return templates.TemplateResponse("bienestar/form.html", {
        "request": request,
        "lotes": lotes,
        "tipos": TipoAuditoriaBienestar,
        "indicadores_defecto": INDICADORES_DEFECTO,
        "hoy": date.today(),
        "current_user": current_user,
    })


@router.post("/nueva")
async def nueva_auditoria(
    request: Request,
    fecha: str = Form(...),
    tipo: str = Form(...),
    responsable: str = Form(default=""),
    lote_id: str = Form(default=""),
    observaciones_generales: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    form = await request.form()
    categorias = form.getlist("categoria")
    indicadores = form.getlist("indicador")
    puntuaciones = form.getlist("puntuacion")
    observaciones = form.getlist("obs_indicador")
    acciones = form.getlist("accion_correctora")
    fechas_limite = form.getlist("fecha_limite_accion")

    auditoria = AuditoriaBienestar(
        fecha=date.fromisoformat(fecha),
        tipo=tipo,
        responsable=responsable or None,
        lote_id=int(lote_id) if lote_id else None,
        observaciones_generales=observaciones_generales or None,
    )
    db.add(auditoria)
    db.flush()

    orden = 0
    for categoria, texto, puntuacion, obs, accion, fecha_limite in zip(
        categorias, indicadores, puntuaciones, observaciones, acciones, fechas_limite
    ):
        if not texto or not texto.strip():
            continue
        db.add(IndicadorBienestar(
            auditoria_id=auditoria.id,
            categoria=categoria,
            indicador=texto.strip(),
            puntuacion=int(puntuacion) if puntuacion not in (None, "") else None,
            observaciones=obs.strip() if obs and obs.strip() else None,
            accion_correctora=accion.strip() if accion and accion.strip() else None,
            fecha_limite_accion=date.fromisoformat(fecha_limite) if fecha_limite else None,
            orden=orden,
        ))
        orden += 1

    db.commit()
    return RedirectResponse(url=f"/bienestar/{auditoria.id}?guardado=1", status_code=302)


@router.get("/{auditoria_id}", response_class=HTMLResponse)
def detalle_auditoria(
    auditoria_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    auditoria = db.query(AuditoriaBienestar).filter(AuditoriaBienestar.id == auditoria_id).first()
    if not auditoria:
        raise HTTPException(status_code=404)

    indicadores_por_categoria = {}
    for ind in auditoria.indicadores:
        indicadores_por_categoria.setdefault(ind.categoria, []).append(ind)

    lotes = db.query(Lote).order_by(Lote.nombre).all()
    return templates.TemplateResponse("bienestar/detalle.html", {
        "request": request,
        "auditoria": auditoria,
        "indicadores_por_categoria": indicadores_por_categoria,
        "categorias": CategoriaBienestar,
        "tipos": TipoAuditoriaBienestar,
        "lotes": lotes,
        "hoy": date.today(),
        "current_user": current_user,
    })


@router.post("/{auditoria_id}/editar")
def editar_cabecera_auditoria(
    auditoria_id: int,
    fecha: str = Form(...),
    tipo: str = Form(...),
    responsable: str = Form(default=""),
    lote_id: str = Form(default=""),
    observaciones_generales: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    auditoria = db.query(AuditoriaBienestar).filter(AuditoriaBienestar.id == auditoria_id).first()
    if not auditoria:
        raise HTTPException(status_code=404)
    auditoria.fecha = date.fromisoformat(fecha)
    auditoria.tipo = tipo
    auditoria.responsable = responsable or None
    auditoria.lote_id = int(lote_id) if lote_id else None
    auditoria.observaciones_generales = observaciones_generales or None
    db.commit()
    return RedirectResponse(url=f"/bienestar/{auditoria_id}?guardado=1", status_code=302)


@router.post("/{auditoria_id}/eliminar")
def eliminar_auditoria(
    auditoria_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    auditoria = db.query(AuditoriaBienestar).filter(AuditoriaBienestar.id == auditoria_id).first()
    if auditoria:
        db.delete(auditoria)
        db.commit()
    return RedirectResponse(url="/bienestar", status_code=302)


@router.post("/indicador/{indicador_id}/editar")
def editar_indicador(
    indicador_id: int,
    puntuacion: str = Form(default=""),
    observaciones: str = Form(default=""),
    accion_correctora: str = Form(default=""),
    fecha_limite_accion: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ind = db.query(IndicadorBienestar).filter(IndicadorBienestar.id == indicador_id).first()
    if not ind:
        raise HTTPException(status_code=404)
    ind.puntuacion = int(puntuacion) if puntuacion not in (None, "") else None
    ind.observaciones = observaciones.strip() or None
    accion_nueva = accion_correctora.strip() or None
    if accion_nueva != ind.accion_correctora:
        ind.accion_resuelta = False  # una acción correctora nueva/editada vuelve a estar pendiente
    ind.accion_correctora = accion_nueva
    ind.fecha_limite_accion = date.fromisoformat(fecha_limite_accion) if fecha_limite_accion else None
    db.commit()
    return RedirectResponse(url=f"/bienestar/{ind.auditoria_id}?guardado=1", status_code=302)


@router.post("/indicador/{indicador_id}/resolver")
def resolver_accion(
    indicador_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ind = db.query(IndicadorBienestar).filter(IndicadorBienestar.id == indicador_id).first()
    if not ind:
        raise HTTPException(status_code=404)
    ind.accion_resuelta = not ind.accion_resuelta
    db.commit()
    return RedirectResponse(url=f"/bienestar/{ind.auditoria_id}", status_code=302)
