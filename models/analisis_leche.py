from sqlalchemy import Column, Integer, String, Date, Float, Text
from database import Base


class AnalisisLeche(Base):
    __tablename__ = "analisis_leche"

    id = Column(Integer, primary_key=True, index=True)

    numero_informe = Column(String(30), nullable=True)
    numero_recepcion = Column(String(30), nullable=True)
    numero_muestra = Column(String(30), nullable=True)
    descripcion_muestra = Column(String(200), nullable=True)
    producto = Column(String(100), nullable=True)
    laboratorio = Column(String(100), nullable=True, default="LILA Asturias")

    fecha_toma = Column(Date, nullable=False)
    fecha_recepcion = Column(Date, nullable=True)
    fecha_emision_informe = Column(Date, nullable=True)

    bactoscan = Column(Float, nullable=True)            # ufc/ml (x1000)
    celulas_somaticas = Column(Float, nullable=True)    # celulas/ml (x1000)
    crioscopia = Column(Float, nullable=True)           # -m°C
    extracto_seco_magro = Column(Float, nullable=True)  # % m/m
    materia_grasa = Column(Float, nullable=True)        # % m/m
    lactosa = Column(Float, nullable=True)              # % m/m
    proteina = Column(Float, nullable=True)             # % m/m
    urea = Column(Float, nullable=True)                 # mg/l
    inhibidores = Column(String(20), nullable=True)     # Negativo/Positivo

    observaciones = Column(Text, nullable=True)
