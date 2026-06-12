from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base
import enum


class TipoAlimento(str, enum.Enum):
    heno_propio = "heno_propio"
    heno_comprado = "heno_comprado"
    concentrado = "concentrado"
    corrector_mineral = "corrector_mineral"
    paja = "paja"
    ensilado = "ensilado"


class TipoMovimientoStock(str, enum.Enum):
    entrada = "entrada"
    consumo = "consumo"
    perdida = "perdida"
    ajuste = "ajuste"


class EstadoProductivo(str, enum.Enum):
    gestante = "gestante"
    lactante = "lactante"
    vacia = "vacia"
    semental = "semental"
    ternero_lactante = "ternero_lactante"
    ternero_destete = "ternero_destete"


class Alimento(Base):
    __tablename__ = "alimentos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    tipo = Column(String(30), nullable=False)
    es_ecologico = Column(Boolean, default=False)
    unidad = Column(String(20), default="kg")
    descripcion = Column(Text, nullable=True)
    activo = Column(Boolean, default=True)

    raciones = relationship("RacionTipo", back_populates="alimento")
    movimientos = relationship("StockMovimiento", back_populates="alimento")
    compras = relationship("CompraAlimento", back_populates="alimento")


class RacionTipo(Base):
    __tablename__ = "raciones_tipo"

    id = Column(Integer, primary_key=True, index=True)
    estado_productivo = Column(String(30), nullable=False)
    alimento_id = Column(Integer, ForeignKey("alimentos.id"), nullable=False)
    kg_por_animal_dia = Column(Float, nullable=False)
    observaciones = Column(Text, nullable=True)

    alimento = relationship("Alimento", back_populates="raciones")


class StockMovimiento(Base):
    __tablename__ = "stock_movimientos"

    id = Column(Integer, primary_key=True, index=True)
    alimento_id = Column(Integer, ForeignKey("alimentos.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    tipo_movimiento = Column(String(20), nullable=False)
    cantidad_kg = Column(Float, nullable=False)
    lote_id = Column(Integer, ForeignKey("lotes.id"), nullable=True)
    observaciones = Column(Text, nullable=True)

    alimento = relationship("Alimento", back_populates="movimientos")


class CompraAlimento(Base):
    __tablename__ = "compras_alimento"

    id = Column(Integer, primary_key=True, index=True)
    alimento_id = Column(Integer, ForeignKey("alimentos.id"), nullable=False)
    proveedor = Column(String(200), nullable=False)
    fecha = Column(Date, nullable=False)
    cantidad_kg = Column(Float, nullable=False)
    precio_total = Column(Float, nullable=False)
    num_factura = Column(String(100), nullable=True)
    certificado_eco = Column(String(200), nullable=True)
    observaciones = Column(Text, nullable=True)

    alimento = relationship("Alimento", back_populates="compras")
