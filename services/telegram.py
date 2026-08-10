import httpx
import logging
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


async def enviar_telegram(mensaje: str, chat_id: str = None, token: str = None) -> bool:
    chat_id = chat_id or settings.TELEGRAM_CHAT_ID
    token = token or settings.TELEGRAM_BOT_TOKEN

    if not chat_id or not token:
        logger.warning("Telegram no configurado — mensaje no enviado: %s", mensaje)
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                TELEGRAM_API_URL.format(token=token),
                json={"chat_id": chat_id, "text": mensaje},
            )
            if resp.status_code == 200:
                logger.info("Telegram enviado a %s", chat_id)
                return True
            logger.warning("Telegram error %s: %s", resp.status_code, resp.text)
            return False
    except Exception as e:
        logger.error("Error enviando Telegram: %s", e)
        return False
