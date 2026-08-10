from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import extract
from datetime import date
from database import get_db
from auth import get_current_user
from models.maquinaria import Maquina, RevisionMaquina
from models.usuario import Usuario

router = APIRouter(prefix="/maquinaria", tags=["maquinaria"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def lista_maquinaria(
    request: Request,
    maquina_id: str = None,
    anio: int = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()
    maquinas = db.query(Maquina).order_by(Maquina.nombre).all()

    q = db.query(RevisionMaquina)
    if maquina_id:
        q = q.filter(RevisionMaquina.maquina_id == int(maquina_id))
    if anio:
        q = q.filter(extract("year", RevisionMaquina.fecha) == anio)
    revisiones = q.order_by(RevisionMaquina.fecha.desc()).all()

    anios_revision = sorted(
        {int(r[0]) for r in db.query(extract("year", RevisionMaquina.fecha)).distinct().all() if r[0]},
        reverse=True,
    )

    # Próxima fecha de revisión por máquina (última revisión con proxima_fecha calculada)
    proximas_por_maquina = {}
    for maquina in maquinas:
        ultima = db.query(RevisionMaquina).filter(
            RevisionMaquina.maquina_id == maquina.id,
            RevisionMaquina.proxima_fecha.isnot(None),
        ).order_by(RevisionMaquina.fecha.desc()).first()
        if ultima:
            proximas_por_maquina[maquina.id] = ultima.proxima_fecha

    # La más urgente de todas (vencida o más próxima) para destacarla arriba
    proxima_revision = None
    if proximas_por_maquina:
        maquina_id_urgente = min(proximas_por_maquina, key=proximas_por_maquina.get)
        proxima_revision = {
            "maquina": next(m for m in maquinas if m.id == maquina_id_urgente),
            "fecha": proximas_por_maquina[maquina_id_urgente],
        }

    tipos_usados = sorted({r[0] for r in db.query(RevisionMaquina.tipo_revision).distinct().all() if r[0]})
    talleres_usados = sorted({r[0] for r in db.query(RevisionMaquina.taller).distinct().all() if r[0]})

    return templates.TemplateResponse("maquinaria/lista.html", {
        "request": request,
        "maquinas": maquinas,
        "revisiones": revisiones,
        "proxima_revision": proxima_revision,
        "proximas_por_maquina": proximas_por_maquina,
        "hoy": hoy,
        "current_user": current_user,
        "filtro_maquina": maquina_id,
        "filtro_anio": anio,
        "anios_revision": anios_revision,
        "tipos_usados": tipos_usados,
        "talleres_usados": talleres_usados,
    })


@router.post("/nueva")
def nueva_maquina(
    nombre: str = Form(...),
    tipo: str = Form(default=""),
    marca: str = Form(default=""),
    modelo: str = Form(default=""),
    matricula: str = Form(default=""),
    num_serie: str = Form(default=""),
    fecha_compra: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    m = Maquina(
        nombre=nombre,
        tipo=tipo or None,
        marca=marca or None,
        modelo=modelo or None,
        matricula=matricula or None,
        num_serie=num_serie or None,
        fecha_compra=date.fromisoformat(fecha_compra) if fecha_compra else None,
        observaciones=observaciones or None,
    )
    db.add(m)
    db.commit()
    return RedirectResponse(url="/maquinaria?guardado=1", status_code=302)


@router.post("/{maquina_id}/editar")
def editar_maquina(
    maquina_id: int,
    nombre: str = Form(...),
    tipo: str = Form(default=""),
    marca: str = Form(default=""),
    modelo: str = Form(default=""),
    matricula: str = Form(default=""),
    num_serie: str = Form(default=""),
    fecha_compra: str = Form(default=""),
    activa: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    m = db.query(Maquina).filter(Maquina.id == maquina_id).first()
    if not m:
        raise HTTPException(status_code=404)
    m.nombre = nombre
    m.tipo = tipo or None
    m.marca = marca or None
    m.modelo = modelo or None
    m.matricula = matricula or None
    m.num_serie = num_serie or None
    m.fecha_compra = date.fromisoformat(fecha_compra) if fecha_compra else None
    m.activa = bool(activa)
    m.observaciones = observaciones or None
    db.commit()
    return RedirectResponse(url="/maquinaria?guardado=1", status_code=302)


@router.post("/{maquina_id}/eliminar")
def eliminar_maquina(
    maquina_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    m = db.query(Maquina).filter(Maquina.id == maquina_id).first()
    if m:
        db.delete(m)
        db.commit()
    return RedirectResponse(url="/maquinaria", status_code=302)


@router.post("/revision/nueva")
def nueva_revision(
    maquina_id: str = Form(...),
    fecha: str = Form(...),
    tipo_revision: str = Form(...),
    taller: str = Form(default=""),
    coste: str = Form(default=""),
    horas_km: str = Form(default=""),
    descripcion: str = Form(default=""),
    num_factura: str = Form(default=""),
    periodicidad_meses: str = Form(default=""),
    proxima_fecha: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    from dateutil.relativedelta import relativedelta
    fecha_d = date.fromisoformat(fecha)
    periodo = int(periodicidad_meses) if periodicidad_meses else None
    if proxima_fecha:
        prox = date.fromisoformat(proxima_fecha)
    elif periodo:
        prox = fecha_d + relativedelta(months=periodo)
    else:
        prox = None

    r = RevisionMaquina(
        maquina_id=int(maquina_id),
        fecha=fecha_d,
        tipo_revision=tipo_revision,
        taller=taller or None,
        coste=float(coste) if coste else None,
        horas_km=float(horas_km) if horas_km else None,
        descripcion=descripcion or None,
        num_factura=num_factura or None,
        periodicidad_meses=periodo,
        proxima_fecha=prox,
        observaciones=observaciones or None,
    )
    db.add(r)
    db.commit()
    return RedirectResponse(url="/maquinaria?guardado=1", status_code=302)


@router.post("/revision/{revision_id}/editar")
def editar_revision(
    revision_id: int,
    maquina_id: str = Form(...),
    fecha: str = Form(...),
    tipo_revision: str = Form(...),
    taller: str = Form(default=""),
    coste: str = Form(default=""),
    horas_km: str = Form(default=""),
    descripcion: str = Form(default=""),
    num_factura: str = Form(default=""),
    periodicidad_meses: str = Form(default=""),
    proxima_fecha: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    from dateutil.relativedelta import relativedelta
    r = db.query(RevisionMaquina).filter(RevisionMaquina.id == revision_id).first()
    if not r:
        raise HTTPException(status_code=404)
    fecha_d = date.fromisoformat(fecha)
    periodo = int(periodicidad_meses) if periodicidad_meses else None
    if proxima_fecha:
        prox = date.fromisoformat(proxima_fecha)
    elif periodo:
        prox = fecha_d + relativedelta(months=periodo)
    else:
        prox = None
    r.maquina_id = int(maquina_id)
    r.fecha = fecha_d
    r.tipo_revision = tipo_revision
    r.taller = taller or None
    r.coste = float(coste) if coste else None
    r.horas_km = float(horas_km) if horas_km else None
    r.descripcion = descripcion or None
    r.num_factura = num_factura or None
    r.periodicidad_meses = periodo
    r.proxima_fecha = prox
    r.observaciones = observaciones or None
    db.commit()
    return RedirectResponse(url="/maquinaria?guardado=1", status_code=302)


@router.post("/revision/{revision_id}/eliminar")
def eliminar_revision(
    revision_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    r = db.query(RevisionMaquina).filter(RevisionMaquina.id == revision_id).first()
    if r:
        db.delete(r)
        db.commit()
    return RedirectResponse(url="/maquinaria", status_code=302)
