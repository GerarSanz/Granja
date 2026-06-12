from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from datetime import date

from database import create_tables, get_db
from auth import get_current_user, get_current_user_optional
from models.usuario import Usuario
from models.animal import Animal, EstadoAnimal, SexoAnimal
from models.reproduccion import Reproduccion
from models.alerta import Alerta, NivelAlerta
from models.alimentacion import Alimento
from services.stock_calculator import resumen_stock
from scheduler import iniciar_scheduler

from fastapi.responses import JSONResponse
from routers import auth, animales, reproduccion, alimentacion


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    scheduler = iniciar_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(title="GranjaManager", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth.router)
app.include_router(animales.router)
app.include_router(reproduccion.router)
app.include_router(alimentacion.router)


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

    # Censo
    total_vacas = db.query(Animal).filter(
        Animal.sexo == SexoAnimal.hembra, Animal.fecha_baja.is_(None),
        Animal.estado != EstadoAnimal.ternero
    ).count()
    gestantes = db.query(Animal).filter(Animal.estado == EstadoAnimal.gestante, Animal.fecha_baja.is_(None)).count()
    lactantes = db.query(Animal).filter(Animal.estado == EstadoAnimal.lactante, Animal.fecha_baja.is_(None)).count()
    vacias = db.query(Animal).filter(Animal.estado == EstadoAnimal.vacia, Animal.fecha_baja.is_(None)).count()
    terneros = db.query(Animal).filter(Animal.estado == EstadoAnimal.ternero, Animal.fecha_baja.is_(None)).count()

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

    # Stock alimentación
    stocks = resumen_stock(db)
    stocks_alerta = [s for s in stocks if s["alerta"]]

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": current_user,
        "hoy": hoy,
        "total_vacas": total_vacas,
        "gestantes": gestantes,
        "lactantes": lactantes,
        "vacias": vacias,
        "terneros": terneros,
        "proximos_partos": proximos_partos,
        "alertas": alertas,
        "alertas_count": len(alertas),
        "stocks_alerta": stocks_alerta,
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
