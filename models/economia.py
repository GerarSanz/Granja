from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base
import enum


class TipoVenta(str, enum.Enum):
    ternero_destete = "ternero_destete"
    animal_cebado = "animal_cebado"
    reproductora = "reproductora"
    semental = "semental"
    desvieje = "desvieje"


class CategoriaGasto(str, enum.Enum):
    alimentacion = "alimentacion"
    sanidad = "sanidad"
    maquinaria = "maquinaria"
    instalaciones = "instalaciones"
    mano_obra = "mano_obra"
    seguros = "seguros"
    otros = "otros"


class Venta(Base):
    __tablename__ = "ventas"

    id = Column(Integer, primary_key=True, index=True)
    animal_crotal = Column(String(20), ForeignKey("animales.crotal"), nullable=False)
    fecha = Column(Date, nullable=False)
    tipo_venta = Column(String(30), nullable=False)
    kg_peso = Column(Float, nullable=True)
    precio_kg = Column(Float, nullable=True)
    importe_total = Column(Float, nullable=False)
    comprador = Column(String(200), nullable=True)
    num_factura = Column(String(100), nullable=True)
    observaciones = Column(Text, nullable=True)

    animal = relationship("Animal", back_populates="ventas")


class Gasto(Base):
    __tablename__ = "gastos"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False)
    categoria = Column(String(30), nullable=False)
    concepto = Column(String(200), nullable=False)
    importe = Column(Float, nullable=False)
    proveedor = Column(String(200), nullable=True)
    num_factura = Column(String(100), nullable=True)
    observaciones = Column(Text, nullable=True)
