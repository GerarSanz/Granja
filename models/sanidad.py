from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base
import enum


class ViaAdministracion(str, enum.Enum):
    oral = "oral"
    inyectable_iv = "inyectable IV"
    inyectable_im = "inyectable IM"
    inyectable_sc = "inyectable SC"
    topico = "tópico"
    intramamario = "intramamario"


class Tratamiento(Base):
    __tablename__ = "tratamientos"

    id = Column(Integer, primary_key=True, index=True)
    animal_crotal = Column(String(20), ForeignKey("animales.crotal"), nullable=False)
    fecha = Column(Date, nullable=False)
    medicamento = Column(String(200), nullable=False)
    principio_activo = Column(String(200), nullable=True)
    dosis = Column(String(100), nullable=True)
    via_administracion = Column(String(50), nullable=True)
    dias_tiempo_espera = Column(Integer, default=0)
    fecha_fin_espera = Column(Date, nullable=True)
    veterinario = Column(String(200), nullable=True)
    num_receta = Column(String(100), nullable=True)
    es_ecologico = Column(Boolean, default=False)
    observaciones = Column(Text, nullable=True)

    animal = relationship("Animal", back_populates="tratamientos")


class PlanVacunal(Base):
    __tablename__ = "plan_vacunal"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=True)
    vacuna = Column(String(200), nullable=False)
    periodicidad_meses = Column(Integer, nullable=True)
    aplica_a = Column(String(50), default="todo_rebano")  # todo_rebano / hembras / machos / terneros
    proxima_fecha = Column(Date, nullable=True)
    ultima_fecha = Column(Date, nullable=True)
    activo = Column(Boolean, default=True)
