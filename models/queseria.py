from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import timedelta
import enum


class TipoQueso(str, enum.Enum):
    fresco = "fresco"
    tierno = "tierno"
    semicurado = "semicurado"
    curado = "curado"
    afuega_el_pitu = "afuega_el_pitu"
    otro = "otro"


class EtapaQueso(str, enum.Enum):
    cuajado = "cuajado"      # recién hecho el lote, cuajando
    moldeado = "moldeado"    # en molde, desuerando
    curacion = "curacion"    # curando
    listo = "listo"          # peso conocido, disponible para vender


class TipoMovimientoQueso(str, enum.Enum):
    venta = "venta"
    obsequio = "obsequio"
    merma = "merma"
    autoconsumo = "autoconsumo"
    ajuste = "ajuste"


class TurnoOrdeno(str, enum.Enum):
    manana = "manana"
    tarde = "tarde"


class Estanteria(Base):
    __tablename__ = "estanterias"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), nullable=False, unique=True)


class CuajoProducto(Base):
    __tablename__ = "cuajo_productos"

    id = Column(Integer, primary_key=True, index=True)
    marca = Column(String(100), nullable=False, unique=True)
    registro_sanitario = Column(String(100), nullable=True)
    # Último frasco/lote en uso — se autoactualiza al crear/editar un lote de queso,
    # así el siguiente lote con este mismo producto ya viene precargado.
    lote_actual = Column(String(100), nullable=True)
    caducidad_actual = Column(Date, nullable=True)


class LoteQueso(Base):
    __tablename__ = "lotes_queso"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(30), unique=True, nullable=False)  # p.ej. Q2026-001
    fecha_elaboracion = Column(Date, nullable=False)  # día de ordeño/cuajado
    turno_ordeno = Column(String(10), nullable=True)  # manana/tarde — de qué ordeño procede la leche
    litros_leche = Column(Float, nullable=True)
    animales_crotales = Column(Text, nullable=True)  # crotales separados por coma — trazabilidad hasta la vaca
    tipo_queso = Column(String(30), nullable=False, default=TipoQueso.curado)
    num_piezas_inicial = Column(Integer, nullable=True)  # se conoce al moldear, no al cuajar

    etapa = Column(String(20), nullable=False, default=EtapaQueso.cuajado)
    fecha_moldeado = Column(Date, nullable=True)         # pasa a molde / empieza desuerado
    fecha_inicio_curacion = Column(Date, nullable=True)  # empieza a curar (tras desuerado)
    dias_curacion_objetivo = Column(Integer, nullable=True)

    peso_inicial_kg = Column(Float, nullable=True)  # se conoce al pesar (curado: al final de la curación)
    fecha_listo = Column(Date, nullable=True)        # se rellena al marcar "listo para vender" (con el peso ya conocido)

    es_ecologico = Column(Boolean, default=True)
    observaciones = Column(Text, nullable=True)

    # Ubicación física en la cámara de curación
    estanteria = Column(String(50), nullable=True)
    fila = Column(Integer, nullable=True)
    columna = Column(Integer, nullable=True)

    # Trazabilidad del cuajo empleado en este lote
    cuajo_marca = Column(String(100), nullable=True)
    cuajo_registro_sanitario = Column(String(100), nullable=True)
    cuajo_lote = Column(String(100), nullable=True)
    cuajo_caducidad = Column(Date, nullable=True)

    movimientos = relationship("MovimientoQueso", back_populates="lote", cascade="all, delete-orphan")

    @property
    def fecha_estimada_lista(self):
        if self.fecha_inicio_curacion and self.dias_curacion_objetivo:
            return self.fecha_inicio_curacion + timedelta(days=self.dias_curacion_objetivo)
        return None


class MovimientoQueso(Base):
    __tablename__ = "movimientos_queso"

    id = Column(Integer, primary_key=True, index=True)
    lote_id = Column(Integer, ForeignKey("lotes_queso.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    tipo = Column(String(20), nullable=False)  # venta/obsequio/merma/autoconsumo/ajuste
    peso_kg = Column(Float, nullable=False)
    num_piezas = Column(Integer, nullable=True)
    cliente = Column(String(200), nullable=True)  # destino: a quién/dónde va el queso, en cualquier tipo de movimiento
    precio_total = Column(Float, nullable=True)   # solo si hay contraprestación económica (venta)
    num_factura = Column(String(100), nullable=True)
    observaciones = Column(Text, nullable=True)

    lote = relationship("LoteQueso", back_populates="movimientos")
