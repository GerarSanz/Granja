from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
from models.facturacion import Cliente, EstadoFactura
from models.crm import InteraccionCliente, TipoCliente, TipoInteraccion
from models.usuario import Usuario

router = APIRouter(prefix="/crm", tags=["crm"])
templates = Jinja2Templates(directory="templates")

FACTURADO_ESTADOS = (EstadoFactura.emitida, EstadoFactura.pagada)


@router.get("", response_class=HTMLResponse)
def lista_crm(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()
    clientes = db.query(Cliente).order_by(Cliente.nombre).all()

    filas = []
    for c in clientes:
        facturado = sum(f.total for f in c.facturas if f.estado in FACTURADO_ESTADOS)
        ultima_interaccion = max((i.fecha for i in c.interacciones), default=None)
        filas.append({
            "cliente": c,
            "facturado_total": facturado,
            "n_facturas": len(c.facturas),
            "ultima_interaccion": ultima_interaccion,
        })

    contactos_vencidos = db.query(Cliente).filter(
        Cliente.proximo_contacto_fecha.isnot(None), Cliente.proximo_contacto_fecha < hoy,
    ).count()
    contactos_proximos = db.query(Cliente).filter(
        Cliente.proximo_contacto_fecha.isnot(None),
        Cliente.proximo_contacto_fecha >= hoy,
        Cliente.proximo_contacto_fecha <= hoy + timedelta(days=7),
    ).count()

    return templates.TemplateResponse("crm/lista.html", {
        "request": request,
        "filas": filas,
        "total_clientes": len(clientes),
        "contactos_vencidos": contactos_vencidos,
        "contactos_proximos": contactos_proximos,
        "hoy": hoy,
        "current_user": current_user,
    })


@router.get("/clientes/{cliente_id}", response_class=HTMLResponse)
def detalle_cliente(
    cliente_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404)

    facturas = sorted(cliente.facturas, key=lambda f: f.fecha_emision, reverse=True)
    facturado_total = sum(f.total for f in facturas if f.estado in FACTURADO_ESTADOS)

    return templates.TemplateResponse("crm/detalle.html", {
        "request": request,
        "cliente": cliente,
        "facturas": facturas,
        "facturado_total": facturado_total,
        "tipos_cliente": TipoCliente,
        "tipos_interaccion": TipoInteraccion,
        "hoy": date.today(),
        "current_user": current_user,
    })


@router.post("/clientes/{cliente_id}/interaccion")
def nueva_interaccion(
    cliente_id: int,
    fecha: str = Form(...),
    tipo: str = Form(...),
    texto: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404)
    db.add(InteraccionCliente(
        cliente_id=cliente_id,
        fecha=date.fromisoformat(fecha),
        tipo=tipo,
        texto=texto.strip(),
    ))
    db.commit()
    return RedirectResponse(url=f"/crm/clientes/{cliente_id}?guardado=1", status_code=302)


@router.post("/interaccion/{interaccion_id}/eliminar")
def eliminar_interaccion(
    interaccion_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    interaccion = db.query(InteraccionCliente).filter(InteraccionCliente.id == interaccion_id).first()
    cliente_id = interaccion.cliente_id if interaccion else None
    if interaccion:
        db.delete(interaccion)
        db.commit()
    return RedirectResponse(url=f"/crm/clientes/{cliente_id}" if cliente_id else "/crm", status_code=302)


@router.post("/clientes/{cliente_id}/seguimiento")
def actualizar_seguimiento(
    cliente_id: int,
    tipo_cliente: str = Form(default=""),
    proximo_contacto_fecha: str = Form(default=""),
    proximo_contacto_motivo: str = Form(default=""),
    activo: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404)
    cliente.tipo_cliente = tipo_cliente or None
    cliente.proximo_contacto_fecha = date.fromisoformat(proximo_contacto_fecha) if proximo_contacto_fecha else None
    cliente.proximo_contacto_motivo = proximo_contacto_motivo.strip() or None
    cliente.activo = bool(activo)
    db.commit()
    return RedirectResponse(url=f"/crm/clientes/{cliente_id}?guardado=1", status_code=302)
