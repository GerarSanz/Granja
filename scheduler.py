from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database import SessionLocal
from services.alertas import generar_alertas_diarias
from config import get_settings
import logging

logger = logging.getLogger(__name__)

JOB_ID_ALERTAS = "alertas_diarias"
JOB_ID_DEMO = "reset_demo"


def tarea_alertas_diarias():
    db = SessionLocal()
    try:
        alertas = generar_alertas_diarias(db)
        logger.info("Tarea diaria completada: %d alertas", len(alertas))
    except Exception as e:
        logger.error("Error en tarea diaria de alertas: %s", e)
    finally:
        db.close()


def tarea_reset_demo():
    from services.demo_seed import resetear_y_sembrar_demo
    try:
        resetear_y_sembrar_demo()
        logger.info("Demo reiniciada por el scheduler")
    except Exception as e:
        logger.error("Error al reiniciar la demo: %s", e)


def _parse_hora(hora: str) -> tuple[int, int]:
    hh, mm = hora.split(":")
    return int(hh), int(mm)


def iniciar_scheduler(hora: str = "07:00"):
    hh, mm = _parse_hora(hora)
    scheduler = BackgroundScheduler(timezone="Europe/Madrid")
    scheduler.add_job(tarea_alertas_diarias, "cron", hour=hh, minute=mm, id=JOB_ID_ALERTAS)
    if get_settings().DEMO_MODE:
        # Reinicia la demo cada noche a las 04:00, para que quien la pruebe
        # durante el día no deje datos raros para el siguiente visitante.
        scheduler.add_job(tarea_reset_demo, "cron", hour=4, minute=0, id=JOB_ID_DEMO)
        logger.info("DEMO_MODE activo — la demo se reinicia cada noche a las 04:00")
    scheduler.start()
    logger.info("Scheduler iniciado — alertas diarias a las %s", hora)
    return scheduler


def reprogramar_alertas(scheduler, hora: str):
    hh, mm = _parse_hora(hora)
    scheduler.reschedule_job(JOB_ID_ALERTAS, trigger=CronTrigger(hour=hh, minute=mm, timezone="Europe/Madrid"))
    logger.info("Alertas diarias reprogramadas a las %s", hora)
