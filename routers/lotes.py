from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date, timedelta
import asyncio
import httpx
from database import get_db
from services.ugm import ugm_total
from auth import get_current_user
from models.lote import (Lote, Parcela, OcupacionParcela, AsignacionToro,
                         AbonoParcela, TratamientoParcela,
                         SubParcela, OcupacionSubParcela)
from models.animal import Animal
from models.usuario import Usuario

router = APIRouter(prefix="/lotes", tags=["lotes"])
templates = Jinja2Templates(directory="templates")

# Sugerencias de uso de parcela — se combinan con los valores ya usados en la
# explotación para el autocompletado (campo libre, no una lista cerrada)
USOS_PARCELA_SUGERIDOS = [
    "Pradera / Pasto", "Prado de siega", "Manzanos (pomarada)", "Frutales",
    "Huerta", "Forraje", "Monte / Bosque", "Barbecho / Descanso",
]


def _usos_disponibles(db: Session) -> list[str]:
    usados = {r[0] for r in db.query(Parcela.especie_cultivo).filter(Parcela.especie_cultivo.isnot(None)).distinct().all() if r[0]}
    return sorted(set(USOS_PARCELA_SUGERIDOS) | usados)


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

    # Conteo de animales y UGM por lote
    conteo_lotes = {}
    ugm_lotes = {}
    for lote in lotes:
        animales_lote = db.query(Animal).filter(
            Animal.lote_id == lote.id,
            Animal.fecha_baja.is_(None),
        ).all()
        conteo_lotes[lote.id] = len(animales_lote)
        ugm_lotes[lote.id] = ugm_total(animales_lote, hoy)

    # Densidad UGM/ha de cada parcela con ocupación activa
    hectareas_parcelas = {p.id: p.hectareas for p in parcelas}
    densidad_parcelas = {}
    for oc in ocupaciones_activas:
        hectareas = hectareas_parcelas.get(oc.parcela_id)
        if hectareas:
            densidad_parcelas[oc.parcela_id] = ugm_lotes.get(oc.lote_id, 0) / hectareas

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
        "ugm_lotes": ugm_lotes,
        "densidad_parcelas": densidad_parcelas,
        "animales_sin_lote": animales_sin_lote,
        "toros": toros,
        "hoy": hoy,
        "current_user": current_user,
        "usos_disponibles": _usos_disponibles(db),
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
    return RedirectResponse(url="/lotes?guardado=1", status_code=302)


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
    abonados = db.query(AbonoParcela).filter(
        AbonoParcela.parcela_id == parcela_id
    ).order_by(AbonoParcela.fecha.desc()).all()
    tratamientos_parcela = db.query(TratamientoParcela).filter(
        TratamientoParcela.parcela_id == parcela_id
    ).order_by(TratamientoParcela.fecha.desc()).all()
    subparcelas = db.query(SubParcela).filter(
        SubParcela.parcela_id == parcela_id
    ).order_by(SubParcela.nombre).all()
    lotes = db.query(Lote).order_by(Lote.nombre).all()

    hoy = date.today()
    ocupacion_actual = next((oc for oc in ocupaciones if oc.fecha_salida is None), None)
    animales_ocupantes = []
    ugm_actual = 0.0
    densidad_actual = None
    if ocupacion_actual:
        animales_ocupantes = db.query(Animal).filter(
            Animal.lote_id == ocupacion_actual.lote_id,
            Animal.fecha_baja.is_(None),
        ).all()
        ugm_actual = ugm_total(animales_ocupantes, hoy)
        if parcela.hectareas:
            densidad_actual = ugm_actual / parcela.hectareas

    productos_abono_usados = sorted({r[0] for r in db.query(AbonoParcela.producto).distinct().all() if r[0]})
    productos_trat_usados = sorted({r[0] for r in db.query(TratamientoParcela.producto).distinct().all() if r[0]})
    dosis_trat_usadas = sorted({r[0] for r in db.query(TratamientoParcela.dosis).distinct().all() if r[0]})

    return templates.TemplateResponse("lotes/parcela.html", {
        "request": request,
        "parcela": parcela,
        "ocupaciones": ocupaciones,
        "abonados": abonados,
        "tratamientos_parcela": tratamientos_parcela,
        "subparcelas": subparcelas,
        "lotes": lotes,
        "n_animales_ocupantes": len(animales_ocupantes),
        "ugm_actual": ugm_actual,
        "densidad_actual": densidad_actual,
        "hoy": hoy,
        "timedelta": timedelta,
        "productos_abono_usados": productos_abono_usados,
        "productos_trat_usados": productos_trat_usados,
        "dosis_trat_usadas": dosis_trat_usadas,
        "current_user": current_user,
        "usos_disponibles": _usos_disponibles(db),
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
    especie_cultivo: str = Form(default=""),
    variedad_cultivo: str = Form(default=""),
    regadio: str = Form(default="SEC"),
    tipo_proteccion: str = Form(default="AL"),
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
    p.especie_cultivo = especie_cultivo.strip() or None
    p.variedad_cultivo = variedad_cultivo.strip() or None
    p.regadio = regadio or "SEC"
    p.tipo_proteccion = tipo_proteccion or "AL"
    db.commit()
    return RedirectResponse(url=f"/lotes/parcela/{parcela_id}", status_code=302)


@router.post("/parcela/{parcela_id}/eliminar")
def eliminar_parcela(
    parcela_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    p = db.query(Parcela).filter(Parcela.id == parcela_id).first()
    if not p:
        raise HTTPException(status_code=404)
    db.query(OcupacionParcela).filter(OcupacionParcela.parcela_id == parcela_id).delete()
    db.delete(p)
    db.commit()
    return RedirectResponse(url="/lotes", status_code=302)


@router.get("/parcela/{parcela_id}/sigpac")
async def sigpac_proxy(parcela_id: int, db: Session = Depends(get_db)):
    """Proxy hacia la API SIGPAC para obtener la geometría de la parcela."""
    p = db.query(Parcela).filter(Parcela.id == parcela_id).first()
    if not p or not all([p.provincia_codigo, p.municipio_codigo, p.poligono, p.parcela_sigpac]):
        return JSONResponse({"error": "Referencia SIGPAC incompleta"}, status_code=400)

    # SIGPAC en la Nube — OGC API Features del FEGA.
    # Devuelve GeoJSON (WGS84) con todos los recintos de la parcela.
    params = {
        "provincia": int(p.provincia_codigo),
        "municipio": int(p.municipio_codigo),
        "poligono": int(p.poligono),
        "parcela": int(p.parcela_sigpac),
        "f": "json",
        "limit": 100,
    }
    url = "https://sigpac-hubcloud.es/ogcapi/collections/recintos/items"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(
                url,
                params=params,
                headers={"User-Agent": "GranjaManager/1.0", "Accept": "application/json"},
            )
            if not resp.is_success:
                return JSONResponse(
                    {"error": f"SIGPAC {resp.status_code}: {resp.text[:300]}"},
                    status_code=502,
                )
            content_type = resp.headers.get("content-type", "")
            if "json" not in content_type:
                return JSONResponse(
                    {"error": f"SIGPAC devolvió formato inesperado ({content_type}): {resp.text[:300]}"},
                    status_code=502,
                )
            data = resp.json()
            if not data.get("features"):
                return JSONResponse(
                    {"error": "Parcela no encontrada en SIGPAC. Verifica municipio, polígono y parcela."},
                    status_code=404,
                )
            return JSONResponse(data)
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
    especie_cultivo: str = Form(default=""),
    variedad_cultivo: str = Form(default=""),
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
        especie_cultivo=especie_cultivo.strip() or None,
        variedad_cultivo=variedad_cultivo.strip() or None,
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
    return RedirectResponse(url="/lotes?guardado=1", status_code=302)


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
    return RedirectResponse(url="/lotes?guardado=1", status_code=302)


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


@router.post("/parcela/{parcela_id}/abono/nuevo")
def nuevo_abono(
    parcela_id: int,
    fecha: str = Form(...),
    tipo: str = Form(...),
    producto: str = Form(default=""),
    cantidad: str = Form(default=""),
    unidad: str = Form(default=""),
    superficie_ha: str = Form(default=""),
    es_ecologico: str = Form(default=""),
    observaciones: str = Form(default=""),
    albaran: str = Form(default=""),
    riqueza_npk: str = Form(default=""),
    tipo_fertilizacion: str = Form(default="AF"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    parcela = db.query(Parcela).filter(Parcela.id == parcela_id).first()
    if not parcela:
        return RedirectResponse(url="/lotes", status_code=302)
    db.add(AbonoParcela(
        parcela_id=parcela_id,
        fecha=date.fromisoformat(fecha),
        tipo=tipo,
        producto=producto.strip() or None,
        cantidad=float(cantidad) if cantidad else None,
        unidad=unidad.strip() or None,
        superficie_ha=float(superficie_ha) if superficie_ha else parcela.hectareas,
        es_ecologico=1 if es_ecologico else 0,
        observaciones=observaciones.strip() or None,
        albaran=albaran.strip() or None,
        riqueza_npk=riqueza_npk.strip() or None,
        tipo_fertilizacion=tipo_fertilizacion or "AF",
    ))
    db.commit()
    return RedirectResponse(url=f"/lotes/parcela/{parcela_id}?guardado=1", status_code=302)


@router.post("/parcela/{parcela_id}/abono/{abono_id}/eliminar")
def eliminar_abono(
    parcela_id: int,
    abono_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    a = db.query(AbonoParcela).filter(AbonoParcela.id == abono_id).first()
    if a:
        db.delete(a)
        db.commit()
    return RedirectResponse(url=f"/lotes/parcela/{parcela_id}", status_code=302)


@router.post("/parcela/{parcela_id}/tratamiento/nuevo")
def nuevo_tratamiento_parcela(
    parcela_id: int,
    fecha: str = Form(...),
    tipo: str = Form(...),
    producto: str = Form(...),
    dosis: str = Form(default=""),
    superficie_ha: str = Form(default=""),
    plazo_seguridad_dias: str = Form(default=""),
    es_ecologico: str = Form(default=""),
    observaciones: str = Form(default=""),
    num_registro_fito: str = Form(default=""),
    problema_fitosanitario: str = Form(default=""),
    eficacia: str = Form(default=""),
    aplicador_nombre: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    parcela = db.query(Parcela).filter(Parcela.id == parcela_id).first()
    if not parcela:
        return RedirectResponse(url="/lotes", status_code=302)
    db.add(TratamientoParcela(
        parcela_id=parcela_id,
        fecha=date.fromisoformat(fecha),
        tipo=tipo,
        producto=producto.strip(),
        dosis=dosis.strip() or None,
        superficie_ha=float(superficie_ha) if superficie_ha else parcela.hectareas,
        plazo_seguridad_dias=int(plazo_seguridad_dias) if plazo_seguridad_dias else None,
        es_ecologico=1 if es_ecologico else 0,
        observaciones=observaciones.strip() or None,
        num_registro_fito=num_registro_fito.strip() or None,
        problema_fitosanitario=problema_fitosanitario.strip() or None,
        eficacia=eficacia or None,
        aplicador_nombre=aplicador_nombre.strip() or None,
    ))
    db.commit()
    return RedirectResponse(url=f"/lotes/parcela/{parcela_id}?guardado=1", status_code=302)


@router.post("/parcela/{parcela_id}/tratamiento/{trat_id}/eliminar")
def eliminar_tratamiento_parcela(
    parcela_id: int,
    trat_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    t = db.query(TratamientoParcela).filter(TratamientoParcela.id == trat_id).first()
    if t:
        db.delete(t)
        db.commit()
    return RedirectResponse(url=f"/lotes/parcela/{parcela_id}", status_code=302)


# ── SubParcelas (pastoreo rotacional) ─────────────────────────────────────────

@router.get("/parcela/{parcela_id}/subparcelas.geojson")
def subparcelas_geojson(parcela_id: int, db: Session = Depends(get_db)):
    """GeoJSON FeatureCollection con todas las subparcelas y su ocupación actual."""
    import json
    subparcelas = db.query(SubParcela).filter(SubParcela.parcela_id == parcela_id).all()
    features = []
    for sp in subparcelas:
        oc = sp.ocupacion_actual
        features.append({
            "type": "Feature",
            "id": sp.id,
            "geometry": json.loads(sp.geojson),
            "properties": {
                "id": sp.id,
                "nombre": sp.nombre,
                "uso": sp.uso or "",
                "color": sp.color,
                "lote_id": oc.lote_id if oc else None,
                "lote_actual": oc.lote.nombre if oc else None,
                "desde": oc.fecha_entrada.strftime("%d/%m/%Y") if oc else None,
                "ocupacion_id": oc.id if oc else None,
            }
        })
    return JSONResponse({"type": "FeatureCollection", "features": features})


@router.post("/parcela/{parcela_id}/subparcela/nueva")
async def nueva_subparcela(
    parcela_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    import json
    body = await request.json()
    sp = SubParcela(
        parcela_id=parcela_id,
        nombre=body.get("nombre", "Sin nombre"),
        uso=body.get("uso") or None,
        color=body.get("color", "#198754"),
        geojson=json.dumps(body["geometry"]),
        observaciones=body.get("observaciones") or None,
    )
    db.add(sp)
    db.commit()
    db.refresh(sp)
    return JSONResponse({"id": sp.id, "nombre": sp.nombre, "color": sp.color})


@router.post("/parcela/{parcela_id}/subparcela/{sp_id}/eliminar")
def eliminar_subparcela(
    parcela_id: int,
    sp_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    sp = db.query(SubParcela).filter(SubParcela.id == sp_id).first()
    if sp:
        db.delete(sp)
        db.commit()
    return RedirectResponse(url=f"/lotes/parcela/{parcela_id}", status_code=302)


@router.post("/parcela/{parcela_id}/subparcela/{sp_id}/ocupacion/nueva")
def nueva_ocupacion_subparcela(
    parcela_id: int,
    sp_id: int,
    lote_id: int = Form(...),
    fecha_entrada: str = Form(...),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Cerrar ocupación activa si existe
    activa = db.query(OcupacionSubParcela).filter(
        OcupacionSubParcela.subparcela_id == sp_id,
        OcupacionSubParcela.fecha_salida.is_(None),
    ).first()
    if activa:
        activa.fecha_salida = date.fromisoformat(fecha_entrada)
    db.add(OcupacionSubParcela(
        subparcela_id=sp_id,
        lote_id=lote_id,
        fecha_entrada=date.fromisoformat(fecha_entrada),
        observaciones=observaciones or None,
    ))
    db.commit()
    return RedirectResponse(url=f"/lotes/parcela/{parcela_id}", status_code=302)


@router.post("/parcela/{parcela_id}/subparcela/{sp_id}/ocupacion/cerrar")
def cerrar_ocupacion_subparcela(
    parcela_id: int,
    sp_id: int,
    fecha_salida: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    activa = db.query(OcupacionSubParcela).filter(
        OcupacionSubParcela.subparcela_id == sp_id,
        OcupacionSubParcela.fecha_salida.is_(None),
    ).first()
    if activa:
        activa.fecha_salida = date.fromisoformat(fecha_salida)
        db.commit()
    return RedirectResponse(url=f"/lotes/parcela/{parcela_id}", status_code=302)
