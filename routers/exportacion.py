from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date
import io
from database import get_db
from auth import get_current_user
from models.usuario import Usuario
from services.exportacion import (
    exportar_altas_sitran,
    exportar_bajas_sitran,
    exportar_cuaderno_arca,
    exportar_censo_actual,
)

router = APIRouter(prefix="/exportacion", tags=["exportacion"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def pagina_exportacion(
    request: Request,
    sin_datos: str = Query(default=""),
    current_user: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse("exportacion/index.html", {
        "request": request,
        "current_user": current_user,
        "hoy": date.today().isoformat(),
        "sin_datos": sin_datos,
    })


def _tiene_datos(csv_data: str) -> bool:
    """El CSV siempre lleva cabecera — hay datos si hay más de una línea."""
    return len(csv_data.strip().splitlines()) > 1


def _csv_response(contenido: str, nombre: str) -> StreamingResponse:
    return StreamingResponse(
        io.StringIO(contenido),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/sitran/altas")
def descargar_altas_sitran(
    desde: str = Query(default=""),
    hasta: str = Query(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    csv_data = exportar_altas_sitran(
        db,
        desde=date.fromisoformat(desde) if desde else None,
        hasta=date.fromisoformat(hasta) if hasta else None,
    )
    if not _tiene_datos(csv_data):
        return RedirectResponse(url="/exportacion?sin_datos=altas", status_code=302)
    return _csv_response(csv_data, f"SITRAN_altas_{date.today()}.csv")


@router.get("/sitran/bajas")
def descargar_bajas_sitran(
    desde: str = Query(default=""),
    hasta: str = Query(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    csv_data = exportar_bajas_sitran(
        db,
        desde=date.fromisoformat(desde) if desde else None,
        hasta=date.fromisoformat(hasta) if hasta else None,
    )
    if not _tiene_datos(csv_data):
        return RedirectResponse(url="/exportacion?sin_datos=bajas", status_code=302)
    return _csv_response(csv_data, f"SITRAN_bajas_{date.today()}.csv")


@router.get("/arca/cuaderno")
def descargar_cuaderno_arca(
    desde: str = Query(default=""),
    hasta: str = Query(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    csv_data = exportar_cuaderno_arca(
        db,
        desde=date.fromisoformat(desde) if desde else None,
        hasta=date.fromisoformat(hasta) if hasta else None,
    )
    if not _tiene_datos(csv_data):
        return RedirectResponse(url="/exportacion?sin_datos=cuaderno", status_code=302)
    return _csv_response(csv_data, f"ARCA_cuaderno_{date.today()}.csv")


@router.get("/censo")
def descargar_censo(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    csv_data = exportar_censo_actual(db)
    if not _tiene_datos(csv_data):
        return RedirectResponse(url="/exportacion?sin_datos=censo", status_code=302)
    return _csv_response(csv_data, f"censo_{date.today()}.csv")
