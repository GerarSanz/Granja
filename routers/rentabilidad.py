from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import extract
from datetime import date

from database import get_db
from auth import get_current_user
from config import get_settings
from models.economia import Venta, Gasto
from models.animal import Animal
from models.usuario import Usuario

router = APIRouter(prefix="/rentabilidad", tags=["rentabilidad"])
templates = Jinja2Templates(directory="templates")


def _ingresos_ventas(db: Session, anio: int) -> float:
    return sum(
        v.importe_total for v in db.query(Venta).filter(extract("year", Venta.fecha) == anio).all()
    )


def _gastos(db: Session, anio: int) -> list[Gasto]:
    return db.query(Gasto).filter(extract("year", Gasto.fecha) == anio).all()


def _ingresos_queseria(db: Session, anio: int) -> float:
    if "queseria" not in get_settings().MODULOS:
        return 0.0
    from models.queseria import MovimientoQueso, TipoMovimientoQueso
    movimientos = db.query(MovimientoQueso).filter(
        extract("year", MovimientoQueso.fecha) == anio,
        MovimientoQueso.tipo == TipoMovimientoQueso.venta,
    ).all()
    return sum(m.precio_total or 0 for m in movimientos)


def _ingresos_facturacion(db: Session, anio: int) -> float:
    if "facturacion" not in get_settings().MODULOS:
        return 0.0
    from models.facturacion import Factura, EstadoFactura
    facturas = db.query(Factura).filter(
        extract("year", Factura.fecha_emision) == anio,
        Factura.estado.in_([EstadoFactura.emitida, EstadoFactura.pagada]),
    ).all()
    return sum(f.total for f in facturas)


def _totales_anio(db: Session, anio: int) -> dict:
    ingresos = _ingresos_ventas(db, anio) + _ingresos_queseria(db, anio) + _ingresos_facturacion(db, anio)
    gastos = sum(g.importe for g in _gastos(db, anio))
    return {"anio": anio, "ingresos": ingresos, "gastos": gastos, "margen": ingresos - gastos}


@router.get("", response_class=HTMLResponse)
def dashboard_rentabilidad(
    request: Request,
    anio: int = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    settings = get_settings()
    anio = anio or date.today().year

    ventas_ganado = _ingresos_ventas(db, anio)
    ingresos_queseria = _ingresos_queseria(db, anio)
    ingresos_facturacion = _ingresos_facturacion(db, anio)
    total_ingresos = ventas_ganado + ingresos_queseria + ingresos_facturacion

    gastos = _gastos(db, anio)
    total_gastos = sum(g.importe for g in gastos)
    gastos_por_categoria = {}
    for g in gastos:
        gastos_por_categoria[g.categoria] = gastos_por_categoria.get(g.categoria, 0) + g.importe
    max_gasto_categoria = max(gastos_por_categoria.values(), default=0)

    margen = total_ingresos - total_gastos
    pct_margen = (margen / total_ingresos * 100) if total_ingresos else None

    censo_activo = db.query(Animal).filter(Animal.fecha_baja.is_(None)).count()
    margen_por_animal = (margen / censo_activo) if censo_activo else None

    ingresos_por_origen = [{"nombre": "Ventas de ganado", "importe": ventas_ganado}]
    if "queseria" in settings.MODULOS:
        ingresos_por_origen.append({"nombre": "Quesería (venta directa)", "importe": ingresos_queseria})
    if "facturacion" in settings.MODULOS:
        ingresos_por_origen.append({"nombre": "Facturación", "importe": ingresos_facturacion})
    max_ingreso_origen = max((o["importe"] for o in ingresos_por_origen), default=0)

    anios_con_datos = {
        int(r[0]) for r in db.query(extract("year", Venta.fecha)).distinct().all() if r[0]
    } | {
        int(r[0]) for r in db.query(extract("year", Gasto.fecha)).distinct().all() if r[0]
    }
    anios_con_datos.add(anio)
    anios_evolucion = sorted(anios_con_datos, reverse=True)[:6]
    evolucion = [_totales_anio(db, a) for a in sorted(anios_evolucion)]
    max_evolucion = max((max(e["ingresos"], e["gastos"]) for e in evolucion), default=0)

    return templates.TemplateResponse("rentabilidad/dashboard.html", {
        "request": request,
        "anio": anio,
        "anios_disponibles": sorted(anios_con_datos, reverse=True),
        "total_ingresos": total_ingresos,
        "total_gastos": total_gastos,
        "margen": margen,
        "pct_margen": pct_margen,
        "censo_activo": censo_activo,
        "margen_por_animal": margen_por_animal,
        "ingresos_por_origen": ingresos_por_origen,
        "max_ingreso_origen": max_ingreso_origen,
        "gastos_por_categoria": gastos_por_categoria,
        "max_gasto_categoria": max_gasto_categoria,
        "evolucion": evolucion,
        "max_evolucion": max_evolucion,
        "current_user": current_user,
    })
