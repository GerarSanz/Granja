from datetime import timedelta, date
from sqlalchemy.orm import Session
from models.agroturismo import ReservaTurismo, ActividadTurismo, EstadoReserva


def _rango_dias(inicio: date, fin: date) -> list[date]:
    dias = []
    d = inicio
    while d <= fin:
        dias.append(d)
        d += timedelta(days=1)
    return dias


def _reservas_activas_en_rango(db: Session, actividad_id: int, desde: date, hasta: date, excluir_reserva_id: int = None):
    q = db.query(ReservaTurismo).filter(
        ReservaTurismo.actividad_id == actividad_id,
        ReservaTurismo.estado != EstadoReserva.cancelada,
        ReservaTurismo.fecha_inicio <= hasta,
        ReservaTurismo.fecha_fin >= desde,
    )
    if excluir_reserva_id:
        q = q.filter(ReservaTurismo.id != excluir_reserva_id)
    return q.all()


def ocupacion_por_dia(db: Session, actividad_id: int, desde: date, hasta: date) -> dict[date, int]:
    """Personas ya reservadas (no canceladas) por cada día del rango, para esa actividad."""
    ocupacion = {d: 0 for d in _rango_dias(desde, hasta)}
    for r in _reservas_activas_en_rango(db, actividad_id, desde, hasta):
        for d in _rango_dias(max(r.fecha_inicio, desde), min(r.fecha_fin, hasta)):
            if d in ocupacion:
                ocupacion[d] += r.num_personas
    return ocupacion


def plazas_disponibles_minimas(db: Session, actividad: ActividadTurismo, fecha_inicio: date, fecha_fin: date,
                                excluir_reserva_id: int = None) -> int:
    """Plazas libres en el día más ocupado del rango — la reserva solo cabe si
    hay sitio TODOS los días que dura, no basta con la media."""
    ocupacion = {d: 0 for d in _rango_dias(fecha_inicio, fecha_fin)}
    for r in _reservas_activas_en_rango(db, actividad.id, fecha_inicio, fecha_fin, excluir_reserva_id):
        for d in _rango_dias(max(r.fecha_inicio, fecha_inicio), min(r.fecha_fin, fecha_fin)):
            if d in ocupacion:
                ocupacion[d] += r.num_personas
    return min(actividad.capacidad_maxima - ocupadas for ocupadas in ocupacion.values())
