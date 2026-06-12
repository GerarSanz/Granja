from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import date
from database import get_db
from auth import get_current_user
from models.economia import Venta, Gasto, TipoVenta, CategoriaGasto
from models.animal import Animal
from models.usuario import Usuario

router = APIRouter(prefix="/economia", tags=["economia"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def dashboard_economia(
    request: Request,
    anio: int = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    anio = anio or date.today().year

    ventas = db.query(Venta).filter(
        extract("year", Venta.fecha) == anio
    ).order_by(Venta.fecha.desc()).all()

    gastos = db.query(Gasto).filter(
        extract("year", Gasto.fecha) == anio
    ).order_by(Gasto.fecha.desc()).all()

    total_ingresos = sum(v.importe_total for v in ventas)
    total_gastos = sum(g.importe for g in gastos)
    margen = total_ingresos - total_gastos

    # Totales por categoría de gasto
    gastos_por_categoria = {}
    for g in gastos:
        gastos_por_categoria[g.categoria] = gastos_por_categoria.get(g.categoria, 0) + g.importe

    # Ingresos por tipo de venta
    ingresos_por_tipo = {}
    for v in ventas:
        ingresos_por_tipo[v.tipo_venta] = ingresos_por_tipo.get(v.tipo_venta, 0) + v.importe_total

    animales_activos = db.query(Animal).filter(Animal.fecha_baja.is_(None)).all()

    return templates.TemplateResponse("economia/dashboard.html", {
        "request": request,
        "anio": anio,
        "ventas": ventas,
        "gastos": gastos,
        "total_ingresos": total_ingresos,
        "total_gastos": total_gastos,
        "margen": margen,
        "gastos_por_categoria": gastos_por_categoria,
        "ingresos_por_tipo": ingresos_por_tipo,
        "animales_activos": animales_activos,
        "tipos_venta": TipoVenta,
        "categorias_gasto": CategoriaGasto,
        "current_user": current_user,
    })


@router.post("/venta/nueva")
def nueva_venta(
    animal_crotal: str = Form(...),
    fecha: str = Form(...),
    tipo_venta: str = Form(...),
    kg_peso: str = Form(default=""),
    precio_kg: str = Form(default=""),
    importe_total: float = Form(...),
    comprador: str = Form(default=""),
    num_factura: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    from models.animal import EstadoAnimal
    venta = Venta(
        animal_crotal=animal_crotal.upper(),
        fecha=date.fromisoformat(fecha),
        tipo_venta=tipo_venta,
        kg_peso=float(kg_peso) if kg_peso else None,
        precio_kg=float(precio_kg) if precio_kg else None,
        importe_total=importe_total,
        comprador=comprador or None,
        num_factura=num_factura or None,
        observaciones=observaciones or None,
    )
    db.add(venta)

    # Marcar animal como vendido
    animal = db.query(Animal).filter(Animal.crotal == animal_crotal.upper()).first()
    if animal:
        animal.estado = EstadoAnimal.vendido
        animal.fecha_baja = date.fromisoformat(fecha)
        animal.motivo_baja = f"Venta — {comprador or 'sin especificar'}"

    db.commit()
    return RedirectResponse(url="/economia", status_code=302)


@router.post("/gasto/nuevo")
def nuevo_gasto(
    fecha: str = Form(...),
    categoria: str = Form(...),
    concepto: str = Form(...),
    importe: float = Form(...),
    proveedor: str = Form(default=""),
    num_factura: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    gasto = Gasto(
        fecha=date.fromisoformat(fecha),
        categoria=categoria,
        concepto=concepto,
        importe=importe,
        proveedor=proveedor or None,
        num_factura=num_factura or None,
        observaciones=observaciones or None,
    )
    db.add(gasto)
    db.commit()
    return RedirectResponse(url="/economia", status_code=302)
