import os
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import date

from config import get_settings
from database import create_tables, get_db, SessionLocal
from auth import get_current_user, get_current_user_optional
from models.usuario import Usuario
from models.animal import Animal, EstadoAnimal, SexoAnimal
from models.reproduccion import Reproduccion
from models.alerta import Alerta, NivelAlerta
from models.alimentacion import Alimento
from models.tarea import Tarea
from models.maestros import Especie
from models.cuaderno import ConfigExplotacion
from services.stock_calculator import resumen_stock
from scheduler import iniciar_scheduler

from fastapi.responses import JSONResponse
from routers import auth, animales, reproduccion, alimentacion, sanidad, lotes, economia, exportacion, maestros, cuaderno, tareas, presupuesto, queseria, trazabilidad, analisis_leche, maquinaria, agroturismo, facturacion, rentabilidad, bienestar


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    db = SessionLocal()
    try:
        config = db.query(ConfigExplotacion).first()
        hora_alertas = (config.hora_alertas if config and config.hora_alertas else "07:00")
    finally:
        db.close()
    scheduler = iniciar_scheduler(hora_alertas)
    app.state.scheduler = scheduler
    yield
    scheduler.shutdown()


app = FastAPI(title="GranjaManager", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
os.makedirs(get_settings().UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=get_settings().UPLOADS_DIR), name="uploads")
templates = Jinja2Templates(directory="templates")


@app.middleware("http")
async def inject_estado_instalacion(request: Request, call_next):
    # Se expone vía request.state (evita que cada router/plantilla tenga que
    # recibir la variable a mano) para que base.html pueda mostrar el aviso de
    # demo y ocultar del menú los módulos no contratados en esta instalación.
    settings = get_settings()
    request.state.demo_mode = settings.DEMO_MODE
    request.state.modulos = settings.MODULOS
    return await call_next(request)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return templates.TemplateResponse("error_datos.html", {"request": request}, status_code=400)

# Núcleo: siempre activo, no es seleccionable por instalación.
app.include_router(auth.router)
app.include_router(animales.router)
app.include_router(reproduccion.router)
app.include_router(sanidad.router)
app.include_router(lotes.router)
app.include_router(maestros.router)
app.include_router(tareas.router)

# Opcionales: se activan según MODULOS (ver config.py). Si no se incluye el
# router, la URL del módulo da 404 en vez de solo ocultarse del menú.
_modulos = get_settings().MODULOS
if "alimentacion" in _modulos:
    app.include_router(alimentacion.router)
if "economia" in _modulos:
    app.include_router(economia.router)
    app.include_router(presupuesto.router)
if "cuaderno" in _modulos:
    app.include_router(cuaderno.router)
    app.include_router(exportacion.router)
if "queseria" in _modulos:
    app.include_router(queseria.router)
    app.include_router(trazabilidad.router)
if "analisis_leche" in _modulos:
    app.include_router(analisis_leche.router)
if "maquinaria" in _modulos:
    app.include_router(maquinaria.router)
if "agroturismo" in _modulos:
    app.include_router(agroturismo.router)
if "facturacion" in _modulos:
    app.include_router(facturacion.router)
if "rentabilidad" in _modulos:
    app.include_router(rentabilidad.router)
if "bienestar" in _modulos:
    app.include_router(bienestar.router)


@app.get("/health")
def health():
    return JSONResponse({"status": "ok"})


@app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()

    # Censo (tarjetas "Vacas/Gestantes/Lactantes/Terneros" = solo vacuno;
    # los animales sin especie registrada se asumen vacuno por compatibilidad)
    bovino = db.query(Especie).filter(Especie.nombre == "Bovino").first()
    es_bovino = or_(Animal.especie_id.is_(None), Animal.especie_id == (bovino.id if bovino else -1))

    total_vacas = db.query(Animal).filter(
        Animal.sexo == SexoAnimal.hembra, Animal.fecha_baja.is_(None),
        Animal.estado != EstadoAnimal.ternero, es_bovino,
    ).count()
    gestantes = db.query(Animal).filter(Animal.estado == EstadoAnimal.gestante, Animal.fecha_baja.is_(None), es_bovino).count()
    lactantes = db.query(Animal).filter(Animal.estado == EstadoAnimal.lactante, Animal.fecha_baja.is_(None), es_bovino).count()
    vacias = db.query(Animal).filter(Animal.estado == EstadoAnimal.vacia, Animal.fecha_baja.is_(None), es_bovino).count()
    terneros = db.query(Animal).filter(Animal.estado == EstadoAnimal.ternero, Animal.fecha_baja.is_(None), es_bovino).count()

    # Otras especies (resumen aparte, para no mezclar con el censo de vacuno)
    conteo_otras = {}
    for a in db.query(Animal).filter(Animal.fecha_baja.is_(None), Animal.especie_id.isnot(None)).all():
        if bovino and a.especie_id == bovino.id:
            continue
        conteo_otras[a.especie.nombre] = conteo_otras.get(a.especie.nombre, 0) + 1
    otras_especies = sorted(conteo_otras.items())

    # Próximos partos (30 días)
    from datetime import timedelta
    proximos_partos = db.query(Reproduccion).filter(
        Reproduccion.parto_fecha.is_(None),
        Reproduccion.fecha_parto_estimada >= hoy,
        Reproduccion.fecha_parto_estimada <= hoy + timedelta(days=30),
    ).order_by(Reproduccion.fecha_parto_estimada).all()

    # Alertas no leídas
    alertas = db.query(Alerta).filter(
        Alerta.leida == False
    ).order_by(Alerta.nivel.desc(), Alerta.fecha_disparo.desc()).limit(10).all()

    # Stock alimentación (solo si el módulo está activo en esta instalación)
    stocks_alerta = []
    if "alimentacion" in get_settings().MODULOS:
        stocks = resumen_stock(db)
        stocks_alerta = [s for s in stocks if s["alerta"]]

    # Tareas pendientes (vencidas primero, luego por fecha límite más próxima)
    tareas_pendientes = db.query(Tarea).filter(Tarea.completada == False).order_by(
        Tarea.fecha_limite.is_(None), Tarea.fecha_limite
    ).limit(6).all()
    n_tareas_pendientes = db.query(Tarea).filter(Tarea.completada == False).count()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": current_user,
        "hoy": hoy,
        "total_vacas": total_vacas,
        "gestantes": gestantes,
        "lactantes": lactantes,
        "vacias": vacias,
        "terneros": terneros,
        "otras_especies": otras_especies,
        "proximos_partos": proximos_partos,
        "alertas": alertas,
        "alertas_count": len(alertas),
        "stocks_alerta": stocks_alerta,
        "tareas_pendientes": tareas_pendientes,
        "n_tareas_pendientes": n_tareas_pendientes,
    })


@app.post("/alertas/{alerta_id}/leer")
def marcar_alerta_leida(
    alerta_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    alerta = db.query(Alerta).filter(Alerta.id == alerta_id).first()
    if alerta:
        alerta.leida = True
        db.commit()
    return RedirectResponse(url="/", status_code=302)
