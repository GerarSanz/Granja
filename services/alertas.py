from datetime import date, timedelta
from sqlalchemy.orm import Session
from models.animal import Animal, EstadoAnimal
from models.reproduccion import Reproduccion
from models.alimentacion import Alimento, StockMovimiento, TipoMovimientoStock
from models.alerta import Alerta, TipoAlerta, NivelAlerta
from models.tarea import Tarea
from models.queseria import LoteQueso
from models.maquinaria import Maquina, RevisionMaquina
from models.bienestar import IndicadorBienestar
from models.documento import Documento
from models.facturacion import Cliente
from services.telegram import enviar_telegram
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
        # Umbrales de mayor a menor: si el scheduler se salta un día (p.ej. por un
        # reinicio del servidor), al día siguiente se recupera el umbral más urgente
        # todavía pendiente en vez de perder el aviso para siempre.
        umbrales_desc = sorted(settings.ALERTA_PREPARTO_DIAS, reverse=True)
        ya_alertados = db.query(Alerta).filter(
            Alerta.tipo == TipoAlerta.preparto,
            Alerta.animal_crotal == rep.animal_crotal,
            Alerta.fecha_disparo >= rep.fecha_cubricion,
        ).count()
        if ya_alertados < len(umbrales_desc):
            umbral_actual = umbrales_desc[ya_alertados]
            if dias_para_parto <= umbral_actual:
                nivel = NivelAlerta.urgente if umbral_actual <= 7 else NivelAlerta.aviso
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

    # --- Recordatorio de tareas próximas a vencer (a N días vista) ---
    tareas_proximas = db.query(Tarea).filter(
        Tarea.completada == False,
        Tarea.fecha_limite.isnot(None),
        Tarea.fecha_limite >= hoy,
    ).all()

    for t in tareas_proximas:
        dias_restantes = (t.fecha_limite - hoy).days
        # Igual que en preparto: recupera el umbral más urgente pendiente si se
        # saltó algún día, en vez de perder el aviso para siempre.
        umbrales_desc = sorted(settings.ALERTA_TAREA_DIAS, reverse=True)
        ya_alertados = db.query(Alerta).filter(
            Alerta.tipo == TipoAlerta.tarea_proxima,
            Alerta.tarea_id == t.id,
        ).count()
        if ya_alertados < len(umbrales_desc):
            umbral_actual = umbrales_desc[ya_alertados]
            if dias_restantes <= umbral_actual:
                if dias_restantes == 0:
                    plazo = "vence HOY"
                elif dias_restantes == 1:
                    plazo = "vence MAÑANA"
                else:
                    plazo = f"vence en {dias_restantes} dias"
                nivel = NivelAlerta.urgente if t.prioridad == "alta" else NivelAlerta.aviso
                msg = f"TAREA: {t.titulo} — {plazo}"
                alertas_nuevas.append(Alerta(
                    tipo=TipoAlerta.tarea_proxima,
                    nivel=nivel,
                    tarea_id=t.id,
                    mensaje=msg,
                    fecha_disparo=hoy,
                ))

    # --- Tareas vencidas (una sola alerta por tarea, al pasar su fecha límite) ---
    tareas_vencidas = db.query(Tarea).filter(
        Tarea.completada == False,
        Tarea.fecha_limite.isnot(None),
        Tarea.fecha_limite < hoy,
    ).all()

    for t in tareas_vencidas:
        ya_existe = db.query(Alerta).filter(
            Alerta.tipo == TipoAlerta.tarea_vencida,
            Alerta.tarea_id == t.id,
        ).first()
        if not ya_existe:
            dias_vencida = (hoy - t.fecha_limite).days
            nivel = NivelAlerta.urgente if t.prioridad == "alta" else NivelAlerta.aviso
            msg = f"TAREA VENCIDA: {t.titulo} — vencio hace {dias_vencida} dia(s)"
            alertas_nuevas.append(Alerta(
                tipo=TipoAlerta.tarea_vencida,
                nivel=nivel,
                tarea_id=t.id,
                mensaje=msg,
                fecha_disparo=hoy,
            ))

    # --- Lotes de queso listos para vender (curación cumplida, sin marcar todavía) ---
    lotes_en_curacion = db.query(LoteQueso).filter(
        LoteQueso.fecha_listo.is_(None),
        LoteQueso.dias_curacion_objetivo.isnot(None),
    ).all()

    for lote in lotes_en_curacion:
        fecha_estimada = lote.fecha_estimada_lista
        if fecha_estimada and fecha_estimada <= hoy:
            ya_existe = db.query(Alerta).filter(
                Alerta.tipo == TipoAlerta.queso_listo,
                Alerta.lote_queso_id == lote.id,
            ).first()
            if not ya_existe:
                msg = f"QUESO LISTO: el lote {lote.codigo} ha cumplido su curación — {lote.num_piezas_inicial} piezas"
                alertas_nuevas.append(Alerta(
                    tipo=TipoAlerta.queso_listo,
                    nivel=NivelAlerta.aviso,
                    lote_queso_id=lote.id,
                    mensaje=msg,
                    fecha_disparo=hoy,
                ))

    # --- Revisiones de maquinaria próximas / vencidas (según la última revisión
    # con próxima fecha calculada de cada máquina) ---
    maquinas_activas = db.query(Maquina).filter(Maquina.activa == True).all()
    for maquina in maquinas_activas:
        ultima_revision = db.query(RevisionMaquina).filter(
            RevisionMaquina.maquina_id == maquina.id,
            RevisionMaquina.proxima_fecha.isnot(None),
        ).order_by(RevisionMaquina.fecha.desc()).first()
        if not ultima_revision:
            continue
        dias_restantes = (ultima_revision.proxima_fecha - hoy).days

        if dias_restantes < 0:
            ya_existe = db.query(Alerta).filter(
                Alerta.tipo == TipoAlerta.revision_vencida,
                Alerta.maquina_id == maquina.id,
                Alerta.fecha_disparo >= ultima_revision.fecha,
            ).first()
            if not ya_existe:
                msg = f"REVISION VENCIDA: {maquina.nombre} — vencio hace {-dias_restantes} dia(s)"
                alertas_nuevas.append(Alerta(
                    tipo=TipoAlerta.revision_vencida,
                    nivel=NivelAlerta.urgente,
                    maquina_id=maquina.id,
                    mensaje=msg,
                    fecha_disparo=hoy,
                ))
        else:
            umbrales_desc = sorted(settings.ALERTA_REVISION_DIAS, reverse=True)
            ya_alertados = db.query(Alerta).filter(
                Alerta.tipo == TipoAlerta.revision_proxima,
                Alerta.maquina_id == maquina.id,
                Alerta.fecha_disparo >= ultima_revision.fecha,
            ).count()
            if ya_alertados < len(umbrales_desc):
                umbral_actual = umbrales_desc[ya_alertados]
                if dias_restantes <= umbral_actual:
                    nivel = NivelAlerta.urgente if umbral_actual <= 7 else NivelAlerta.aviso
                    msg = f"REVISION en {dias_restantes} dias: {maquina.nombre} ({ultima_revision.tipo_revision})"
                    alertas_nuevas.append(Alerta(
                        tipo=TipoAlerta.revision_proxima,
                        nivel=nivel,
                        maquina_id=maquina.id,
                        mensaje=msg,
                        fecha_disparo=hoy,
                    ))

    # --- Acciones correctoras de bienestar animal vencidas ---
    acciones_pendientes = db.query(IndicadorBienestar).filter(
        IndicadorBienestar.accion_correctora.isnot(None),
        IndicadorBienestar.accion_resuelta == False,
        IndicadorBienestar.fecha_limite_accion.isnot(None),
        IndicadorBienestar.fecha_limite_accion < hoy,
    ).all()

    for ind in acciones_pendientes:
        ya_existe = db.query(Alerta).filter(
            Alerta.tipo == TipoAlerta.bienestar_accion_vencida,
            Alerta.indicador_bienestar_id == ind.id,
        ).first()
        if not ya_existe:
            dias_vencida = (hoy - ind.fecha_limite_accion).days
            msg = f"ACCION BIENESTAR VENCIDA: {ind.indicador} — vencio hace {dias_vencida} dia(s)"
            alertas_nuevas.append(Alerta(
                tipo=TipoAlerta.bienestar_accion_vencida,
                nivel=NivelAlerta.urgente,
                indicador_bienestar_id=ind.id,
                mensaje=msg,
                fecha_disparo=hoy,
            ))

    # --- Documentos próximos a caducar / caducados (certificados, seguros,
    # contratos, licencias...) ---
    documentos_con_caducidad = db.query(Documento).filter(Documento.fecha_caducidad.isnot(None)).all()
    for doc in documentos_con_caducidad:
        dias_restantes = (doc.fecha_caducidad - hoy).days

        if dias_restantes < 0:
            ya_existe = db.query(Alerta).filter(
                Alerta.tipo == TipoAlerta.documento_caducado,
                Alerta.documento_id == doc.id,
                Alerta.fecha_disparo >= doc.fecha_caducidad,
            ).first()
            if not ya_existe:
                msg = f"DOCUMENTO CADUCADO: {doc.titulo} — vencio hace {-dias_restantes} dia(s)"
                alertas_nuevas.append(Alerta(
                    tipo=TipoAlerta.documento_caducado,
                    nivel=NivelAlerta.urgente,
                    documento_id=doc.id,
                    mensaje=msg,
                    fecha_disparo=hoy,
                ))
        else:
            umbrales_desc = sorted(settings.ALERTA_DOCUMENTO_DIAS, reverse=True)
            ya_alertados = db.query(Alerta).filter(
                Alerta.tipo == TipoAlerta.documento_proximo_caducar,
                Alerta.documento_id == doc.id,
                Alerta.fecha_disparo >= (doc.fecha_emision or hoy),
            ).count()
            if ya_alertados < len(umbrales_desc):
                umbral_actual = umbrales_desc[ya_alertados]
                if dias_restantes <= umbral_actual:
                    nivel = NivelAlerta.urgente if umbral_actual <= 15 else NivelAlerta.aviso
                    msg = f"DOCUMENTO caduca en {dias_restantes} dias: {doc.titulo}"
                    alertas_nuevas.append(Alerta(
                        tipo=TipoAlerta.documento_proximo_caducar,
                        nivel=nivel,
                        documento_id=doc.id,
                        mensaje=msg,
                        fecha_disparo=hoy,
                    ))

    # --- Recordatorios de contacto CRM vencidos ---
    clientes_seguimiento = db.query(Cliente).filter(
        Cliente.activo == True,
        Cliente.proximo_contacto_fecha.isnot(None),
        Cliente.proximo_contacto_fecha < hoy,
    ).all()

    for cliente in clientes_seguimiento:
        ya_existe = db.query(Alerta).filter(
            Alerta.tipo == TipoAlerta.crm_contacto_vencido,
            Alerta.cliente_id == cliente.id,
            Alerta.fecha_disparo >= cliente.proximo_contacto_fecha,
        ).first()
        if not ya_existe:
            dias = (hoy - cliente.proximo_contacto_fecha).days
            motivo = cliente.proximo_contacto_motivo or "seguimiento pendiente"
            msg = f"CONTACTO PENDIENTE: {cliente.nombre} — {motivo} (hace {dias} dia(s))"
            alertas_nuevas.append(Alerta(
                tipo=TipoAlerta.crm_contacto_vencido,
                nivel=NivelAlerta.aviso,
                cliente_id=cliente.id,
                mensaje=msg,
                fecha_disparo=hoy,
            ))

    # Guardar alertas y enviar Telegram
    for alerta in alertas_nuevas:
        db.add(alerta)

    db.commit()

    # Enviar Telegram para todas las alertas nuevas (urgentes destacadas)
    for alerta in alertas_nuevas:
        prefijo = "URGENTE" if alerta.nivel == NivelAlerta.urgente else "Aviso"
        asyncio.run(enviar_telegram(f"[GranjaManager] {prefijo}: {alerta.mensaje}"))
        alerta.enviada_telegram = True

    if alertas_nuevas:
        db.commit()

    logger.info("Alertas generadas hoy: %d", len(alertas_nuevas))
    return alertas_nuevas
