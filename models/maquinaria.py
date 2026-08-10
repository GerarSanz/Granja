from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base


class Maquina(Base):
    __tablename__ = "maquinas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    tipo = Column(String(100), nullable=True)  # tractor, remolque, segadora, ordeñadora, otro...
    marca = Column(String(100), nullable=True)
    modelo = Column(String(100), nullable=True)
    matricula = Column(String(30), nullable=True)
    num_serie = Column(String(100), nullable=True)
    fecha_compra = Column(Date, nullable=True)
    activa = Column(Boolean, default=True)
    observaciones = Column(Text, nullable=True)

    revisiones = relationship("RevisionMaquina", back_populates="maquina", cascade="all, delete-orphan")


class RevisionMaquina(Base):
    __tablename__ = "revisiones_maquina"

    id = Column(Integer, primary_key=True, index=True)
    maquina_id = Column(Integer, ForeignKey("maquinas.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    tipo_revision = Column(String(150), nullable=False)  # Revisión periódica, ITV, Cambio de aceite, Avería...
    taller = Column(String(200), nullable=True)
    coste = Column(Float, nullable=True)
    horas_km = Column(Float, nullable=True)  # lectura de horómetro o km en el momento de la revisión
    descripcion = Column(Text, nullable=True)  # trabajo realizado
    num_factura = Column(String(100), nullable=True)
    periodicidad_meses = Column(Integer, nullable=True)
    proxima_fecha = Column(Date, nullable=True)
    observaciones = Column(Text, nullable=True)

    maquina = relationship("Maquina", back_populates="revisiones")
