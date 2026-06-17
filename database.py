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
    from models import animal, reproduccion, lote, sanidad, alimentacion, economia, alerta, usuario
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()


def _migrate_sqlite():
    """Añade columnas nuevas a tablas existentes en SQLite (idempotente)."""
    if "sqlite" not in DATABASE_URL:
        return
    migrations = [
        ("parcelas", "provincia_codigo", "INTEGER DEFAULT 33"),
        ("parcelas", "municipio_codigo", "INTEGER"),
        ("parcelas", "poligono", "INTEGER"),
        ("parcelas", "parcela_sigpac", "INTEGER"),
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
