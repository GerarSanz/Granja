from sqlalchemy import Column, Integer, String, Float
from database import Base


class PresupuestoPartida(Base):
    __tablename__ = "presupuesto_partidas"

    id = Column(Integer, primary_key=True, index=True)
    anio = Column(Integer, nullable=False, index=True)
    tipo = Column(String(10), nullable=False)       # ingreso / gasto
    categoria = Column(String(30), nullable=False)  # TipoVenta o CategoriaGasto
    concepto = Column(String(200), nullable=True)   # línea de detalle (solo gastos); None = importe global de la categoría
    importe_previsto = Column(Float, nullable=False, default=0)
