from sqlalchemy import Column, Integer, String, Text
from database import Base


class ConfigExplotacion(Base):
    __tablename__ = "config_explotacion"

    id = Column(Integer, primary_key=True, default=1)
    nombre_razon_social = Column(String(200), nullable=True)
    nif = Column(String(20), nullable=True)
    n_registro_nacional = Column(String(50), nullable=True)
    n_registro_autonomico = Column(String(50), nullable=True)
    direccion = Column(String(200), nullable=True)
    localidad = Column(String(100), nullable=True)
    cp = Column(String(10), nullable=True)
    provincia = Column(String(50), nullable=True)
    telefono_fijo = Column(String(20), nullable=True)
    telefono_movil = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    titular_nombre = Column(String(200), nullable=True)
    titular_nif = Column(String(20), nullable=True)
    asesor_nombre = Column(String(200), nullable=True)
    asesor_nif = Column(String(20), nullable=True)
    asesor_n_identificacion = Column(String(50), nullable=True)
    tipo_explotacion_gip = Column(String(10), nullable=True, default="AE")
    hora_alertas = Column(String(5), nullable=True, default="07:00")  # HH:MM — hora de envío de alertas por Telegram


class AplicadorFito(Base):
    __tablename__ = "aplicadores_fito"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False)
    nif = Column(String(20), nullable=True)
    n_inscripcion_ropo = Column(String(50), nullable=True)
    tipo_carne = Column(String(20), nullable=True)  # basico/cualificado/fumigador/piloto/asesor


class EquipoAplicacion(Base):
    __tablename__ = "equipos_aplicacion"

    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(String(200), nullable=False)
    n_inscripcion_roma = Column(String(50), nullable=True)
    fecha_adquisicion = Column(String(20), nullable=True)
    fecha_ultima_inspeccion = Column(String(20), nullable=True)
