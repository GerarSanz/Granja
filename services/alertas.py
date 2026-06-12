from datetime import date, timedelta
from sqlalchemy.orm import Session
from models.animal import Animal, EstadoAnimal
from models.reproduccion import Reproduccion
from models.alimentacion import Alimento, StockMovimiento, TipoMovimientoStock
from models.alerta import Alerta, TipoAlerta, NivelAlerta
from services.whatsapp import enviar_whatsapp
from config import get_settings
import asyncio
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


def calcular_stock_actual(db: Session, alimento_id: int) -> float:
    movimientos = db.query(StockMovimiento).filter(
        StockMovimiento.alimento_id == alimento_id
    ).all()
    total = 0.0
    for m in movimientos:
        if m.tipo_movimiento == TipoMovimientoStock.entrada:
            total += m.cantidad_kg
        else:
            total -= m.cantidad_kg
    return max(0.0, total)


def calcular_consumo_diario(db: Session, alimento_id: int) -> float:
    from models.alimentacion import RacionTipo
    from models.animal import Animal, EstadoAnimal

    conteo = {
        "gestante": db.query(Animal).filter(Animal.estado == EstadoAnimal.gestante, Animal.fecha_baja.is_(None)).count(),
        "lactante": db.query(Animal).filter(Animal.estado == EstadoAnimal.lactante, Animal.fecha_baja.is_(None)).count(),
        "vacia": db.query(Animal).filter(Animal.estado == EstadoAnimal.vacia, Animal.fecha_baja.is_(None)).count(),
        "semental": db.query(Animal).filter(Animal.estado == EstadoAnimal.semental, Animal.fecha_baja.is_(None)).count(),
        "ternero": db.query(Animal).filter(Animal.estado == EstadoAnimal.ternero, Animal.fecha_baja.is_(None)).count(),
        "recria": db.query(Animal).filter(Animal.estado == EstadoAnimal.recria, Animal.fecha_baja.is_(None)).count(),
    }

    raciones = db.query(RacionTipo).filter(RacionTipo.alimento_id == alimento_id).all()
    total_dia = 0.0
    for r in raciones:
        n = conteo.get(r.estado_productivo, 0)
        total_dia += n * r.kg_por_animal_dia
    return total_dia


def generar_alertas_diarias(db: Session):
    hoy = date.today()
    alertas_nuevas = []

    # --- Alertas de parto próximo ---
    reproducciones_activas = db.query(Reproduccion).filter(
        Reproduccion.parto_fecha.is_(None),
        Reproduccion.fecha_parto_estimada.isnot(None),
    ).all()

    for rep in reproducciones_activas:
        dias_para_parto = (rep.fecha_parto_estimada - hoy).days
        for umbral in settings.ALERTA_PREPARTO_DIAS:
            if dias_para_parto == umbral:
                nivel = NivelAlerta.urgente if umbral <= 7 else NivelAlerta.aviso
                ya_existe = db.query(Alerta).filter(
                    Alerta.tipo == TipoAlerta.preparto,
                    Alerta.animal_crotal == rep.animal_crotal,
                    Alerta.fecha_disparo == hoy,
                ).first()
                if not ya_existe:
                    animal = db.query(Animal).filter(Animal.crotal == rep.animal_crotal).first()
                    nombre = animal.display_name if animal else rep.animal_crotal
                    msg = f"PARTO en {dias_para_parto} dias: {nombre} ({rep.animal_crotal}). Fecha estimada: {rep.fecha_parto_estimada}"
                    alertas_nuevas.append(Alerta(
                        tipo=TipoAlerta.preparto,
                        nivel=nivel,
                        animal_crotal=rep.animal_crotal,
                        mensaje=msg,
                        fecha_disparo=hoy,
                    ))

    # --- Vacías sin cubrir > N días ---
    vacas_vacias = db.query(Animal).filter(
        Animal.sexo == "hembra",
        Animal.estado == EstadoAnimal.vacia,
        Animal.fecha_baja.is_(None),
    ).all()

    for vaca in vacas_vacias:
        ultima_rep = db.query(Reproduccion).filter(
            Reproduccion.animal_crotal == vaca.crotal
        ).order_by(Reproduccion.fecha_cubricion.desc()).first()

        fecha_referencia = ultima_rep.parto_fecha if (ultima_rep and ultima_rep.parto_fecha) else vaca.fecha_alta
        if not fecha_referencia:
            continue
        dias_vacia = (hoy - fecha_referencia).days
        if dias_vacia >= settings.ALERTA_VACIA_DIAS:
            ya_existe = db.query(Alerta).filter(
                Alerta.tipo == TipoAlerta.vacia_sin_cubrir,
                Alerta.animal_crotal == vaca.crotal,
                Alerta.fecha_disparo == hoy,
            ).first()
            if not ya_existe:
                msg = f"VACIA sin cubrir: {vaca.display_name} ({vaca.crotal}) lleva {dias_vacia} dias sin cubricion"
                alertas_nuevas.append(Alerta(
                    tipo=TipoAlerta.vacia_sin_cubrir,
                    nivel=NivelAlerta.aviso,
                    animal_crotal=vaca.crotal,
                    mensaje=msg,
                    fecha_disparo=hoy,
                ))

    # --- Stock bajo de alimentos ---
    alimentos = db.query(Alimento).filter(Alimento.activo == True).all()
    for alimento in alimentos:
        stock_kg = calcular_stock_actual(db, alimento.id)
        consumo_dia = calcular_consumo_diario(db, alimento.id)
        if consumo_dia > 0:
            dias_restantes = stock_kg / consumo_dia
            if dias_restantes < settings.ALERTA_STOCK_MINIMO_DIAS:
                ya_existe = db.query(Alerta).filter(
                    Alerta.tipo == TipoAlerta.stock_bajo,
                    Alerta.mensaje.contains(alimento.nombre),
                    Alerta.fecha_disparo == hoy,
                ).first()
                if not ya_existe:
                    nivel = NivelAlerta.urgente if dias_restantes < 7 else NivelAlerta.aviso
                    msg = f"STOCK BAJO: {alimento.nombre} — quedan {stock_kg:.0f} kg ({dias_restantes:.0f} dias de consumo)"
                    alertas_nuevas.append(Alerta(
                        tipo=TipoAlerta.stock_bajo,
                        nivel=nivel,
                        mensaje=msg,
                        fecha_disparo=hoy,
                    ))

    # Guardar alertas y enviar WhatsApp
    for alerta in alertas_nuevas:
        db.add(alerta)

    db.commit()

    # Enviar WhatsApp para alertas urgentes
    for alerta in alertas_nuevas:
        if alerta.nivel == NivelAlerta.urgente:
            prefijo = "URGENTE" if alerta.nivel == NivelAlerta.urgente else "Aviso"
            asyncio.run(enviar_whatsapp(f"[GranjaManager] {prefijo}: {alerta.mensaje}"))
            alerta.enviada_whatsapp = True

    if alertas_nuevas:
        db.commit()

    logger.info("Alertas generadas hoy: %d", len(alertas_nuevas))
    return alertas_nuevas
