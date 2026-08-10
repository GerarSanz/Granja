from sqlalchemy.orm import Session
from datetime import date
from models.queseria import LoteQueso, MovimientoQueso, EtapaQueso


def peso_disponible(db: Session, lote_id: int) -> float:
    lote = db.query(LoteQueso).filter(LoteQueso.id == lote_id).first()
    if not lote or lote.peso_inicial_kg is None:
        return 0.0
    salidas = db.query(MovimientoQueso).filter(MovimientoQueso.lote_id == lote_id).all()
    total_salida = sum(m.peso_kg for m in salidas)
    return max(0.0, lote.peso_inicial_kg - total_salida)


def piezas_disponibles(db: Session, lote_id: int) -> int:
    lote = db.query(LoteQueso).filter(LoteQueso.id == lote_id).first()
    if not lote or lote.num_piezas_inicial is None:
        return 0
    salidas = db.query(MovimientoQueso).filter(
        MovimientoQueso.lote_id == lote_id,
        MovimientoQueso.num_piezas.isnot(None),
    ).all()
    total_salida = sum(m.num_piezas for m in salidas)
    return max(0, lote.num_piezas_inicial - total_salida)


def resumen_lote(db: Session, lote: LoteQueso) -> dict:
    hoy = date.today()
    peso_conocido = lote.peso_inicial_kg is not None
    piezas_conocido = lote.num_piezas_inicial is not None
    peso_kg = peso_disponible(db, lote.id)
    piezas = piezas_disponibles(db, lote.id)
    fecha_estimada = lote.fecha_estimada_lista
    en_curacion = lote.etapa != EtapaQueso.listo
    dias_para_listo = (fecha_estimada - hoy).days if (en_curacion and fecha_estimada) else None
    return {
        "lote": lote,
        "peso_conocido": peso_conocido,
        "peso_disponible_kg": peso_kg,
        "piezas_conocido": piezas_conocido,
        "piezas_disponibles": piezas,
        "agotado": peso_conocido and peso_kg <= 0,
        "en_curacion": en_curacion,
        "fecha_estimada_lista": fecha_estimada,
        "dias_para_listo": dias_para_listo,
    }


def resumen_lotes(db: Session) -> list[dict]:
    lotes = db.query(LoteQueso).order_by(LoteQueso.fecha_elaboracion.desc()).all()
    return [resumen_lote(db, l) for l in lotes]
