import io
import qrcode
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date
from database import get_db
from config import get_settings
from auth import get_current_user
from models.queseria import LoteQueso, MovimientoQueso, TipoQueso, TipoMovimientoQueso, EtapaQueso, TurnoOrdeno, Estanteria, CuajoProducto
from models.animal import Animal, SexoAnimal
from models.sanidad import Tratamiento
from models.usuario import Usuario
from services.queso_calculator import resumen_lotes, resumen_lote, peso_disponible, piezas_disponibles
from services.animal_foto import foto_url

router = APIRouter(prefix="/queseria", tags=["queseria"])
templates = Jinja2Templates(directory="templates")

ETAPA_LABEL = {
    "cuajado": "Cuajando",
    "moldeado": "En molde (desuerando)",
    "curacion": "Curando",
    "listo": "Listo para vender",
}

TIPO_LABEL = {
    "fresco": "Fresco",
    "tierno": "Tierno",
    "semicurado": "Semicurado",
    "curado": "Curado",
    "afuega_el_pitu": "Afuega'l Pitu",
    "otro": "Otro",
}

TURNO_LABEL = {
    "manana": "Mañana",
    "tarde": "Tarde",
}


def _siguiente_codigo(db: Session, fecha: date) -> str:
    prefix = f"Q{fecha.year}-"
    ultimo = db.query(LoteQueso).filter(LoteQueso.codigo.like(f"{prefix}%")).order_by(LoteQueso.codigo.desc()).first()
    n = 1
    if ultimo:
        try:
            n = int(ultimo.codigo.replace(prefix, "")) + 1
        except ValueError:
            n = 1
    return f"{prefix}{n:03d}"


@router.post("/estanteria/nueva")
def nueva_estanteria(
    nombre: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not db.query(Estanteria).filter(Estanteria.nombre == nombre.strip()).first():
        db.add(Estanteria(nombre=nombre.strip()))
        db.commit()
    return RedirectResponse(url="/queseria", status_code=302)


@router.post("/estanteria/{estanteria_id}/eliminar")
def eliminar_estanteria(
    estanteria_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    e = db.query(Estanteria).filter(Estanteria.id == estanteria_id).first()
    if e:
        db.delete(e)
        db.commit()
    return RedirectResponse(url="/queseria", status_code=302)


@router.post("/cuajo-producto/nuevo")
def nuevo_cuajo_producto(
    marca: str = Form(...),
    registro_sanitario: str = Form(default=""),
    lote_actual: str = Form(default=""),
    caducidad_actual: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not db.query(CuajoProducto).filter(CuajoProducto.marca == marca.strip()).first():
        db.add(CuajoProducto(
            marca=marca.strip(),
            registro_sanitario=registro_sanitario.strip() or None,
            lote_actual=lote_actual.strip() or None,
            caducidad_actual=date.fromisoformat(caducidad_actual) if caducidad_actual else None,
        ))
        db.commit()
    return RedirectResponse(url="/queseria", status_code=302)


@router.post("/cuajo-producto/{producto_id}/eliminar")
def eliminar_cuajo_producto(
    producto_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    p = db.query(CuajoProducto).filter(CuajoProducto.id == producto_id).first()
    if p:
        db.delete(p)
        db.commit()
    return RedirectResponse(url="/queseria", status_code=302)


@router.get("", response_class=HTMLResponse)
def dashboard_queseria(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()
    resumenes = resumen_lotes(db)
    en_curacion = [r for r in resumenes if r["en_curacion"] and not r["agotado"]]
    listos = [r for r in resumenes if not r["en_curacion"] and not r["agotado"]]
    agotados = [r for r in resumenes if r["agotado"]]

    vacas = db.query(Animal).filter(
        Animal.sexo == SexoAnimal.hembra,
        Animal.fecha_baja.is_(None),
    ).order_by(Animal.crotal).all()

    crotales_en_espera = {
        t.animal_crotal for t in db.query(Tratamiento).filter(Tratamiento.fecha_fin_espera >= hoy).all()
    }

    total_kg_stock = sum(r["peso_disponible_kg"] for r in resumenes)
    total_kg_vendido_anio = sum(
        m.peso_kg for l in db.query(LoteQueso).all() for m in l.movimientos
        if m.tipo == TipoMovimientoQueso.venta and m.fecha.year == hoy.year
    )
    total_ingresos_anio = sum(
        m.precio_total or 0 for l in db.query(LoteQueso).all() for m in l.movimientos
        if m.tipo == TipoMovimientoQueso.venta and m.fecha.year == hoy.year
    )

    estanterias = db.query(Estanteria).order_by(Estanteria.nombre).all()
    cuajo_productos = db.query(CuajoProducto).order_by(CuajoProducto.marca).all()

    return templates.TemplateResponse("queseria/dashboard.html", {
        "request": request,
        "en_curacion": en_curacion,
        "listos": listos,
        "agotados": agotados,
        "vacas": vacas,
        "crotales_en_espera": crotales_en_espera,
        "tipos_queso": TipoQueso,
        "estanterias": estanterias,
        "cuajo_productos": cuajo_productos,
        "etapa_label": ETAPA_LABEL,
        "turno_label": TURNO_LABEL,
        "total_kg_stock": total_kg_stock,
        "total_kg_vendido_anio": total_kg_vendido_anio,
        "total_ingresos_anio": total_ingresos_anio,
        "hoy": hoy,
        "current_user": current_user,
    })


@router.get("/lote/{lote_id}", response_class=HTMLResponse)
def detalle_lote(
    lote_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lote = db.query(LoteQueso).filter(LoteQueso.id == lote_id).first()
    if not lote:
        raise HTTPException(status_code=404)
    hoy = date.today()
    resumen = resumen_lote(db, lote)
    movimientos = db.query(MovimientoQueso).filter(
        MovimientoQueso.lote_id == lote_id
    ).order_by(MovimientoQueso.fecha.desc()).all()
    crotales_lote = [c.strip() for c in (lote.animales_crotales or "").split(",") if c.strip()]
    animales_origen = db.query(Animal).filter(Animal.crotal.in_(crotales_lote)).all() if crotales_lote else []

    vacas = db.query(Animal).filter(
        Animal.sexo == SexoAnimal.hembra,
        Animal.fecha_baja.is_(None),
    ).order_by(Animal.crotal).all()
    crotales_en_espera = {
        t.animal_crotal for t in db.query(Tratamiento).filter(Tratamiento.fecha_fin_espera >= hoy).all()
    }
    estanterias = db.query(Estanteria).order_by(Estanteria.nombre).all()
    cuajo_productos = db.query(CuajoProducto).order_by(CuajoProducto.marca).all()

    return templates.TemplateResponse("queseria/lote.html", {
        "request": request,
        "lote": lote,
        "resumen": resumen,
        "movimientos": movimientos,
        "animales_origen": animales_origen,
        "crotales_lote": crotales_lote,
        "vacas": vacas,
        "crotales_en_espera": crotales_en_espera,
        "tipos_queso": TipoQueso,
        "estanterias": estanterias,
        "cuajo_productos": cuajo_productos,
        "foto_url": foto_url,
        "etapa_label": ETAPA_LABEL,
        "turno_label": TURNO_LABEL,
        "hoy": hoy,
        "current_user": current_user,
    })


@router.post("/lote/{lote_id}/editar")
def editar_lote(
    lote_id: int,
    fecha_elaboracion: str = Form(...),
    turno_ordeno: str = Form(...),
    litros_leche: str = Form(default=""),
    animales_crotales: list[str] = Form(default=[]),
    tipo_queso: str = Form(...),
    es_ecologico: str = Form(default=""),
    observaciones: str = Form(default=""),
    estanteria: str = Form(default=""),
    fila: str = Form(default=""),
    columna: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lote = db.query(LoteQueso).filter(LoteQueso.id == lote_id).first()
    if not lote:
        raise HTTPException(status_code=404)
    lote.fecha_elaboracion = date.fromisoformat(fecha_elaboracion)
    lote.turno_ordeno = turno_ordeno
    lote.litros_leche = float(litros_leche) if litros_leche else None
    lote.animales_crotales = ",".join(c.upper() for c in animales_crotales) or None
    lote.tipo_queso = tipo_queso
    lote.es_ecologico = bool(es_ecologico)
    lote.observaciones = observaciones or None
    lote.estanteria = estanteria.strip() or None
    lote.fila = int(fila) if fila else None
    lote.columna = int(columna) if columna else None
    db.commit()
    return RedirectResponse(url=f"/queseria/lote/{lote_id}?guardado=1", status_code=302)


@router.get("/lote/{lote_id}/qr.png")
def qr_lote(
    lote_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lote = db.query(LoteQueso).filter(LoteQueso.id == lote_id).first()
    if not lote:
        raise HTTPException(status_code=404)
    settings = get_settings()
    url = f"{settings.BASE_URL}/trazabilidad/{lote.codigo}"
    img = qrcode.make(url, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@router.get("/lote/{lote_id}/etiqueta", response_class=HTMLResponse)
def etiqueta_lote(
    lote_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lote = db.query(LoteQueso).filter(LoteQueso.id == lote_id).first()
    if not lote:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("queseria/etiqueta.html", {
        "request": request,
        "lote": lote,
        "tipo_label": TIPO_LABEL.get(lote.tipo_queso, lote.tipo_queso),
        "current_user": current_user,
    })


@router.post("/lote/nuevo")
def crear_lote(
    fecha_elaboracion: str = Form(...),
    turno_ordeno: str = Form(...),
    litros_leche: str = Form(default=""),
    animales_crotales: list[str] = Form(default=[]),
    tipo_queso: str = Form(default=TipoQueso.curado),
    dias_curacion_objetivo: str = Form(default=""),
    es_ecologico: str = Form(default=""),
    observaciones: str = Form(default=""),
    cuajo_producto_id: int = Form(...),
    cuajo_lote: str = Form(...),
    cuajo_caducidad: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    producto = db.query(CuajoProducto).filter(CuajoProducto.id == cuajo_producto_id).first()
    if not producto:
        raise HTTPException(status_code=400, detail="Producto de cuajo no válido")

    fecha = date.fromisoformat(fecha_elaboracion)
    cuajo_lote = cuajo_lote.strip()
    cuajo_caducidad_fecha = date.fromisoformat(cuajo_caducidad)
    lote = LoteQueso(
        codigo=_siguiente_codigo(db, fecha),
        fecha_elaboracion=fecha,
        turno_ordeno=turno_ordeno,
        litros_leche=float(litros_leche) if litros_leche else None,
        animales_crotales=",".join(c.upper() for c in animales_crotales) or None,
        tipo_queso=tipo_queso,
        etapa=EtapaQueso.cuajado,
        dias_curacion_objetivo=int(dias_curacion_objetivo) if dias_curacion_objetivo else None,
        es_ecologico=bool(es_ecologico),
        observaciones=observaciones or None,
        cuajo_marca=producto.marca,
        cuajo_registro_sanitario=producto.registro_sanitario,
        cuajo_lote=cuajo_lote,
        cuajo_caducidad=cuajo_caducidad_fecha,
    )
    db.add(lote)
    # Recuerda el frasco/lote en uso, para que el próximo lote con este producto venga precargado
    producto.lote_actual = cuajo_lote
    producto.caducidad_actual = cuajo_caducidad_fecha
    db.commit()
    return RedirectResponse(url="/queseria?guardado=1", status_code=302)


@router.post("/lote/{lote_id}/cuajo")
def editar_cuajo(
    lote_id: int,
    cuajo_producto_id: str = Form(default=""),
    cuajo_lote: str = Form(default=""),
    cuajo_caducidad: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lote = db.query(LoteQueso).filter(LoteQueso.id == lote_id).first()
    if not lote:
        raise HTTPException(status_code=404)
    producto = db.query(CuajoProducto).filter(CuajoProducto.id == int(cuajo_producto_id)).first() if cuajo_producto_id else None
    lote.cuajo_marca = producto.marca if producto else None
    lote.cuajo_registro_sanitario = producto.registro_sanitario if producto else None
    lote.cuajo_lote = cuajo_lote.strip() or None
    lote.cuajo_caducidad = date.fromisoformat(cuajo_caducidad) if cuajo_caducidad else None
    if producto:
        producto.lote_actual = lote.cuajo_lote
        producto.caducidad_actual = lote.cuajo_caducidad
    db.commit()
    return RedirectResponse(url=f"/queseria/lote/{lote_id}?guardado=1", status_code=302)


@router.post("/lote/{lote_id}/moldeado")
def registrar_moldeado(
    lote_id: int,
    num_piezas_inicial: int = Form(...),
    fecha_moldeado: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lote = db.query(LoteQueso).filter(LoteQueso.id == lote_id).first()
    if not lote:
        raise HTTPException(status_code=404)
    lote.num_piezas_inicial = num_piezas_inicial
    lote.fecha_moldeado = date.fromisoformat(fecha_moldeado) if fecha_moldeado else date.today()
    lote.etapa = EtapaQueso.moldeado
    db.commit()
    return RedirectResponse(url=f"/queseria/lote/{lote_id}?guardado=1", status_code=302)


@router.post("/lote/{lote_id}/iniciar-curacion")
def iniciar_curacion(
    lote_id: int,
    fecha_inicio_curacion: str = Form(default=""),
    dias_curacion_objetivo: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lote = db.query(LoteQueso).filter(LoteQueso.id == lote_id).first()
    if not lote:
        raise HTTPException(status_code=404)
    lote.fecha_inicio_curacion = date.fromisoformat(fecha_inicio_curacion) if fecha_inicio_curacion else date.today()
    if dias_curacion_objetivo:
        lote.dias_curacion_objetivo = int(dias_curacion_objetivo)
    lote.etapa = EtapaQueso.curacion
    db.commit()
    return RedirectResponse(url=f"/queseria/lote/{lote_id}?guardado=1", status_code=302)


@router.post("/lote/{lote_id}/listo")
def marcar_listo(
    lote_id: int,
    peso_inicial_kg: float = Form(...),
    fecha_listo: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lote = db.query(LoteQueso).filter(LoteQueso.id == lote_id).first()
    if not lote:
        raise HTTPException(status_code=404)
    lote.peso_inicial_kg = peso_inicial_kg
    lote.fecha_listo = date.fromisoformat(fecha_listo) if fecha_listo else date.today()
    lote.etapa = EtapaQueso.listo
    db.commit()
    return RedirectResponse(url=f"/queseria/lote/{lote_id}?guardado=1", status_code=302)


@router.post("/lote/{lote_id}/movimiento/nuevo")
def nuevo_movimiento(
    lote_id: int,
    tipo: str = Form(...),
    fecha: str = Form(...),
    peso_kg: float = Form(...),
    num_piezas: str = Form(default=""),
    cliente: str = Form(default=""),
    precio_total: str = Form(default=""),
    num_factura: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lote = db.query(LoteQueso).filter(LoteQueso.id == lote_id).first()
    if not lote:
        raise HTTPException(status_code=404)
    # Solo "ajuste" admite valores negativos, para corregir stock al alza (p.ej. un recuento erróneo)
    if tipo != TipoMovimientoQueso.ajuste and peso_kg <= 0:
        raise HTTPException(status_code=400, detail="El peso debe ser mayor que 0")
    disponible = peso_disponible(db, lote_id)
    if peso_kg > disponible + 0.001:
        raise HTTPException(status_code=400, detail=f"Solo quedan {disponible:.2f} kg disponibles en este lote")
    piezas = int(num_piezas) if num_piezas else None
    if piezas is not None:
        if tipo != TipoMovimientoQueso.ajuste and piezas <= 0:
            raise HTTPException(status_code=400, detail="Las piezas deben ser mayor que 0")
        piezas_disp = piezas_disponibles(db, lote_id)
        if piezas > piezas_disp:
            raise HTTPException(status_code=400, detail=f"Solo quedan {piezas_disp} piezas disponibles en este lote")
    mov = MovimientoQueso(
        lote_id=lote_id,
        fecha=date.fromisoformat(fecha),
        tipo=tipo,
        peso_kg=peso_kg,
        num_piezas=piezas,
        cliente=cliente.strip() or None,
        precio_total=float(precio_total) if precio_total else None,
        num_factura=num_factura or None,
        observaciones=observaciones or None,
    )
    db.add(mov)
    db.commit()
    return RedirectResponse(url=f"/queseria/lote/{lote_id}?guardado=1", status_code=302)


@router.post("/movimiento/{mov_id}/eliminar")
def eliminar_movimiento(
    mov_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    mov = db.query(MovimientoQueso).filter(MovimientoQueso.id == mov_id).first()
    if not mov:
        raise HTTPException(status_code=404)
    lote_id = mov.lote_id
    db.delete(mov)
    db.commit()
    return RedirectResponse(url=f"/queseria/lote/{lote_id}", status_code=302)


@router.post("/lote/{lote_id}/eliminar")
def eliminar_lote(
    lote_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lote = db.query(LoteQueso).filter(LoteQueso.id == lote_id).first()
    if lote:
        db.delete(lote)
        db.commit()
    return RedirectResponse(url="/queseria", status_code=302)
