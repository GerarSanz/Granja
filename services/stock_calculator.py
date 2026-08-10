from sqlalchemy.orm import Session
from models.alimentacion import Alimento, StockMovimiento, RacionTipo, TipoMovimientoStock
from models.animal import Animal, EstadoAnimal


def stock_actual(db: Session, alimento_id: int) -> float:
    movimientos = db.query(StockMovimiento).filter(
        StockMovimiento.alimento_id == alimento_id
    ).all()
    total = sum(
        m.cantidad_kg if m.tipo_movimiento == TipoMovimientoStock.entrada else -m.cantidad_kg
        for m in movimientos
    )
    return max(0.0, total)


def consumo_diario_alimento(db: Session, alimento_id: int) -> float:
    conteo = _conteo_animales_por_estado_especie(db)
    raciones = db.query(RacionTipo).filter(RacionTipo.alimento_id == alimento_id).all()
    return sum(
        r.kg_por_animal_dia * conteo.get((r.estado_productivo, r.especie_id), 0)
        for r in raciones
    )


def dias_restantes_stock(db: Session, alimento_id: int) -> float | None:
    stock = stock_actual(db, alimento_id)
    consumo = consumo_diario_alimento(db, alimento_id)
    if consumo <= 0:
        return None
    return stock / consumo


def resumen_stock(db: Session) -> list[dict]:
    alimentos = db.query(Alimento).filter(Alimento.activo == True).all()
    result = []
    for a in alimentos:
        stock = stock_actual(db, a.id)
        consumo = consumo_diario_alimento(db, a.id)
        dias = (stock / consumo) if consumo > 0 else None
        result.append({
            "alimento": a,
            "stock_kg": stock,
            "consumo_dia_kg": consumo,
            "dias_restantes": dias,
            "alerta": dias is not None and dias < 21,
        })
    return result


def consumo_total_diario(db: Session) -> dict:
    alimentos = db.query(Alimento).filter(Alimento.activo == True).all()
    return {a.nombre: consumo_diario_alimento(db, a.id) for a in alimentos}


_ESTADO_PRODUCTIVO_POR_ESTADO_ANIMAL = {
    "gestante": EstadoAnimal.gestante,
    "lactante": EstadoAnimal.lactante,
    "vacia": EstadoAnimal.vacia,
    "semental": EstadoAnimal.semental,
    "ternero_lactante": EstadoAnimal.ternero,
    "ternero_destete": EstadoAnimal.recria,
}


def _conteo_animales_por_estado_especie(db: Session) -> dict:
    """Cuenta animales activos por (estado_productivo, especie_id)."""
    conteo = {}
    animales = db.query(Animal).filter(Animal.fecha_baja.is_(None)).all()
    for estado_productivo, estado_animal in _ESTADO_PRODUCTIVO_POR_ESTADO_ANIMAL.items():
        for a in animales:
            if a.estado == estado_animal:
                clave = (estado_productivo, a.especie_id)
                conteo[clave] = conteo.get(clave, 0) + 1
    return conteo
