from sqlalchemy import Column, Integer, String, Date, DateTime, Float, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


class TipoActividad(str, enum.Enum):
    visita = "visita"
    degustacion = "degustacion"
    taller = "taller"
    alojamiento = "alojamiento"
    otro = "otro"


class EstadoReserva(str, enum.Enum):
    pendiente = "pendiente"
    confirmada = "confirmada"
    cancelada = "cancelada"
    completada = "completada"


class ActividadTurismo(Base):
    __tablename__ = "actividades_turismo"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    tipo = Column(String(30), nullable=False, default=TipoActividad.visita)
    descripcion = Column(Text, nullable=True)
    capacidad_maxima = Column(Integer, nullable=False, default=10)
    precio_persona = Column(Float, nullable=True)  # None = gratis / a consultar
    duracion_horas = Column(Float, nullable=True)  # aplica a visita/degustacion/taller, no a alojamiento
    activa = Column(Boolean, default=True)
    observaciones = Column(Text, nullable=True)

    reservas = relationship("ReservaTurismo", back_populates="actividad", cascade="all, delete-orphan")


class ReservaTurismo(Base):
    __tablename__ = "reservas_turismo"

    id = Column(Integer, primary_key=True, index=True)
    actividad_id = Column(Integer, ForeignKey("actividades_turismo.id"), nullable=False)
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin = Column(Date, nullable=False)  # = fecha_inicio si es de un solo día
    num_personas = Column(Integer, nullable=False, default=1)
    nombre_visitante = Column(String(200), nullable=False)
    email = Column(String(150), nullable=True)
    telefono = Column(String(30), nullable=True)
    estado = Column(String(20), nullable=False, default=EstadoReserva.pendiente)
    precio_total = Column(Float, nullable=True)
    pagado = Column(Boolean, default=False)
    observaciones = Column(Text, nullable=True)
    creada_en = Column(DateTime, server_default=func.now())

    actividad = relationship("ActividadTurismo", back_populates="reservas")
