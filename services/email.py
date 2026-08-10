import smtplib
from email.mime.text import MIMEText
import logging
from config import get_settings

logger = logging.getLogger(__name__)


def enviar_email(destinatario: str, asunto: str, cuerpo: str) -> bool:
    settings = get_settings()
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP no configurado — email no enviado: %s", asunto)
        return False
    if not destinatario:
        return False

    try:
        msg = MIMEText(cuerpo)
        msg["Subject"] = asunto
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = destinatario

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], [destinatario], msg.as_string())
        logger.info("Email enviado a %s", destinatario)
        return True
    except Exception as e:
        logger.error("Error enviando email a %s: %s", destinatario, e)
        return False
