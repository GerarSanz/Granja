from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
from database import Base
import enum


class TipoAlerta(str, enum.Enum):
    preparto = "preparto"
    vacia_sin_cubrir = "vacia_sin_cubrir"
    destete_pendiente = "destete_pendiente"
    vacuna_vencida = "vacuna_vencida"
    tiempo_espera = "tiempo_espera"
    stock_bajo = "stock_bajo"


class NivelAlerta(str, enum.Enum):
    info = "info"
    aviso = "aviso"
    urgente = "urgente"


class Alerta(Base):
    __tablename__ = "alertas"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(30), nullable=False)
    nivel = Column(String(20), default=NivelAlerta.aviso)
    animal_crotal = Column(String(20), ForeignKey("animales.crotal"), nullable=True)
    mensaje = Column(Text, nullable=False)
    fecha_disparo = Column(Date, nullable=False)
    leida = Column(Boolean, default=False)
    enviada_whatsapp = Column(Boolean, default=False)
    creada_en = Column(DateTime, server_default=func.now())
