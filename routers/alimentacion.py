from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date
from database import get_db
from auth import get_current_user
from models.alimentacion import (
    Alimento, StockMovimiento, CompraAlimento, RacionTipo,
    TipoAlimento, TipoMovimientoStock, EstadoProductivo
)
from models.animal import Animal
from models.maestros import Especie
from models.usuario import Usuario
from services.stock_calculator import resumen_stock, consumo_total_diario, stock_actual
from services.especies import estados_labels_racion

router = APIRouter(prefix="/alimentacion", tags=["alimentacion"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def dashboard_alimentacion(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    stocks = resumen_stock(db)
    consumo_diario = consumo_total_diario(db)
    alimentos = db.query(Alimento).filter(Alimento.activo == True).all()
    raciones = db.query(RacionTipo).all()

    especies_presentes = (
        db.query(Especie)
        .join(Animal, Animal.especie_id == Especie.id)
        .filter(Animal.fecha_baja.is_(None))
        .distinct()
        .all()
    )
    especies_presentes = sorted(especies_presentes, key=lambda e: (e.nombre != "Bovino", e.nombre))
    estados_labels_por_especie = {e.nombre: estados_labels_racion(e.nombre) for e in especies_presentes}

    return templates.TemplateResponse("alimentacion/dashboard.html", {
        "request": request,
        "stocks": stocks,
        "consumo_diario": consumo_diario,
        "alimentos": alimentos,
        "raciones": raciones,
        "especies_presentes": especies_presentes,
        "estados_labels_por_especie": estados_labels_por_especie,
        "estados_productivos": EstadoProductivo,
        "current_user": current_user,
    })


@router.post("/stock/entrada")
def registrar_entrada_stock(
    alimento_id: int = Form(...),
    cantidad_kg: float = Form(...),
    fecha: str = Form(...),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    mov = StockMovimiento(
        alimento_id=alimento_id,
        fecha=date.fromisoformat(fecha),
        tipo_movimiento=TipoMovimientoStock.entrada,
        cantidad_kg=cantidad_kg,
        observaciones=observaciones or None,
    )
    db.add(mov)
    db.commit()
    return RedirectResponse(url="/alimentacion?guardado=1", status_code=302)


@router.post("/stock/consumo")
def registrar_consumo(
    alimento_id: int = Form(...),
    cantidad_kg: float = Form(...),
    fecha: str = Form(...),
    lote_id: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    disponible = stock_actual(db, alimento_id)
    if cantidad_kg > disponible + 0.001:
        raise HTTPException(status_code=400, detail=f"Solo quedan {disponible:.0f} kg disponibles de este alimento")
    mov = StockMovimiento(
        alimento_id=alimento_id,
        fecha=date.fromisoformat(fecha),
        tipo_movimiento=TipoMovimientoStock.consumo,
        cantidad_kg=cantidad_kg,
        lote_id=int(lote_id) if lote_id else None,
        observaciones=observaciones or None,
    )
    db.add(mov)
    db.commit()
    return RedirectResponse(url="/alimentacion?guardado=1", status_code=302)


@router.post("/compra")
def registrar_compra(
    alimento_id: int = Form(...),
    proveedor: str = Form(...),
    fecha: str = Form(...),
    cantidad_kg: float = Form(...),
    precio_total: float = Form(...),
    num_factura: str = Form(default=""),
    certificado_eco: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    compra = CompraAlimento(
        alimento_id=alimento_id,
        proveedor=proveedor,
        fecha=date.fromisoformat(fecha),
        cantidad_kg=cantidad_kg,
        precio_total=precio_total,
        num_factura=num_factura or None,
        certificado_eco=certificado_eco or None,
    )
    db.add(compra)

    # Generar automáticamente movimiento de entrada en stock
    mov = StockMovimiento(
        alimento_id=alimento_id,
        fecha=date.fromisoformat(fecha),
        tipo_movimiento=TipoMovimientoStock.entrada,
        cantidad_kg=cantidad_kg,
        observaciones=f"Compra a {proveedor} — factura {num_factura}",
    )
    db.add(mov)
    db.commit()
    return RedirectResponse(url="/alimentacion?guardado=1", status_code=302)


@router.post("/alimento/nuevo")
def crear_alimento(
    nombre: str = Form(...),
    tipo: str = Form(...),
    es_ecologico: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    alimento = Alimento(
        nombre=nombre,
        tipo=tipo,
        es_ecologico=bool(es_ecologico),
    )
    db.add(alimento)
    db.commit()
    return RedirectResponse(url="/alimentacion?guardado=1", status_code=302)


@router.post("/racion")
def guardar_racion(
    estado_productivo: str = Form(...),
    alimento_id: int = Form(...),
    especie_id: int = Form(...),
    kg_por_animal_dia: float = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    racion = db.query(RacionTipo).filter(
        RacionTipo.estado_productivo == estado_productivo,
        RacionTipo.alimento_id == alimento_id,
        RacionTipo.especie_id == especie_id,
    ).first()
    if racion:
        racion.kg_por_animal_dia = kg_por_animal_dia
    else:
        racion = RacionTipo(
            estado_productivo=estado_productivo,
            alimento_id=alimento_id,
            especie_id=especie_id,
            kg_por_animal_dia=kg_por_animal_dia,
        )
        db.add(racion)
    db.commit()
    return RedirectResponse(url="/alimentacion?guardado=1", status_code=302)
