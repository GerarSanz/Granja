from pathlib import Path
from config import get_settings


def _pdf_path(analisis_id: int) -> Path:
    return Path(get_settings().UPLOADS_DIR) / "analisis_leche" / f"{analisis_id}.pdf"


def guardar_pdf(analisis_id: int, contenido: bytes) -> None:
    path = _pdf_path(analisis_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contenido)


def pdf_url(analisis_id: int) -> str | None:
    return f"/uploads/analisis_leche/{analisis_id}.pdf" if _pdf_path(analisis_id).exists() else None


def eliminar_pdf(analisis_id: int) -> None:
    path = _pdf_path(analisis_id)
    if path.exists():
        path.unlink()
