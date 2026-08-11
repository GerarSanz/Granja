from pathlib import Path
from config import get_settings

EXTENSIONES_PERMITIDAS = {"pdf", "jpg", "jpeg", "png", "docx", "doc", "xlsx", "xls"}


def _dir() -> Path:
    return Path(get_settings().UPLOADS_DIR) / "documentos"


def _path(documento_id: int, ext: str) -> Path:
    return _dir() / f"{documento_id}.{ext}"


def guardar_archivo(documento_id: int, filename: str, contenido: bytes) -> str | None:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in EXTENSIONES_PERMITIDAS:
        return None
    _dir().mkdir(parents=True, exist_ok=True)
    _path(documento_id, ext).write_bytes(contenido)
    return ext


def archivo_url(documento_id: int, ext: str | None) -> str | None:
    if not ext:
        return None
    return f"/uploads/documentos/{documento_id}.{ext}" if _path(documento_id, ext).exists() else None


def eliminar_archivo(documento_id: int, ext: str | None) -> None:
    if not ext:
        return
    path = _path(documento_id, ext)
    if path.exists():
        path.unlink()
