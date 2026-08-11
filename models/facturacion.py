from sqlalchemy import Column, Integer, String, Date, DateTime, Float, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


class EstadoFactura(str, enum.Enum):
    borrador = "borrador"
    emitida = "emitida"
    pagada = "pagada"
    anulada = "anulada"


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False)  # nombre o razón social
    nif = Column(String(20), nullable=True)
    direccion = Column(String(200), nullable=True)
    cp = Column(String(10), nullable=True)
    localidad = Column(String(100), nullable=True)
    provincia = Column(String(100), nullable=True)
    email = Column(String(150), nullable=True)
    telefono = Column(String(30), nullable=True)
    observaciones = Column(Text, nullable=True)

    # Seguimiento CRM (ver models/crm.py) — vive en Cliente para no duplicar
    # la ficha del cliente en dos módulos distintos.
    tipo_cliente = Column(String(20), nullable=True, default="otro")  # particular/tienda/restaurante/distribuidor/otro
    activo = Column(Boolean, default=True)
    proximo_contacto_fecha = Column(Date, nullable=True)
    proximo_contacto_motivo = Column(String(300), nullable=True)

    facturas = relationship("Factura", back_populates="cliente")
    interacciones = relationship("InteraccionCliente", back_populates="cliente",
                                  cascade="all, delete-orphan", order_by="InteraccionCliente.fecha.desc()")


class Factura(Base):
    __tablename__ = "facturas"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(30), nullable=True)  # se asigna solo al EMITIR: "2026/0001"
    anio = Column(Integer, nullable=False)
    fecha_emision = Column(Date, nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    estado = Column(String(20), nullable=False, default=EstadoFactura.borrador)

    base_imponible = Column(Float, nullable=False, default=0)
    total_iva = Column(Float, nullable=False, default=0)
    total_irpf = Column(Float, nullable=False, default=0)
    total = Column(Float, nullable=False, default=0)

    forma_pago = Column(String(50), nullable=True)
    fecha_pago = Column(Date, nullable=True)
    observaciones = Column(Text, nullable=True)

    # Encadenado tipo VERI*FACTU simplificado (ver services/facturacion_hash.py) —
    # da evidencia de que una factura emitida no se ha alterado después, pero
    # NO es una implementación completa del reglamento (sin QR AEAT ni envío
    # en tiempo real).
    hash_actual = Column(String(64), nullable=True)
    hash_anterior = Column(String(64), nullable=True)
    emitida_en = Column(DateTime, nullable=True)
    creada_en = Column(DateTime, server_default=func.now())

    cliente = relationship("Cliente", back_populates="facturas")
    lineas = relationship("LineaFactura", back_populates="factura", cascade="all, delete-orphan",
                           order_by="LineaFactura.orden")


class LineaFactura(Base):
    __tablename__ = "lineas_factura"

    id = Column(Integer, primary_key=True, index=True)
    factura_id = Column(Integer, ForeignKey("facturas.id"), nullable=False)
    concepto = Column(String(300), nullable=False)
    cantidad = Column(Float, nullable=False, default=1)
    precio_unitario = Column(Float, nullable=False, default=0)
    tipo_iva = Column(Float, nullable=False, default=10.0)  # % — 0/4/10/21 típicos
    orden = Column(Integer, nullable=False, default=0)

    factura = relationship("Factura", back_populates="lineas")

    @property
    def importe(self) -> float:
        return round((self.cantidad or 0) * (self.precio_unitario or 0), 2)
