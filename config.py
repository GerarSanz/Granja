import os
from functools import lru_cache


class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 días

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./granja.db")

    WHATSAPP_PHONE: str = os.getenv("WHATSAPP_PHONE", "")
    WHATSAPP_APIKEY: str = os.getenv("WHATSAPP_APIKEY", "")

    EXPLOTACION_NOMBRE: str = os.getenv("EXPLOTACION_NOMBRE", "Mi Ganadería")
    EXPLOTACION_REGA: str = os.getenv("EXPLOTACION_REGA", "")

    ALERTA_PREPARTO_DIAS: list[int] = [30, 15, 7]
    ALERTA_STOCK_MINIMO_DIAS: int = 21
    ALERTA_VACIA_DIAS: int = 90

    DIAS_GESTACION_BOVINA: int = 285


@lru_cache
def get_settings() -> Settings:
    return Settings()
