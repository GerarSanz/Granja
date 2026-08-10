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

    # Cuaderno de explotación: uso agrícola
    especie_cultivo = Column(String(100), nullable=True)    # "Pradera Natural", "Prado"…
    variedad_cultivo = Column(String(100), nullable=True)
    regadio = Column(String(10), nullable=True, default="SEC")   # SEC/ASP/LOC/GRA
    tipo_proteccion = Column(String(10), nullable=True, default="AL")  # AL/M/BP/INV

    # Referencia SIGPAC
    provincia_codigo = Column(Integer, nullable=True, default=33)  # 33 = Asturias
    municipio_codigo = Column(Integer, nullable=True)
    poligono = Column(Integer, nullable=True)
    parcela_sigpac = Column(Integer, nullable=True)

    ocupaciones = relationship("OcupacionParcela", back_populates="parcela")
    abonados = relationship("AbonoParcela", back_populates="parcela", cascade="all, delete-orphan")
    tratamientos = relationship("TratamientoParcela", back_populates="parcela", cascade="all, delete-orphan")
    subparcelas = relationship("SubParcela", back_populates="parcela", cascade="all, delete-orphan")


class SubParcela(Base):
    __tablename__ = "subparcelas"

    id = Column(Integer, primary_key=True, index=True)
    parcela_id = Column(Integer, ForeignKey("parcelas.id"), nullable=False)
    nombre = Column(String(100), nullable=False)
    uso = Column(String(50), nullable=True)   # pastizal, cultivo, bosque, descanso…
    color = Column(String(10), default="#198754")
    geojson = Column(Text, nullable=False)    # GeoJSON geometry del polígono
    observaciones = Column(Text, nullable=True)

    parcela = relationship("Parcela", back_populates="subparcelas")
    ocupaciones = relationship("OcupacionSubParcela", back_populates="subparcela",
                               cascade="all, delete-orphan")

    @property
    def ocupacion_actual(self):
        for oc in self.ocupaciones:
            if oc.fecha_salida is None:
                return oc
        return None


class OcupacionSubParcela(Base):
    __tablename__ = "ocupaciones_subparcela"

    id = Column(Integer, primary_key=True, index=True)
    subparcela_id = Column(Integer, ForeignKey("subparcelas.id"), nullable=False)
    lote_id = Column(Integer, ForeignKey("lotes.id"), nullable=False)
    fecha_entrada = Column(Date, nullable=False)
    fecha_salida = Column(Date, nullable=True)
    observaciones = Column(Text, nullable=True)

    subparcela = relationship("SubParcela", back_populates="ocupaciones")
    lote = relationship("Lote")


class AbonoParcela(Base):
    __tablename__ = "abonos_parcela"

    id = Column(Integer, primary_key=True, index=True)
    parcela_id = Column(Integer, ForeignKey("parcelas.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    tipo = Column(String(50), nullable=False)   # mineral, orgánico, estiércol, purín, compost, verde
    producto = Column(String(200), nullable=True)
    cantidad = Column(Float, nullable=True)
    unidad = Column(String(20), nullable=True)  # kg, t, m3, l
    superficie_ha = Column(Float, nullable=True)
    es_ecologico = Column(Integer, default=1)   # 1=sí, 0=no
    observaciones = Column(Text, nullable=True)
    # Cuaderno de explotación
    albaran = Column(String(50), nullable=True)
    riqueza_npk = Column(String(30), nullable=True)     # e.g., "8-15-15"
    tipo_fertilizacion = Column(String(5), nullable=True, default="AF")  # F/AF/AC

    parcela = relationship("Parcela", back_populates="abonados")


class TratamientoParcela(Base):
    __tablename__ = "tratamientos_parcela"

    id = Column(Integer, primary_key=True, index=True)
    parcela_id = Column(Integer, ForeignKey("parcelas.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    tipo = Column(String(50), nullable=False)   # herbicida, fungicida, insecticida, enmienda, otro
    producto = Column(String(200), nullable=False)
    dosis = Column(String(100), nullable=True)
    superficie_ha = Column(Float, nullable=True)
    plazo_seguridad_dias = Column(Integer, nullable=True)
    es_ecologico = Column(Integer, default=1)
    observaciones = Column(Text, nullable=True)
    # Cuaderno de explotación
    num_registro_fito = Column(String(50), nullable=True)
    problema_fitosanitario = Column(String(200), nullable=True)
    eficacia = Column(String(10), nullable=True)    # buena/regular/mala
    aplicador_nombre = Column(String(200), nullable=True)

    parcela = relationship("Parcela", back_populates="tratamientos")


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
