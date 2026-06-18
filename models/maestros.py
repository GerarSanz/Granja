from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Especie(Base):
    __tablename__ = "especies"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, unique=True)
    codigo = Column(String(20), nullable=True)  # bovino, ovino, caprino…

    razas = relationship("Raza", back_populates="especie", cascade="all, delete-orphan")


class Raza(Base):
    __tablename__ = "razas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    especie_id = Column(Integer, ForeignKey("especies.id"), nullable=False)

    especie = relationship("Especie", back_populates="razas")
