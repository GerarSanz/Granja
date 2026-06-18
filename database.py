from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./granja.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from models import animal, reproduccion, lote, sanidad, alimentacion, economia, alerta, usuario, maestros
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()
    _seed_maestros()


def _migrate_sqlite():
    """Añade columnas nuevas a tablas existentes en SQLite (idempotente)."""
    if "sqlite" not in DATABASE_URL:
        return
    migrations = [
        ("parcelas", "provincia_codigo", "INTEGER DEFAULT 33"),
        ("parcelas", "municipio_codigo", "INTEGER"),
        ("parcelas", "poligono", "INTEGER"),
        ("parcelas", "parcela_sigpac", "INTEGER"),
        # desparasitaciones se crea como tabla nueva en create_all — no necesita ALTER TABLE
    ]
    with engine.connect() as conn:
        for tabla, columna, tipo in migrations:
            try:
                conn.execute(__import__("sqlalchemy").text(
                    f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}"
                ))
                conn.commit()
            except Exception:
                pass  # la columna ya existe


def _seed_maestros():
    """Inserta especies y razas iniciales si las tablas están vacías."""
    from models.maestros import Especie, Raza
    db = SessionLocal()
    try:
        if db.query(Especie).count() > 0:
            return
        datos = {
            "Bovino": ["Asturiana de la Montaña", "Asturiana de los Valles", "Frisona", "Parda Alpina",
                       "Limusina", "Charolesa", "Rubia Gallega", "Pirenaica", "Retinta", "Cruzado bovino"],
            "Ovino":  ["Merina", "Latxa", "Churra", "Castellana", "Cruzado ovino"],
            "Caprino": ["Murciana-Granadina", "Malagueña", "Payoya", "Cruzado caprino"],
            "Equino":  ["Pura Raza Española", "Asturcón", "Cruzado equino"],
            "Porcino": ["Ibérico", "Duroc", "Landrace", "Cruzado porcino"],
        }
        for especie_nombre, razas in datos.items():
            e = Especie(nombre=especie_nombre, codigo=especie_nombre[:3].upper())
            db.add(e)
            db.flush()
            for r in razas:
                db.add(Raza(nombre=r, especie_id=e.id))
        db.commit()
    finally:
        db.close()
