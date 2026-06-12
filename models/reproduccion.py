from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base
import enum


class TipoParto(str, enum.Enum):
    normal = "normal"
    distocico = "distócico"
    aborto = "aborto"
    gemelar = "gemelar"
    mortinato = "mortinato"


class Reproduccion(Base):
    __tablename__ = "reproducciones"

    id = Column(Integer, primary_key=True, index=True)
    animal_crotal = Column(String(20), ForeignKey("animales.crotal"), nullable=False)
    toro_crotal = Column(String(20), ForeignKey("animales.crotal"), nullable=True)

    # Cubrición
    fecha_cubricion = Column(Date, nullable=False)
    fecha_parto_estimada = Column(Date, nullable=True)  # fecha_cubricion + 285 días

    # Parto
    parto_fecha = Column(Date, nullable=True)
    parto_tipo = Column(String(20), nullable=True)
    parto_observaciones = Column(Text, nullable=True)

    # Ternero nacido
    ternero_crotal = Column(String(20), nullable=True)
    ternero_sexo = Column(String(10), nullable=True)
    ternero_peso_nacimiento = Column(Float, nullable=True)
    ternero_vivo = Column(Integer, default=1)  # 1=vivo, 0=muerto al nacer

    # Destete
    destete_fecha = Column(Date, nullable=True)
    destete_peso = Column(Float, nullable=True)
    destete_destino = Column(String(200), nullable=True)

    animal = relationship("Animal", foreign_keys=[animal_crotal], back_populates="reproducciones")
