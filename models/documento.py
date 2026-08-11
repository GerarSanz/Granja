from sqlalchemy import Column, Integer, String, Date, DateTime, Text
from sqlalchemy.sql import func
from database import Base
import enum


class TipoDocumento(str, enum.Enum):
    certificado_ecologico = "certificado_ecologico"
    inspeccion = "inspeccion"
    contrato = "contrato"
    seguro = "seguro"
    licencia_permiso = "licencia_permiso"
    otro = "otro"


class Documento(Base):
    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(30), nullable=False, default=TipoDocumento.otro)
    titulo = Column(String(200), nullable=False)
    entidad = Column(String(200), nullable=True)   # organismo emisor o contraparte del contrato
    num_referencia = Column(String(100), nullable=True)  # nº de certificado/contrato/póliza...
    fecha_emision = Column(Date, nullable=True)
    fecha_caducidad = Column(Date, nullable=True)  # None = no caduca
    archivo_nombre = Column(String(255), nullable=True)  # nombre original del archivo subido
    archivo_ext = Column(String(10), nullable=True)      # extensión guardada en disco
    observaciones = Column(Text, nullable=True)
    creado_en = Column(DateTime, server_default=func.now())
