from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


class TipoCliente(str, enum.Enum):
    particular = "particular"
    tienda = "tienda"
    restaurante = "restaurante"
    distribuidor = "distribuidor"
    otro = "otro"


class TipoInteraccion(str, enum.Enum):
    llamada = "llamada"
    visita = "visita"
    email = "email"
    pedido = "pedido"
    otro = "otro"


class InteraccionCliente(Base):
    __tablename__ = "interacciones_cliente"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    tipo = Column(String(20), nullable=False, default=TipoInteraccion.otro)
    texto = Column(Text, nullable=False)
    creada_en = Column(DateTime, server_default=func.now())

    cliente = relationship("Cliente", back_populates="interacciones")
