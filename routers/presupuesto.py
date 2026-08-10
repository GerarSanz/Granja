from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import extract
from datetime import date

from database import get_db
from auth import get_current_user
from models.presupuesto import PresupuestoPartida
from models.economia import Venta, Gasto, TipoVenta, CategoriaGasto
from models.usuario import Usuario

router = APIRouter(prefix="/presupuesto", tags=["presupuesto"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def dashboard_presupuesto(
    request: Request,
    anio: int = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    anio = anio or date.today().year

    partidas_ingreso = db.query(PresupuestoPartida).filter(
        PresupuestoPartida.anio == anio,
        PresupuestoPartida.tipo == "ingreso",
    ).all()
    previsto_ingreso = {p.categoria: p.importe_previsto for p in partidas_ingreso}

    lineas_gasto = db.query(PresupuestoPartida).filter(
        PresupuestoPartida.anio == anio,
        PresupuestoPartida.tipo == "gasto",
    ).order_by(PresupuestoPartida.id).all()
    lineas_por_categoria = {}
    for l in lineas_gasto:
        lineas_por_categoria.setdefault(l.categoria, []).append(l)

    ventas = db.query(Venta).filter(extract("year", Venta.fecha) == anio).all()
    gastos = db.query(Gasto).filter(extract("year", Gasto.fecha) == anio).all()

    real_ingresos = {}
    for v in ventas:
        real_ingresos[v.tipo_venta] = real_ingresos.get(v.tipo_venta, 0) + v.importe_total

    real_gastos = {}
    for g in gastos:
        real_gastos[g.categoria] = real_gastos.get(g.categoria, 0) + g.importe

    filas_ingresos = []
    for tv in TipoVenta:
        prev = previsto_ingreso.get(tv.value, 0) or 0
        real = real_ingresos.get(tv.value, 0)
        filas_ingresos.append({
            "categoria": tv.value,
            "previsto": prev,
            "real": real,
            "diferencia": real - prev,
            "pct": (real / prev * 100) if prev else None,
        })

    categorias_gasto = []
    for cg in CategoriaGasto:
        lineas = lineas_por_categoria.get(cg.value, [])
        prev = sum(l.importe_previsto for l in lineas)
        real = real_gastos.get(cg.value, 0)
        categorias_gasto.append({
            "categoria": cg.value,
            "lineas": lineas,
            "previsto": prev,
            "real": real,
            "diferencia": real - prev,
            "pct": (real / prev * 100) if prev else None,
        })

    total_previsto_ingresos = sum(f["previsto"] for f in filas_ingresos)
    total_real_ingresos = sum(f["real"] for f in filas_ingresos)
    total_previsto_gastos = sum(c["previsto"] for c in categorias_gasto)
    total_real_gastos = sum(c["real"] for c in categorias_gasto)

    margen_previsto = total_previsto_ingresos - total_previsto_gastos
    margen_real = total_real_ingresos - total_real_gastos

    anios_set = {
        int(r[0]) for r in db.query(extract("year", Venta.fecha)).distinct().all() if r[0]
    } | {
        int(r[0]) for r in db.query(extract("year", Gasto.fecha)).distinct().all() if r[0]
    } | {
        p.anio for p in (partidas_ingreso + lineas_gasto)
    }
    anios_set.add(anio)

    return templates.TemplateResponse("presupuesto/dashboard.html", {
        "request": request,
        "anio": anio,
        "anios_con_datos": sorted(anios_set, reverse=True),
        "filas_ingresos": filas_ingresos,
        "categorias_gasto": categorias_gasto,
        "total_previsto_ingresos": total_previsto_ingresos,
        "total_real_ingresos": total_real_ingresos,
        "total_previsto_gastos": total_previsto_gastos,
        "total_real_gastos": total_real_gastos,
        "margen_previsto": margen_previsto,
        "margen_real": margen_real,
        "current_user": current_user,
    })


@router.post("/guardar")
async def guardar_presupuesto(
    request: Request,
    anio: int = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Guarda los importes previstos de ingresos (edición global por categoría)."""
    form = await request.form()
    for key, value in form.items():
        if key == "anio" or "__" not in key:
            continue
        tipo, categoria = key.split("__", 1)
        if tipo != "ingreso":
            continue
        try:
            importe = float(value) if value not in (None, "") else 0.0
        except ValueError:
            continue
        partida = db.query(PresupuestoPartida).filter(
            PresupuestoPartida.anio == anio,
            PresupuestoPartida.tipo == "ingreso",
            PresupuestoPartida.categoria == categoria,
        ).first()
        if not partida:
            partida = PresupuestoPartida(anio=anio, tipo="ingreso", categoria=categoria, importe_previsto=0)
            db.add(partida)
        partida.importe_previsto = importe
    db.commit()
    return RedirectResponse(url=f"/presupuesto?anio={anio}", status_code=302)


@router.post("/gasto/linea/nueva")
def nueva_linea_gasto(
    anio: int = Form(...),
    categoria: str = Form(...),
    concepto: str = Form(default=""),
    importe: float = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db.add(PresupuestoPartida(
        anio=anio,
        tipo="gasto",
        categoria=categoria,
        concepto=concepto.strip() or None,
        importe_previsto=importe,
    ))
    db.commit()
    return RedirectResponse(url=f"/presupuesto?anio={anio}", status_code=302)


@router.post("/gasto/linea/{linea_id}/editar")
def editar_linea_gasto(
    linea_id: int,
    concepto: str = Form(default=""),
    importe: float = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    l = db.query(PresupuestoPartida).filter(PresupuestoPartida.id == linea_id).first()
    if not l:
        raise HTTPException(status_code=404)
    l.concepto = concepto.strip() or None
    l.importe_previsto = importe
    db.commit()
    return RedirectResponse(url=f"/presupuesto?anio={l.anio}", status_code=302)


@router.post("/gasto/linea/{linea_id}/eliminar")
def eliminar_linea_gasto(
    linea_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    l = db.query(PresupuestoPartida).filter(PresupuestoPartida.id == linea_id).first()
    anio = l.anio if l else date.today().year
    if l:
        db.delete(l)
        db.commit()
    return RedirectResponse(url=f"/presupuesto?anio={anio}", status_code=302)
