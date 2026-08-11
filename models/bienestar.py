from sqlalchemy import Column, Integer, String, Date, ForeignKey, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


class TipoAuditoriaBienestar(str, enum.Enum):
    autoevaluacion = "autoevaluacion"
    oficial = "oficial"
    certificadora = "certificadora"
    otra = "otra"


class CategoriaBienestar(str, enum.Enum):
    alimentacion = "alimentacion"
    alojamiento = "alojamiento"
    salud = "salud"
    comportamiento = "comportamiento"


# Checklist de partida al crear una auditoría — inspirado en los cuatro
# principios de Welfare Quality (r) simplificados. El usuario puede editar,
# borrar o añadir filas antes de guardar.
INDICADORES_DEFECTO = [
    (CategoriaBienestar.alimentacion, "Acceso a agua limpia y en cantidad suficiente"),
    (CategoriaBienestar.alimentacion, "Ausencia de animales con delgadez excesiva (condición corporal)"),
    (CategoriaBienestar.alimentacion, "Ración adecuada al estado productivo de cada grupo"),
    (CategoriaBienestar.alojamiento, "Espacio suficiente para tumbarse y moverse con libertad"),
    (CategoriaBienestar.alojamiento, "Cama o suelo limpio, seco y no resbaladizo"),
    (CategoriaBienestar.alojamiento, "Ventilación adecuada, sin corrientes de aire excesivas"),
    (CategoriaBienestar.alojamiento, "Protección frente a frío, calor o lluvia extremos"),
    (CategoriaBienestar.salud, "Ausencia de cojeras"),
    (CategoriaBienestar.salud, "Ausencia de heridas, lesiones o rozaduras visibles"),
    (CategoriaBienestar.salud, "Ausencia de signos de enfermedad sin tratar"),
    (CategoriaBienestar.salud, "Manejo del dolor en intervenciones (descuerne, castración...)"),
    (CategoriaBienestar.comportamiento, "Los animales pueden expresar comportamiento social normal"),
    (CategoriaBienestar.comportamiento, "Ausencia de signos de miedo ante la presencia humana"),
    (CategoriaBienestar.comportamiento, "Acceso a pastoreo o espacio exterior"),
]


class AuditoriaBienestar(Base):
    __tablename__ = "auditorias_bienestar"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False)
    tipo = Column(String(20), nullable=False, default=TipoAuditoriaBienestar.autoevaluacion)
    responsable = Column(String(200), nullable=True)
    lote_id = Column(Integer, ForeignKey("lotes.id"), nullable=True)  # None = toda la explotación
    observaciones_generales = Column(Text, nullable=True)
    creada_en = Column(DateTime, server_default=func.now())

    lote = relationship("Lote")
    indicadores = relationship("IndicadorBienestar", back_populates="auditoria",
                                cascade="all, delete-orphan", order_by="IndicadorBienestar.orden")

    @property
    def puntuacion_pct(self):
        puntuados = [i.puntuacion for i in self.indicadores if i.puntuacion is not None]
        if not puntuados:
            return None
        return round(sum(puntuados) / (len(puntuados) * 10) * 100, 1)

    @property
    def acciones_pendientes(self):
        return [i for i in self.indicadores if i.accion_correctora and not i.accion_resuelta]


class IndicadorBienestar(Base):
    __tablename__ = "indicadores_bienestar"

    id = Column(Integer, primary_key=True, index=True)
    auditoria_id = Column(Integer, ForeignKey("auditorias_bienestar.id"), nullable=False)
    categoria = Column(String(20), nullable=False)
    indicador = Column(String(300), nullable=False)
    puntuacion = Column(Integer, nullable=True)  # 0-10, vacío = no evaluado
    observaciones = Column(Text, nullable=True)
    accion_correctora = Column(Text, nullable=True)
    fecha_limite_accion = Column(Date, nullable=True)
    accion_resuelta = Column(Boolean, default=False)
    orden = Column(Integer, nullable=False, default=0)

    auditoria = relationship("AuditoriaBienestar", back_populates="indicadores")
