import asyncio
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
from config import get_settings
from models.agroturismo import ActividadTurismo, ReservaTurismo, EstadoReserva
from models.usuario import Usuario
from services.turismo_calculator import plazas_disponibles_minimas, ocupacion_por_dia
from services.telegram import enviar_telegram
from services.email import enviar_email

router = APIRouter(prefix="/agroturismo", tags=["agroturismo"])
templates = Jinja2Templates(directory="templates")


def _notificar_reserva(r: ReservaTurismo, actividad: ActividadTurismo, motivo: str):
    settings = get_settings()
    fechas = r.fecha_inicio.strftime("%d/%m/%Y")
    if r.fecha_fin != r.fecha_inicio:
        fechas += f" a {r.fecha_fin.strftime('%d/%m/%Y')}"

    mensaje_titular = (
        f"{motivo}: {actividad.nombre}\n"
        f"{r.nombre_visitante} — {r.num_personas} persona(s)\n"
        f"Fechas: {fechas}\n"
        f"Estado: {r.estado}" +
        (f"\nTel: {r.telefono}" if r.telefono else "")
    )
    try:
        asyncio.run(enviar_telegram(f"[GranjaManager] {mensaje_titular}"))
    except Exception:
        pass

    if r.email:
        cuerpo = (
            f"Hola {r.nombre_visitante},\n\n"
            f"{motivo} en {settings.EXPLOTACION_NOMBRE}:\n\n"
            f"- Actividad: {actividad.nombre}\n"
            f"- Fechas: {fechas}\n"
            f"- Personas: {r.num_personas}\n"
            f"- Estado: {r.estado}\n"
            + (f"- Precio total: {r.precio_total:.2f} €\n" if r.precio_total else "")
            + "\nSi tiene cualquier duda, puede responder a este correo.\n\n"
            f"Un saludo,\n{settings.EXPLOTACION_NOMBRE}"
        )
        enviar_email(r.email, f"{motivo} — {settings.EXPLOTACION_NOMBRE}", cuerpo)


def _construir_reserva(datos: "ReservaForm", db: Session, excluir_reserva_id: int = None) -> tuple[ReservaTurismo, ActividadTurismo]:
    actividad = db.query(ActividadTurismo).filter(ActividadTurismo.id == datos.actividad_id).first()
    if not actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    if datos.fecha_fin < datos.fecha_inicio:
        raise HTTPException(status_code=400, detail="La fecha de fin no puede ser anterior a la de inicio")

    libres = plazas_disponibles_minimas(db, actividad, datos.fecha_inicio, datos.fecha_fin, excluir_reserva_id)
    if datos.num_personas > libres:
        raise HTTPException(
            status_code=400,
            detail=f"No hay suficientes plazas para esas fechas en «{actividad.nombre}» — quedan {libres}",
        )

    precio_total = datos.precio_total
    if precio_total is None and actividad.precio_persona:
        precio_total = actividad.precio_persona * datos.num_personas

    return actividad, precio_total


class ReservaForm:
    def __init__(
        self,
        actividad_id: str = Form(...),
        fecha_inicio: str = Form(...),
        fecha_fin: str = Form(default=""),
        num_personas: str = Form(default="1"),
        nombre_visitante: str = Form(...),
        email: str = Form(default=""),
        telefono: str = Form(default=""),
        estado: str = Form(default=EstadoReserva.pendiente),
        precio_total: str = Form(default=""),
        pagado: str = Form(default=""),
        observaciones: str = Form(default=""),
    ):
        self.actividad_id = int(actividad_id)
        self.fecha_inicio = date.fromisoformat(fecha_inicio)
        self.fecha_fin = date.fromisoformat(fecha_fin) if fecha_fin else self.fecha_inicio
        self.num_personas = int(num_personas) if num_personas else 1
        self.nombre_visitante = nombre_visitante
        self.email = email or None
        self.telefono = telefono or None
        self.estado = estado or EstadoReserva.pendiente
        self.precio_total = float(precio_total) if precio_total else None
        self.pagado = bool(pagado)
        self.observaciones = observaciones or None


@router.get("", response_class=HTMLResponse)
def lista_agroturismo(
    request: Request,
    actividad_id: str = None,
    estado: str = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()
    actividades = db.query(ActividadTurismo).order_by(ActividadTurismo.nombre).all()

    q = db.query(ReservaTurismo)
    if actividad_id:
        q = q.filter(ReservaTurismo.actividad_id == int(actividad_id))
    if estado:
        q = q.filter(ReservaTurismo.estado == estado)
    reservas = q.order_by(ReservaTurismo.fecha_inicio.desc()).all()

    proximas = db.query(ReservaTurismo).filter(
        ReservaTurismo.estado != EstadoReserva.cancelada,
        ReservaTurismo.fecha_fin >= hoy,
    ).order_by(ReservaTurismo.fecha_inicio).limit(8).all()

    ingresos_previstos = sum(
        (r.precio_total or 0) for r in db.query(ReservaTurismo).filter(
            ReservaTurismo.estado.in_([EstadoReserva.pendiente, EstadoReserva.confirmada]),
            ReservaTurismo.fecha_fin >= hoy,
        ).all()
    )

    disponibilidad = None
    actividad_disp = None
    activas = [a for a in actividades if a.activa]
    if activas:
        actividad_disp_id = int(actividad_id) if actividad_id else activas[0].id
        actividad_disp = next((a for a in activas if a.id == actividad_disp_id), activas[0])
        desde = hoy
        hasta = hoy + timedelta(days=13)
        ocupacion = ocupacion_por_dia(db, actividad_disp.id, desde, hasta)
        disponibilidad = [
            {
                "fecha": d,
                "ocupadas": ocupacion.get(d, 0),
                "libres": max(0, actividad_disp.capacidad_maxima - ocupacion.get(d, 0)),
            }
            for d in sorted(ocupacion.keys())
        ]

    return templates.TemplateResponse("agroturismo/lista.html", {
        "request": request,
        "actividades": actividades,
        "reservas": reservas,
        "proximas": proximas,
        "ingresos_previstos": ingresos_previstos,
        "disponibilidad": disponibilidad,
        "actividad_disp": actividad_disp,
        "hoy": hoy,
        "current_user": current_user,
        "filtro_actividad": actividad_id,
        "filtro_estado": estado,
    })


@router.post("/actividad/nueva")
def nueva_actividad(
    nombre: str = Form(...),
    tipo: str = Form(default="visita"),
    descripcion: str = Form(default=""),
    capacidad_maxima: str = Form(default="10"),
    precio_persona: str = Form(default=""),
    duracion_horas: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    a = ActividadTurismo(
        nombre=nombre,
        tipo=tipo,
        descripcion=descripcion or None,
        capacidad_maxima=int(capacidad_maxima) if capacidad_maxima else 10,
        precio_persona=float(precio_persona) if precio_persona else None,
        duracion_horas=float(duracion_horas) if duracion_horas else None,
        observaciones=observaciones or None,
    )
    db.add(a)
    db.commit()
    return RedirectResponse(url="/agroturismo?guardado=1", status_code=302)


@router.post("/actividad/{actividad_id}/editar")
def editar_actividad(
    actividad_id: int,
    nombre: str = Form(...),
    tipo: str = Form(default="visita"),
    descripcion: str = Form(default=""),
    capacidad_maxima: str = Form(default="10"),
    precio_persona: str = Form(default=""),
    duracion_horas: str = Form(default=""),
    activa: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    a = db.query(ActividadTurismo).filter(ActividadTurismo.id == actividad_id).first()
    if not a:
        raise HTTPException(status_code=404)
    a.nombre = nombre
    a.tipo = tipo
    a.descripcion = descripcion or None
    a.capacidad_maxima = int(capacidad_maxima) if capacidad_maxima else 10
    a.precio_persona = float(precio_persona) if precio_persona else None
    a.duracion_horas = float(duracion_horas) if duracion_horas else None
    a.activa = bool(activa)
    a.observaciones = observaciones or None
    db.commit()
    return RedirectResponse(url="/agroturismo?guardado=1", status_code=302)


@router.post("/actividad/{actividad_id}/eliminar")
def eliminar_actividad(
    actividad_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    a = db.query(ActividadTurismo).filter(ActividadTurismo.id == actividad_id).first()
    if a:
        db.delete(a)
        db.commit()
    return RedirectResponse(url="/agroturismo", status_code=302)


@router.post("/reserva/nueva")
def nueva_reserva(
    datos: ReservaForm = Depends(),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    actividad, precio_total = _construir_reserva(datos, db)

    r = ReservaTurismo(
        actividad_id=actividad.id,
        fecha_inicio=datos.fecha_inicio,
        fecha_fin=datos.fecha_fin,
        num_personas=datos.num_personas,
        nombre_visitante=datos.nombre_visitante,
        email=datos.email,
        telefono=datos.telefono,
        estado=EstadoReserva.pendiente,
        precio_total=precio_total,
        pagado=datos.pagado,
        observaciones=datos.observaciones,
    )
    db.add(r)
    db.commit()
    db.refresh(r)

    _notificar_reserva(r, actividad, "Nueva reserva")

    return RedirectResponse(url="/agroturismo?guardado=1", status_code=302)


@router.post("/reserva/{reserva_id}/editar")
def editar_reserva(
    reserva_id: int,
    datos: ReservaForm = Depends(),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    r = db.query(ReservaTurismo).filter(ReservaTurismo.id == reserva_id).first()
    if not r:
        raise HTTPException(status_code=404)

    estado_anterior = r.estado
    actividad, precio_total = _construir_reserva(datos, db, excluir_reserva_id=reserva_id)

    r.actividad_id = actividad.id
    r.fecha_inicio = datos.fecha_inicio
    r.fecha_fin = datos.fecha_fin
    r.num_personas = datos.num_personas
    r.nombre_visitante = datos.nombre_visitante
    r.email = datos.email
    r.telefono = datos.telefono
    r.estado = datos.estado
    r.precio_total = precio_total if precio_total is not None else datos.precio_total
    r.pagado = datos.pagado
    r.observaciones = datos.observaciones
    db.commit()

    if r.estado != estado_anterior:
        motivo = "Reserva cancelada" if r.estado == EstadoReserva.cancelada else "Reserva actualizada"
        _notificar_reserva(r, actividad, motivo)

    return RedirectResponse(url="/agroturismo?guardado=1", status_code=302)


@router.post("/reserva/{reserva_id}/cancelar")
def cancelar_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    r = db.query(ReservaTurismo).filter(ReservaTurismo.id == reserva_id).first()
    if not r:
        raise HTTPException(status_code=404)
    r.estado = EstadoReserva.cancelada
    db.commit()
    _notificar_reserva(r, r.actividad, "Reserva cancelada")
    return RedirectResponse(url="/agroturismo?guardado=1", status_code=302)


@router.post("/reserva/{reserva_id}/eliminar")
def eliminar_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    r = db.query(ReservaTurismo).filter(ReservaTurismo.id == reserva_id).first()
    if r:
        db.delete(r)
        db.commit()
    return RedirectResponse(url="/agroturismo", status_code=302)
