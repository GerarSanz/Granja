from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date
import asyncio
import httpx
from database import get_db


def _resolver_ip_google(hostname: str) -> str:
    """Resuelve hostname usando DNS de Google, saltando el DNS de Fly.io."""
    import dns.resolver as dns_r
    r = dns_r.Resolver(configure=False)
    r.nameservers = ["8.8.8.8", "1.1.1.1"]
    r.lifetime = 5.0
    return str(r.resolve(hostname, "A")[0])
from auth import get_current_user
from models.lote import Lote, Parcela, OcupacionParcela, AsignacionToro
from models.animal import Animal
from models.usuario import Usuario

router = APIRouter(prefix="/lotes", tags=["lotes"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def lista_lotes(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()
    lotes = db.query(Lote).all()
    parcelas = db.query(Parcela).all()

    # Ocupación actual por lote
    ocupaciones_activas = db.query(OcupacionParcela).filter(
        OcupacionParcela.fecha_salida.is_(None)
    ).all()

    # Toros actualmente en lotes
    toros_activos = db.query(AsignacionToro).filter(
        AsignacionToro.fecha_salida.is_(None)
    ).all()

    # Conteo de animales por lote
    conteo_lotes = {}
    for lote in lotes:
        conteo_lotes[lote.id] = db.query(Animal).filter(
            Animal.lote_id == lote.id,
            Animal.fecha_baja.is_(None),
        ).count()

    animales_sin_lote = db.query(Animal).filter(
        Animal.lote_id.is_(None),
        Animal.fecha_baja.is_(None),
    ).all()

    toros = db.query(Animal).filter(
        Animal.sexo == "macho",
        Animal.fecha_baja.is_(None),
    ).all()

    return templates.TemplateResponse("lotes/lista.html", {
        "request": request,
        "lotes": lotes,
        "parcelas": parcelas,
        "ocupaciones_activas": ocupaciones_activas,
        "toros_activos": toros_activos,
        "conteo_lotes": conteo_lotes,
        "animales_sin_lote": animales_sin_lote,
        "toros": toros,
        "hoy": hoy,
        "current_user": current_user,
    })


@router.post("/nuevo")
def crear_lote(
    nombre: str = Form(...),
    descripcion: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lote = Lote(nombre=nombre, descripcion=descripcion or None)
    db.add(lote)
    db.commit()
    return RedirectResponse(url="/lotes", status_code=302)


@router.get("/parcela/{parcela_id}", response_class=HTMLResponse)
def detalle_parcela(
    parcela_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    parcela = db.query(Parcela).filter(Parcela.id == parcela_id).first()
    if not parcela:
        return RedirectResponse(url="/lotes")
    ocupaciones = db.query(OcupacionParcela).filter(
        OcupacionParcela.parcela_id == parcela_id
    ).order_by(OcupacionParcela.fecha_entrada.desc()).all()
    return templates.TemplateResponse("lotes/parcela.html", {
        "request": request,
        "parcela": parcela,
        "ocupaciones": ocupaciones,
        "current_user": current_user,
    })


@router.post("/parcela/{parcela_id}/editar")
def editar_parcela(
    parcela_id: int,
    nombre: str = Form(...),
    hectareas: float = Form(...),
    municipio: str = Form(default=""),
    referencia_catastral: str = Form(default=""),
    provincia_codigo: str = Form(default="33"),
    municipio_codigo: str = Form(default=""),
    poligono: str = Form(default=""),
    parcela_sigpac: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    p = db.query(Parcela).filter(Parcela.id == parcela_id).first()
    if not p:
        return RedirectResponse(url="/lotes")
    p.nombre = nombre
    p.hectareas = hectareas
    p.municipio = municipio or None
    p.referencia_catastral = referencia_catastral or None
    p.provincia_codigo = int(provincia_codigo) if provincia_codigo else 33
    p.municipio_codigo = int(municipio_codigo) if municipio_codigo else None
    p.poligono = int(poligono) if poligono else None
    p.parcela_sigpac = int(parcela_sigpac) if parcela_sigpac else None
    p.observaciones = observaciones or None
    db.commit()
    return RedirectResponse(url=f"/lotes/parcela/{parcela_id}", status_code=302)


@router.get("/parcela/{parcela_id}/sigpac")
async def sigpac_proxy(parcela_id: int, db: Session = Depends(get_db)):
    """Proxy hacia la API SIGPAC para obtener la geometría de la parcela."""
    p = db.query(Parcela).filter(Parcela.id == parcela_id).first()
    if not p or not all([p.provincia_codigo, p.municipio_codigo, p.poligono, p.parcela_sigpac]):
        return JSONResponse({"error": "Referencia SIGPAC incompleta"}, status_code=400)

    prov = str(p.provincia_codigo)
    mun = str(p.municipio_codigo)
    pol = str(p.poligono)
    par = str(p.parcela_sigpac)

    hostname = "sigpac.mapa.gob.es"
    path = f"/fega/ServiciosVisorSigpac/query/recintos/{prov}/{mun}/0/0/{pol}/{par}.geojson"
    try:
        # DNS con Google para saltarse el bloqueo del servidor Fly.io en París
        ip = await asyncio.to_thread(_resolver_ip_google, hostname)
        async with httpx.AsyncClient(
            verify=False, timeout=15,
            headers={"Host": hostname, "User-Agent": "GranjaManager/1.0"},
        ) as client:
            resp = await client.get(f"https://{ip}{path}")
            resp.raise_for_status()
            return JSONResponse(resp.json())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@router.post("/parcela/nueva")
def crear_parcela(
    nombre: str = Form(...),
    hectareas: float = Form(...),
    referencia_catastral: str = Form(default=""),
    municipio: str = Form(default=""),
    provincia_codigo: str = Form(default="33"),
    municipio_codigo: str = Form(default=""),
    poligono: str = Form(default=""),
    parcela_sigpac: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    p = Parcela(
        nombre=nombre,
        hectareas=hectareas,
        referencia_catastral=referencia_catastral or None,
        municipio=municipio or None,
        provincia_codigo=int(provincia_codigo) if provincia_codigo else 33,
        municipio_codigo=int(municipio_codigo) if municipio_codigo else None,
        poligono=int(poligono) if poligono else None,
        parcela_sigpac=int(parcela_sigpac) if parcela_sigpac else None,
    )
    db.add(p)
    db.commit()
    return RedirectResponse(url="/lotes", status_code=302)


@router.post("/ocupacion/nueva")
def nueva_ocupacion(
    lote_id: int = Form(...),
    parcela_id: int = Form(...),
    fecha_entrada: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Cerrar ocupación anterior del lote en otra parcela si existe
    prev = db.query(OcupacionParcela).filter(
        OcupacionParcela.lote_id == lote_id,
        OcupacionParcela.fecha_salida.is_(None),
    ).first()
    if prev:
        prev.fecha_salida = date.fromisoformat(fecha_entrada)

    oc = OcupacionParcela(
        lote_id=lote_id,
        parcela_id=parcela_id,
        fecha_entrada=date.fromisoformat(fecha_entrada),
    )
    db.add(oc)
    db.commit()
    return RedirectResponse(url="/lotes", status_code=302)


@router.post("/toro/asignar")
def asignar_toro(
    toro_crotal: str = Form(...),
    lote_id: int = Form(...),
    fecha_entrada: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Cerrar asignación anterior del toro si existe
    prev = db.query(AsignacionToro).filter(
        AsignacionToro.toro_crotal == toro_crotal.upper(),
        AsignacionToro.fecha_salida.is_(None),
    ).first()
    if prev:
        prev.fecha_salida = date.fromisoformat(fecha_entrada)

    at = AsignacionToro(
        toro_crotal=toro_crotal.upper(),
        lote_id=lote_id,
        fecha_entrada=date.fromisoformat(fecha_entrada),
    )
    db.add(at)
    db.commit()
    return RedirectResponse(url="/lotes", status_code=302)


@router.post("/toro/{asignacion_id}/retirar")
def retirar_toro(
    asignacion_id: int,
    fecha_salida: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    at = db.query(AsignacionToro).filter(AsignacionToro.id == asignacion_id).first()
    if at:
        at.fecha_salida = date.fromisoformat(fecha_salida)
        db.commit()
    return RedirectResponse(url="/lotes", status_code=302)
