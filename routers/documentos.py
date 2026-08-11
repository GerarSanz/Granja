from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
from models.documento import Documento, TipoDocumento
from models.usuario import Usuario
from services.documento_archivo import guardar_archivo, archivo_url, eliminar_archivo

router = APIRouter(prefix="/documentos", tags=["documentos"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def lista_documentos(
    request: Request,
    tipo: str = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()
    q = db.query(Documento)
    if tipo:
        q = q.filter(Documento.tipo == tipo)
    documentos = q.order_by(Documento.fecha_caducidad.is_(None), Documento.fecha_caducidad).all()

    vencidos = db.query(Documento).filter(
        Documento.fecha_caducidad.isnot(None), Documento.fecha_caducidad < hoy
    ).count()
    proximos = db.query(Documento).filter(
        Documento.fecha_caducidad.isnot(None),
        Documento.fecha_caducidad >= hoy,
        Documento.fecha_caducidad <= hoy + timedelta(days=30),
    ).count()

    return templates.TemplateResponse("documentos/lista.html", {
        "request": request,
        "documentos": documentos,
        "archivo_urls": {d.id: archivo_url(d.id, d.archivo_ext) for d in documentos},
        "tipos": TipoDocumento,
        "filtro_tipo": tipo,
        "total": len(documentos) if not tipo else db.query(Documento).count(),
        "vencidos": vencidos,
        "proximos": proximos,
        "hoy": hoy,
        "current_user": current_user,
    })


@router.post("/nuevo")
async def nuevo_documento(
    tipo: str = Form(...),
    titulo: str = Form(...),
    entidad: str = Form(default=""),
    num_referencia: str = Form(default=""),
    fecha_emision: str = Form(default=""),
    fecha_caducidad: str = Form(default=""),
    observaciones: str = Form(default=""),
    archivo: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    documento = Documento(
        tipo=tipo,
        titulo=titulo.strip(),
        entidad=entidad or None,
        num_referencia=num_referencia or None,
        fecha_emision=date.fromisoformat(fecha_emision) if fecha_emision else None,
        fecha_caducidad=date.fromisoformat(fecha_caducidad) if fecha_caducidad else None,
        observaciones=observaciones or None,
    )
    db.add(documento)
    db.flush()

    if archivo and archivo.filename:
        contenido = await archivo.read()
        ext = guardar_archivo(documento.id, archivo.filename, contenido)
        if ext:
            documento.archivo_nombre = archivo.filename
            documento.archivo_ext = ext

    db.commit()
    return RedirectResponse(url="/documentos?guardado=1", status_code=302)


@router.post("/{documento_id}/editar")
async def editar_documento(
    documento_id: int,
    tipo: str = Form(...),
    titulo: str = Form(...),
    entidad: str = Form(default=""),
    num_referencia: str = Form(default=""),
    fecha_emision: str = Form(default=""),
    fecha_caducidad: str = Form(default=""),
    observaciones: str = Form(default=""),
    archivo: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    if not documento:
        raise HTTPException(status_code=404)

    documento.tipo = tipo
    documento.titulo = titulo.strip()
    documento.entidad = entidad or None
    documento.num_referencia = num_referencia or None
    documento.fecha_emision = date.fromisoformat(fecha_emision) if fecha_emision else None
    documento.fecha_caducidad = date.fromisoformat(fecha_caducidad) if fecha_caducidad else None
    documento.observaciones = observaciones or None

    if archivo and archivo.filename:
        contenido = await archivo.read()
        ext = guardar_archivo(documento.id, archivo.filename, contenido)
        if ext:
            if documento.archivo_ext and documento.archivo_ext != ext:
                eliminar_archivo(documento.id, documento.archivo_ext)
            documento.archivo_nombre = archivo.filename
            documento.archivo_ext = ext

    db.commit()
    return RedirectResponse(url="/documentos?guardado=1", status_code=302)


@router.post("/{documento_id}/eliminar")
def eliminar_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    if documento:
        eliminar_archivo(documento.id, documento.archivo_ext)
        db.delete(documento)
        db.commit()
    return RedirectResponse(url="/documentos", status_code=302)
