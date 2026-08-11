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
    from models import animal, reproduccion, lote, sanidad, alimentacion, economia, alerta, usuario, maestros, cuaderno, tarea, presupuesto, queseria, analisis_leche, maquinaria, agroturismo, facturacion, bienestar
    _migrate_esquema_queseria_v2()
    _migrate_lotes_queso_piezas_nullable()
    _migrate_tratamientos_animal_nullable()
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()
    _seed_maestros()
    _backfill_especie_animales()
    _backfill_especie_raciones()


def _migrate_lotes_queso_piezas_nullable():
    """Relaja num_piezas_inicial a NULL (las piezas se conocen al moldear, no al
    cuajar). SQLite no permite ALTER COLUMN, así que reconstruye la tabla
    preservando los datos existentes."""
    if "sqlite" not in DATABASE_URL:
        return
    import sqlalchemy as sa
    from models.queseria import LoteQueso
    with engine.connect() as conn:
        try:
            cols = conn.execute(sa.text("PRAGMA table_info(lotes_queso)")).fetchall()
        except Exception:
            return
        if not cols:
            return  # la tabla no existe todavía; create_all la creará con el esquema nuevo
        piezas_col = next((c for c in cols if c[1] == "num_piezas_inicial"), None)
        if not piezas_col or piezas_col[3] == 0:
            return  # ya es nullable (o no existe la columna todavía)
        old_col_names = [c[1] for c in cols]
        conn.execute(sa.text("ALTER TABLE lotes_queso RENAME TO lotes_queso_old_tmp"))
        # Los índices con nombre explícito (p.ej. ix_lotes_queso_id) se quedan
        # apuntando a la tabla renombrada y chocarían al crear la tabla nueva.
        indices = conn.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='lotes_queso_old_tmp' AND name NOT LIKE 'sqlite_autoindex%'"
        )).fetchall()
        for (idx_name,) in indices:
            conn.execute(sa.text(f"DROP INDEX {idx_name}"))
        conn.commit()

    LoteQueso.__table__.create(bind=engine)

    with engine.connect() as conn:
        nuevas_cols = {c.name for c in LoteQueso.__table__.columns}
        comunes = [c for c in old_col_names if c in nuevas_cols]
        cols_sql = ", ".join(comunes)
        conn.execute(sa.text(f"INSERT INTO lotes_queso ({cols_sql}) SELECT {cols_sql} FROM lotes_queso_old_tmp"))
        conn.execute(sa.text("DROP TABLE lotes_queso_old_tmp"))
        conn.commit()


def _migrate_tratamientos_animal_nullable():
    """Relaja animal_crotal a NULL (un tratamiento ahora puede aplicarse a todo
    el rebaño o a un lote entero, no solo a un animal). SQLite no permite ALTER
    COLUMN, así que reconstruye la tabla preservando los datos existentes."""
    if "sqlite" not in DATABASE_URL:
        return
    import sqlalchemy as sa
    from models.sanidad import Tratamiento
    with engine.connect() as conn:
        try:
            cols = conn.execute(sa.text("PRAGMA table_info(tratamientos)")).fetchall()
        except Exception:
            return
        if not cols:
            return  # la tabla no existe todavía; create_all la creará con el esquema nuevo
        crotal_col = next((c for c in cols if c[1] == "animal_crotal"), None)
        if not crotal_col or crotal_col[3] == 0:
            return  # ya es nullable (o no existe la columna todavía)
        old_col_names = [c[1] for c in cols]
        conn.execute(sa.text("ALTER TABLE tratamientos RENAME TO tratamientos_old_tmp"))
        indices = conn.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tratamientos_old_tmp' AND name NOT LIKE 'sqlite_autoindex%'"
        )).fetchall()
        for (idx_name,) in indices:
            conn.execute(sa.text(f"DROP INDEX {idx_name}"))
        conn.commit()

    Tratamiento.__table__.create(bind=engine)

    with engine.connect() as conn:
        nuevas_cols = {c.name for c in Tratamiento.__table__.columns}
        comunes = [c for c in old_col_names if c in nuevas_cols]
        cols_sql = ", ".join(comunes)
        conn.execute(sa.text(f"INSERT INTO tratamientos ({cols_sql}) SELECT {cols_sql} FROM tratamientos_old_tmp"))
        conn.execute(sa.text("DROP TABLE tratamientos_old_tmp"))
        conn.commit()


def _migrate_esquema_queseria_v2():
    """Corrige el esquema inicial de lotes_queso (peso obligatorio -> opcional,
    y nuevas columnas de etapa). Solo actúa si la tabla tiene el esquema viejo
    y está vacía (para no arriesgar datos reales)."""
    if "sqlite" not in DATABASE_URL:
        return
    import sqlalchemy as sa
    with engine.connect() as conn:
        try:
            cols = conn.execute(sa.text("PRAGMA table_info(lotes_queso)")).fetchall()
        except Exception:
            return
        if not cols:
            return  # la tabla no existe todavía; create_all la creará con el esquema nuevo
        col_names = {c[1] for c in cols}
        peso_col = next((c for c in cols if c[1] == "peso_inicial_kg"), None)
        esquema_viejo = (peso_col is not None and peso_col[3] == 1) or "etapa" not in col_names
        if esquema_viejo:
            count = conn.execute(sa.text("SELECT COUNT(*) FROM lotes_queso")).scalar()
            if count == 0:
                conn.execute(sa.text("DROP TABLE IF EXISTS movimientos_queso"))
                conn.execute(sa.text("DROP TABLE IF EXISTS lotes_queso"))
                conn.commit()


def _migrate_sqlite():
    """Añade columnas nuevas a tablas existentes en SQLite (idempotente)."""
    if "sqlite" not in DATABASE_URL:
        return
    migrations = [
        ("parcelas", "provincia_codigo", "INTEGER DEFAULT 33"),
        ("parcelas", "municipio_codigo", "INTEGER"),
        ("parcelas", "poligono", "INTEGER"),
        ("parcelas", "parcela_sigpac", "INTEGER"),
        # Cuaderno de explotación — parcelas
        ("parcelas", "especie_cultivo", "TEXT"),
        ("parcelas", "variedad_cultivo", "TEXT"),
        ("parcelas", "regadio", "TEXT DEFAULT 'SEC'"),
        ("parcelas", "tipo_proteccion", "TEXT DEFAULT 'AL'"),
        # Cuaderno de explotación — tratamientos de parcela
        ("tratamientos_parcela", "num_registro_fito", "TEXT"),
        ("tratamientos_parcela", "problema_fitosanitario", "TEXT"),
        ("tratamientos_parcela", "eficacia", "TEXT"),
        ("tratamientos_parcela", "aplicador_nombre", "TEXT"),
        # Cuaderno de explotación — abonos de parcela
        ("abonos_parcela", "albaran", "TEXT"),
        ("abonos_parcela", "riqueza_npk", "TEXT"),
        ("abonos_parcela", "tipo_fertilizacion", "TEXT DEFAULT 'AF'"),
        # Presupuesto — líneas de concepto por categoría de gasto
        ("presupuesto_partidas", "concepto", "TEXT"),
        # Multi-especie — animales
        ("animales", "especie_id", "INTEGER"),
        # Multi-especie — raciones de alimentación
        ("raciones_tipo", "especie_id", "INTEGER"),
        # Alertas de tareas vencidas
        ("alertas", "tarea_id", "INTEGER"),
        # Migración WhatsApp → Telegram
        ("alertas", "enviada_telegram", "BOOLEAN DEFAULT 0"),
        ("usuarios", "telegram_chat_id", "TEXT"),
        # Alertas de lotes de queso listos para vender
        ("alertas", "lote_queso_id", "INTEGER"),
        # Trazabilidad del cuajo empleado en cada lote de queso
        ("lotes_queso", "cuajo_marca", "TEXT"),
        ("lotes_queso", "cuajo_registro_sanitario", "TEXT"),
        ("lotes_queso", "cuajo_lote", "TEXT"),
        ("lotes_queso", "cuajo_caducidad", "DATE"),
        # Turno de ordeño (mañana/tarde) del que procede la leche del lote
        ("lotes_queso", "turno_ordeno", "TEXT"),
        # Ubicación física en la cámara de curación
        ("lotes_queso", "estanteria", "TEXT"),
        ("lotes_queso", "fila", "INTEGER"),
        ("lotes_queso", "columna", "INTEGER"),
        # Hora configurable de envío de alertas por Telegram
        ("config_explotacion", "hora_alertas", "TEXT DEFAULT '07:00'"),
        # Desparasitaciones aplicadas a un lote completo (además de todo el rebaño / animal individual)
        ("desparasitaciones", "lote_id", "INTEGER"),
        # Tratamientos aplicados a todo el rebaño o a un lote completo (además de individual)
        ("tratamientos", "aplica_todo_rebano", "BOOLEAN DEFAULT 0"),
        ("tratamientos", "lote_id", "INTEGER"),
        # Plan vacunal aplicado a un lote completo
        ("plan_vacunal", "lote_id", "INTEGER"),
        # Alertas de revisión de maquinaria
        ("alertas", "maquina_id", "INTEGER"),
        # Alertas de acciones correctoras de bienestar animal vencidas
        ("alertas", "indicador_bienestar_id", "INTEGER"),
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


def _backfill_especie_animales():
    """Asigna especie_id a animales existentes sin especie, según su raza
    (o Bovino por defecto, ya que la explotación era 100% vacuno)."""
    from models.animal import Animal
    from models.maestros import Especie, Raza
    db = SessionLocal()
    try:
        pendientes = db.query(Animal).filter(Animal.especie_id.is_(None)).all()
        if not pendientes:
            return
        bovino = db.query(Especie).filter(Especie.nombre == "Bovino").first()
        razas_por_nombre = {r.nombre.lower(): r.especie_id for r in db.query(Raza).all()}
        for a in pendientes:
            especie_id = razas_por_nombre.get((a.raza or "").lower())
            a.especie_id = especie_id or (bovino.id if bovino else None)
        db.commit()
    finally:
        db.close()


def _backfill_especie_raciones():
    """Asigna especie_id a raciones existentes sin especie (todas eran de vacuno)."""
    from models.alimentacion import RacionTipo
    from models.maestros import Especie
    db = SessionLocal()
    try:
        pendientes = db.query(RacionTipo).filter(RacionTipo.especie_id.is_(None)).all()
        if not pendientes:
            return
        bovino = db.query(Especie).filter(Especie.nombre == "Bovino").first()
        if not bovino:
            return
        for r in pendientes:
            r.especie_id = bovino.id
        db.commit()
    finally:
        db.close()
