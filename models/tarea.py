from sqlalchemy import Column, Integer, String, Date, Boolean, Text
from database import Base


class Tarea(Base):
    __tablename__ = "tareas"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=True)
    fecha_limite = Column(Date, nullable=True)
    prioridad = Column(String(10), nullable=False, default="media")  # baja, media, alta
    completada = Column(Boolean, default=False)
    fecha_completada = Column(Date, nullable=True)
    es_recurrente = Column(Boolean, default=False)
    periodicidad_dias = Column(Integer, nullable=True)
    fecha_creacion = Column(Date, nullable=False)
