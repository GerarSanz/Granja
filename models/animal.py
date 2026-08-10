from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base
import enum


class SexoAnimal(str, enum.Enum):
    macho = "macho"
    hembra = "hembra"


class EstadoAnimal(str, enum.Enum):
    gestante = "gestante"
    lactante = "lactante"
    vacia = "vacia"
    semental = "semental"
    ternero = "ternero"
    recria = "recria"
    vendido = "vendido"
    muerto = "muerto"
    baja = "baja"


class Animal(Base):
    __tablename__ = "animales"

    crotal = Column(String(20), primary_key=True, index=True)
    nombre = Column(String(100), nullable=True)
    sexo = Column(String(10), nullable=False)
    fecha_nacimiento = Column(Date, nullable=True)
    madre_crotal = Column(String(20), ForeignKey("animales.crotal"), nullable=True)
    padre_crotal = Column(String(20), ForeignKey("animales.crotal"), nullable=True)
    lote_id = Column(Integer, ForeignKey("lotes.id"), nullable=True)
    especie_id = Column(Integer, ForeignKey("especies.id"), nullable=True)
    estado = Column(String(20), nullable=False, default=EstadoAnimal.vacia)
    raza = Column(String(100), default="Asturiana de la Montaña")
    peso_entrada = Column(Float, nullable=True)
    fecha_alta = Column(Date, nullable=True)
    fecha_baja = Column(Date, nullable=True)
    motivo_baja = Column(String(200), nullable=True)
    observaciones = Column(Text, nullable=True)

    lote = relationship("Lote", back_populates="animales")
    especie = relationship("Especie")
    reproducciones = relationship(
        "Reproduccion",
        foreign_keys="Reproduccion.animal_crotal",
        back_populates="animal",
    )
    tratamientos = relationship("Tratamiento", back_populates="animal")
    desparasitaciones = relationship("Desparasitacion", back_populates="animal")
    ventas = relationship("Venta", back_populates="animal")

    @property
    def display_name(self):
        return self.nombre or self.crotal

    @property
    def es_reproductora(self):
        return self.sexo == SexoAnimal.hembra and self.estado not in [
            EstadoAnimal.vendido, EstadoAnimal.muerto, EstadoAnimal.baja, EstadoAnimal.ternero
        ]
