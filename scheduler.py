from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal
from services.alertas import generar_alertas_diarias
import logging

logger = logging.getLogger(__name__)


def tarea_alertas_diarias():
    db = SessionLocal()
    try:
        alertas = generar_alertas_diarias(db)
        logger.info("Tarea diaria completada: %d alertas", len(alertas))
    except Exception as e:
        logger.error("Error en tarea diaria de alertas: %s", e)
    finally:
        db.close()


def iniciar_scheduler():
    scheduler = BackgroundScheduler(timezone="Europe/Madrid")
    # Ejecutar cada día a las 7:00 hora española
    scheduler.add_job(tarea_alertas_diarias, "cron", hour=7, minute=0)
    scheduler.start()
    logger.info("Scheduler iniciado — alertas diarias a las 07:00")
    return scheduler
