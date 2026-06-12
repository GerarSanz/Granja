import httpx
import logging
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

CALLMEBOT_URL = "https://api.callmebot.com/whatsapp.php"


async def enviar_whatsapp(mensaje: str, phone: str = None, apikey: str = None) -> bool:
    phone = phone or settings.WHATSAPP_PHONE
    apikey = apikey or settings.WHATSAPP_APIKEY

    if not phone or not apikey:
        logger.warning("WhatsApp no configurado — mensaje no enviado: %s", mensaje)
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                CALLMEBOT_URL,
                params={"phone": phone, "text": mensaje, "apikey": apikey},
            )
            if resp.status_code == 200:
                logger.info("WhatsApp enviado a %s", phone)
                return True
            logger.warning("CallMeBot error %s: %s", resp.status_code, resp.text)
            return False
    except Exception as e:
        logger.error("Error enviando WhatsApp: %s", e)
        return False
