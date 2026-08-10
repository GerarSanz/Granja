import io
from pathlib import Path
from PIL import Image
from config import get_settings

MAX_FOTO_BYTES = 15 * 1024 * 1024  # 15 MB


def _foto_path(crotal: str) -> Path:
    return Path(get_settings().UPLOADS_DIR) / "animales" / f"{crotal.upper()}.jpg"


def foto_url(crotal: str) -> str | None:
    path = _foto_path(crotal)
    if not path.exists():
        return None
    # el mtime en la query fuerza al navegador a recargar la imagen cuando se
    # sustituye la foto, ya que la URL de fichero es siempre la misma
    return f"/uploads/animales/{crotal.upper()}.jpg?v={int(path.stat().st_mtime)}"


def guardar_foto(crotal: str, contenido: bytes) -> None:
    path = _foto_path(crotal)
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(io.BytesIO(contenido))
    # Decodifica ya reducida (evita cargar en memoria la foto a resolución
    # completa — las fotos de móvil pueden agotar la RAM del servidor).
    img.draft("RGB", (900, 900))
    img = img.convert("RGB")
    img.thumbnail((900, 900))
    img.save(path, format="JPEG", quality=85)


def eliminar_foto(crotal: str) -> None:
    path = _foto_path(crotal)
    if path.exists():
        path.unlink()
