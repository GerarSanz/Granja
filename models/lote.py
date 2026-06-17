from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Lote(Base):
    __tablename__ = "lotes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=True)

    animales = relationship("Animal", back_populates="lote")
    ocupaciones = relationship("OcupacionParcela", back_populates="lote")
    asignaciones_toro = relationship("AsignacionToro", back_populates="lote")


class Parcela(Base):
    __tablename__ = "parcelas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    hectareas = Column(Float, nullable=False)
    referencia_catastral = Column(String(50), nullable=True)
    municipio = Column(String(100), nullable=True)
    observaciones = Column(Text, nullable=True)

    # Referencia SIGPAC
    provincia_codigo = Column(Integer, nullable=True, default=33)  # 33 = Asturias
    municipio_codigo = Column(Integer, nullable=True)
    poligono = Column(Integer, nullable=True)
    parcela_sigpac = Column(Integer, nullable=True)

    ocupaciones = relationship("OcupacionParcela", back_populates="parcela")


class OcupacionParcela(Base):
    __tablename__ = "ocupaciones_parcela"

    id = Column(Integer, primary_key=True, index=True)
    lote_id = Column(Integer, ForeignKey("lotes.id"), nullable=False)
    parcela_id = Column(Integer, ForeignKey("parcelas.id"), nullable=False)
    fecha_entrada = Column(Date, nullable=False)
    fecha_salida = Column(Date, nullable=True)
    observaciones = Column(Text, nullable=True)

    lote = relationship("Lote", back_populates="ocupaciones")
    parcela = relationship("Parcela", back_populates="ocupaciones")


class AsignacionToro(Base):
    __tablename__ = "asignaciones_toro"

    id = Column(Integer, primary_key=True, index=True)
    toro_crotal = Column(String(20), ForeignKey("animales.crotal"), nullable=False)
    lote_id = Column(Integer, ForeignKey("lotes.id"), nullable=False)
    fecha_entrada = Column(Date, nullable=False)
    fecha_salida = Column(Date, nullable=True)
    observaciones = Column(Text, nullable=True)

    lote = relationship("Lote", back_populates="asignaciones_toro")
