from datetime import date, datetime

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import extract
from io import BytesIO

from database import get_db
from auth import get_current_user
from models.facturacion import Cliente, Factura, LineaFactura, EstadoFactura
from models.cuaderno import ConfigExplotacion
from models.usuario import Usuario
from services.facturacion_hash import calcular_hash, siguiente_numero, verificar_cadena
from services.factura_pdf import generar_pdf_factura

router = APIRouter(prefix="/facturacion", tags=["facturacion"])
templates = Jinja2Templates(directory="templates")


def _recalcular_totales(factura: Factura):
    base = sum(l.importe for l in factura.lineas)
    iva = sum(l.importe * l.tipo_iva / 100 for l in factura.lineas)
    factura.base_imponible = round(base, 2)
    factura.total_iva = round(iva, 2)
    factura.total = round(base + iva - (factura.total_irpf or 0), 2)


def _guardar_lineas(db: Session, factura: Factura, conceptos, cantidades, precios, tipos_iva):
    db.query(LineaFactura).filter(LineaFactura.factura_id == factura.id).delete()
    orden = 0
    for concepto, cantidad, precio, tipo_iva in zip(conceptos, cantidades, precios, tipos_iva):
        if not concepto or not concepto.strip():
            continue
        db.add(LineaFactura(
            factura_id=factura.id,
            concepto=concepto.strip(),
            cantidad=float(cantidad) if cantidad else 1,
            precio_unitario=float(precio) if precio else 0,
            tipo_iva=float(tipo_iva) if tipo_iva else 0,
            orden=orden,
        ))
        orden += 1
    db.flush()
    db.refresh(factura)


@router.get("", response_class=HTMLResponse)
def lista_facturacion(
    request: Request,
    anio: int = None,
    estado: str = None,
    cliente_id: str = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()
    anio_filtro = anio or hoy.year

    clientes = db.query(Cliente).order_by(Cliente.nombre).all()

    q = db.query(Factura)
    if anio:
        q = q.filter(extract("year", Factura.fecha_emision) == anio)
    if estado:
        q = q.filter(Factura.estado == estado)
    if cliente_id:
        q = q.filter(Factura.cliente_id == int(cliente_id))
    facturas = q.order_by(Factura.fecha_emision.desc(), Factura.id.desc()).all()

    anios_disponibles = sorted(
        {int(r[0]) for r in db.query(extract("year", Factura.fecha_emision)).distinct().all() if r[0]},
        reverse=True,
    )
    if hoy.year not in anios_disponibles:
        anios_disponibles.insert(0, hoy.year)

    facturado_anio = sum(
        f.total for f in db.query(Factura).filter(
            extract("year", Factura.fecha_emision) == anio_filtro,
            Factura.estado.in_([EstadoFactura.emitida, EstadoFactura.pagada]),
        ).all()
    )
    pendiente_cobro = sum(
        f.total for f in db.query(Factura).filter(Factura.estado == EstadoFactura.emitida).all()
    )
    borradores = db.query(Factura).filter(Factura.estado == EstadoFactura.borrador).count()

    return templates.TemplateResponse("facturacion/lista.html", {
        "request": request,
        "clientes": clientes,
        "facturas": facturas,
        "anios_disponibles": anios_disponibles,
        "anio_filtro": anio_filtro,
        "filtro_anio": anio,
        "filtro_estado": estado,
        "filtro_cliente": cliente_id,
        "facturado_anio": facturado_anio,
        "pendiente_cobro": pendiente_cobro,
        "borradores": borradores,
        "hoy": hoy,
        "current_user": current_user,
    })


@router.post("/cliente/nuevo")
def nuevo_cliente(
    nombre: str = Form(...),
    nif: str = Form(default=""),
    direccion: str = Form(default=""),
    cp: str = Form(default=""),
    localidad: str = Form(default=""),
    provincia: str = Form(default=""),
    email: str = Form(default=""),
    telefono: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    cliente = Cliente(
        nombre=nombre, nif=nif or None, direccion=direccion or None, cp=cp or None,
        localidad=localidad or None, provincia=provincia or None, email=email or None,
        telefono=telefono or None, observaciones=observaciones or None,
    )
    db.add(cliente)
    db.commit()
    return RedirectResponse(url="/facturacion?guardado=1", status_code=302)


@router.post("/cliente/{cliente_id}/editar")
def editar_cliente(
    cliente_id: int,
    nombre: str = Form(...),
    nif: str = Form(default=""),
    direccion: str = Form(default=""),
    cp: str = Form(default=""),
    localidad: str = Form(default=""),
    provincia: str = Form(default=""),
    email: str = Form(default=""),
    telefono: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404)
    cliente.nombre = nombre
    cliente.nif = nif or None
    cliente.direccion = direccion or None
    cliente.cp = cp or None
    cliente.localidad = localidad or None
    cliente.provincia = provincia or None
    cliente.email = email or None
    cliente.telefono = telefono or None
    cliente.observaciones = observaciones or None
    db.commit()
    return RedirectResponse(url="/facturacion?guardado=1", status_code=302)


@router.post("/cliente/{cliente_id}/eliminar")
def eliminar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    tiene_facturas = db.query(Factura).filter(Factura.cliente_id == cliente_id).first()
    if tiene_facturas:
        raise HTTPException(status_code=400, detail="No se puede eliminar un cliente con facturas registradas")
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if cliente:
        db.delete(cliente)
        db.commit()
    return RedirectResponse(url="/facturacion", status_code=302)


@router.get("/nueva", response_class=HTMLResponse)
def nueva_factura_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    clientes = db.query(Cliente).order_by(Cliente.nombre).all()
    return templates.TemplateResponse("facturacion/form.html", {
        "request": request,
        "clientes": clientes,
        "factura": None,
        "hoy": date.today(),
        "current_user": current_user,
    })


@router.post("/nueva")
async def nueva_factura(
    request: Request,
    cliente_id: str = Form(...),
    fecha_emision: str = Form(...),
    forma_pago: str = Form(default=""),
    total_irpf: str = Form(default="0"),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    form = await request.form()
    conceptos = form.getlist("concepto")
    cantidades = form.getlist("cantidad")
    precios = form.getlist("precio_unitario")
    tipos_iva = form.getlist("tipo_iva")

    fecha = date.fromisoformat(fecha_emision)
    factura = Factura(
        anio=fecha.year, fecha_emision=fecha, cliente_id=int(cliente_id),
        estado=EstadoFactura.borrador, forma_pago=forma_pago or None,
        total_irpf=float(total_irpf) if total_irpf else 0,
        observaciones=observaciones or None,
    )
    db.add(factura)
    db.flush()

    _guardar_lineas(db, factura, conceptos, cantidades, precios, tipos_iva)
    _recalcular_totales(factura)
    db.commit()

    return RedirectResponse(url=f"/facturacion/{factura.id}", status_code=302)


@router.get("/verificar", response_class=HTMLResponse)
def verificar_facturas(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    emitidas = db.query(Factura).filter(
        Factura.estado.in_([EstadoFactura.emitida, EstadoFactura.pagada, EstadoFactura.anulada])
    ).order_by(Factura.fecha_emision, Factura.id).all()
    resultado = verificar_cadena(emitidas)
    todas_integras = all(r["integra"] for r in resultado)
    return templates.TemplateResponse("facturacion/verificar.html", {
        "request": request,
        "resultado": resultado,
        "todas_integras": todas_integras,
        "current_user": current_user,
    })


@router.get("/{factura_id}", response_class=HTMLResponse)
def detalle_factura(
    factura_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    factura = db.query(Factura).filter(Factura.id == factura_id).first()
    if not factura:
        raise HTTPException(status_code=404)
    if factura.estado == EstadoFactura.borrador:
        clientes = db.query(Cliente).order_by(Cliente.nombre).all()
        return templates.TemplateResponse("facturacion/form.html", {
            "request": request,
            "clientes": clientes,
            "factura": factura,
            "hoy": date.today(),
            "current_user": current_user,
        })
    return templates.TemplateResponse("facturacion/detalle.html", {
        "request": request,
        "factura": factura,
        "current_user": current_user,
    })


@router.post("/{factura_id}/editar")
async def editar_factura(
    factura_id: int,
    request: Request,
    cliente_id: str = Form(...),
    fecha_emision: str = Form(...),
    forma_pago: str = Form(default=""),
    total_irpf: str = Form(default="0"),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    factura = db.query(Factura).filter(Factura.id == factura_id).first()
    if not factura:
        raise HTTPException(status_code=404)
    if factura.estado != EstadoFactura.borrador:
        raise HTTPException(status_code=400, detail="Solo se pueden editar facturas en borrador")

    form = await request.form()
    conceptos = form.getlist("concepto")
    cantidades = form.getlist("cantidad")
    precios = form.getlist("precio_unitario")
    tipos_iva = form.getlist("tipo_iva")

    fecha = date.fromisoformat(fecha_emision)
    factura.anio = fecha.year
    factura.fecha_emision = fecha
    factura.cliente_id = int(cliente_id)
    factura.forma_pago = forma_pago or None
    factura.total_irpf = float(total_irpf) if total_irpf else 0
    factura.observaciones = observaciones or None

    _guardar_lineas(db, factura, conceptos, cantidades, precios, tipos_iva)
    _recalcular_totales(factura)
    db.commit()

    return RedirectResponse(url=f"/facturacion/{factura.id}", status_code=302)


@router.post("/{factura_id}/eliminar")
def eliminar_factura(
    factura_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    factura = db.query(Factura).filter(Factura.id == factura_id).first()
    if not factura:
        raise HTTPException(status_code=404)
    if factura.estado != EstadoFactura.borrador:
        raise HTTPException(status_code=400, detail="Solo se pueden eliminar facturas en borrador — una factura emitida se anula, no se borra")
    db.delete(factura)
    db.commit()
    return RedirectResponse(url="/facturacion", status_code=302)


@router.post("/{factura_id}/emitir")
def emitir_factura(
    factura_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    factura = db.query(Factura).filter(Factura.id == factura_id).first()
    if not factura:
        raise HTTPException(status_code=404)
    if factura.estado != EstadoFactura.borrador:
        raise HTTPException(status_code=400, detail="La factura ya ha sido emitida")
    if not factura.lineas:
        raise HTTPException(status_code=400, detail="No se puede emitir una factura sin líneas")

    ultima_emitida = db.query(Factura).filter(
        Factura.estado.in_([EstadoFactura.emitida, EstadoFactura.pagada, EstadoFactura.anulada])
    ).order_by(Factura.emitida_en.desc()).first()

    factura.numero = siguiente_numero(db, factura.anio)
    factura.estado = EstadoFactura.emitida
    factura.emitida_en = datetime.utcnow()
    factura.hash_anterior = ultima_emitida.hash_actual if ultima_emitida else None
    factura.hash_actual = calcular_hash(factura, factura.hash_anterior)
    db.commit()

    return RedirectResponse(url=f"/facturacion/{factura.id}", status_code=302)


@router.post("/{factura_id}/marcar-pagada")
def marcar_pagada(
    factura_id: int,
    fecha_pago: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    factura = db.query(Factura).filter(Factura.id == factura_id).first()
    if not factura:
        raise HTTPException(status_code=404)
    if factura.estado != EstadoFactura.emitida:
        raise HTTPException(status_code=400, detail="Solo se puede marcar como pagada una factura emitida")
    factura.estado = EstadoFactura.pagada
    factura.fecha_pago = date.fromisoformat(fecha_pago) if fecha_pago else date.today()
    db.commit()
    return RedirectResponse(url=f"/facturacion/{factura.id}", status_code=302)


@router.post("/{factura_id}/anular")
def anular_factura(
    factura_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    factura = db.query(Factura).filter(Factura.id == factura_id).first()
    if not factura:
        raise HTTPException(status_code=404)
    if factura.estado not in (EstadoFactura.emitida, EstadoFactura.pagada):
        raise HTTPException(status_code=400, detail="Solo se puede anular una factura emitida o pagada")
    factura.estado = EstadoFactura.anulada
    db.commit()
    return RedirectResponse(url=f"/facturacion/{factura.id}", status_code=302)


@router.get("/{factura_id}/pdf")
def pdf_factura(
    factura_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    factura = db.query(Factura).filter(Factura.id == factura_id).first()
    if not factura:
        raise HTTPException(status_code=404)
    config = db.query(ConfigExplotacion).first() or ConfigExplotacion()
    pdf_bytes = generar_pdf_factura(factura, factura.cliente, config)
    nombre = factura.numero.replace("/", "-") if factura.numero else f"borrador-{factura.id}"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=factura_{nombre}.pdf"},
    )
