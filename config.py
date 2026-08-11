import os
from functools import lru_cache


class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 días

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./granja.db")

    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "")

    EXPLOTACION_NOMBRE: str = os.getenv("EXPLOTACION_NOMBRE", "Mi Ganadería")
    EXPLOTACION_REGA: str = os.getenv("EXPLOTACION_REGA", "")

    BASE_URL: str = os.getenv("BASE_URL", "https://granja-manager.fly.dev")
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"
    UPLOADS_DIR: str = os.getenv("UPLOADS_DIR", "uploads")
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"

    ALERTA_PREPARTO_DIAS: list[int] = [
        int(d) for d in os.getenv("ALERTA_PREPARTO_DIAS", "30,15,7").split(",") if d.strip()
    ]
    ALERTA_STOCK_MINIMO_DIAS: int = int(os.getenv("ALERTA_STOCK_MINIMO_DIAS", "21"))
    ALERTA_VACIA_DIAS: int = int(os.getenv("ALERTA_VACIA_DIAS", "90"))
    ALERTA_TAREA_DIAS: list[int] = [
        int(d) for d in os.getenv("ALERTA_TAREA_DIAS", "3,1,0").split(",") if d.strip()
    ]
    ALERTA_REVISION_DIAS: list[int] = [
        int(d) for d in os.getenv("ALERTA_REVISION_DIAS", "30,15,7").split(",") if d.strip()
    ]
    ALERTA_DOCUMENTO_DIAS: list[int] = [
        int(d) for d in os.getenv("ALERTA_DOCUMENTO_DIAS", "60,30,15,7").split(",") if d.strip()
    ]

    DIAS_GESTACION_BOVINA: int = 285

    # Módulos opcionales de la instalación. "todos" (por defecto, compatible con
    # instalaciones existentes que no fijan la variable) activa todos los
    # módulos opcionales. Si no, lista separada por comas, p.ej.:
    #   MODULOS=queseria,analisis_leche,maquinaria
    # Animales/Reproducción/Sanidad/Lotes/Tareas son el núcleo y siempre están activos.
    MODULOS_DISPONIBLES = {"queseria", "analisis_leche", "maquinaria", "alimentacion", "economia", "cuaderno", "agroturismo", "facturacion", "rentabilidad", "bienestar", "documentos", "crm"}
    _modulos_env = os.getenv("MODULOS", "todos").strip().lower()
    if _modulos_env in ("", "todos", "all"):
        MODULOS: set[str] = set(MODULOS_DISPONIBLES)
    else:
        MODULOS: set[str] = {m.strip() for m in _modulos_env.split(",") if m.strip()} & MODULOS_DISPONIBLES

    def modulo_activo(self, nombre: str) -> bool:
        return nombre in self.MODULOS


@lru_cache
def get_settings() -> Settings:
    return Settings()
