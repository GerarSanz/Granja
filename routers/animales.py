from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import date
from urllib.parse import urlencode
from database import get_db
from auth import get_current_user
from models.animal import Animal, EstadoAnimal, SexoAnimal
from models.lote import Lote
from models.maestros import Raza, Especie
from services.importacion import parsear_excel, parsear_csv, generar_plantilla_excel
from services.especies import CRIA_LABEL
from services.animal_foto import foto_url, guardar_foto, eliminar_foto, MAX_FOTO_BYTES
from models.reproduccion import Reproduccion
from models.sanidad import Desparasitacion
from models.usuario import Usuario

router = APIRouter(prefix="/animales", tags=["animales"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def lista_animales(
    request: Request,
    estado: str = None,
    sexo: str = None,
    lote_id: str = None,
    especie_id: str = None,
    buscar: str = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    q = db.query(Animal).filter(Animal.fecha_baja.is_(None))
    if estado:
        q = q.filter(Animal.estado == estado)
    if sexo:
        q = q.filter(Animal.sexo == sexo)
    if lote_id == "sin_lote":
        q = q.filter(Animal.lote_id.is_(None))
    elif lote_id:
        q = q.filter(Animal.lote_id == int(lote_id))
    if especie_id:
        q = q.filter(Animal.especie_id == int(especie_id))
    if buscar:
        q = q.filter(or_(Animal.crotal.contains(buscar), Animal.nombre.contains(buscar)))
    animales = q.order_by(Animal.crotal).all()
    lotes = db.query(Lote).all()
    especies = db.query(Especie).order_by(Especie.nombre).all()
    return templates.TemplateResponse("animales/lista.html", {
        "request": request,
        "animales": animales,
        "lotes": lotes,
        "especies": especies,
        "estados": EstadoAnimal,
        "filtro_estado": estado,
        "filtro_sexo": sexo,
        "filtro_lote": lote_id,
        "filtro_especie": especie_id,
        "buscar": buscar,
        "cria_label": CRIA_LABEL,
        "current_user": current_user,
    })


@router.post("/mover-lote")
def mover_lote(
    crotales: list[str] = Form(default=[]),
    lote_id: str = Form(default=""),
    f_buscar: str = Form(default=""),
    f_estado: str = Form(default=""),
    f_sexo: str = Form(default=""),
    f_lote: str = Form(default=""),
    f_especie: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if crotales:
        nuevo_lote_id = int(lote_id) if lote_id else None
        animales = db.query(Animal).filter(Animal.crotal.in_([c.upper() for c in crotales])).all()
        for a in animales:
            a.lote_id = nuevo_lote_id
        db.commit()

    params = {}
    if f_buscar:
        params["buscar"] = f_buscar
    if f_estado:
        params["estado"] = f_estado
    if f_sexo:
        params["sexo"] = f_sexo
    if f_lote:
        params["lote_id"] = f_lote
    if f_especie:
        params["especie_id"] = f_especie
    url = f"/animales?{urlencode(params)}" if params else "/animales"
    return RedirectResponse(url=url, status_code=302)


@router.get("/nuevo", response_class=HTMLResponse)
def nuevo_animal_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lotes = db.query(Lote).all()
    hembras = db.query(Animal).filter(Animal.sexo == SexoAnimal.hembra, Animal.fecha_baja.is_(None)).all()
    machos = db.query(Animal).filter(Animal.sexo == SexoAnimal.macho, Animal.fecha_baja.is_(None)).all()
    especies = db.query(Especie).order_by(Especie.nombre).all()
    return templates.TemplateResponse("animales/form.html", {
        "request": request,
        "animal": None,
        "lotes": lotes,
        "hembras": hembras,
        "machos": machos,
        "estados": EstadoAnimal,
        "especies": especies,
        "current_user": current_user,
    })


@router.post("/nuevo")
def crear_animal(
    request: Request,
    crotal: str = Form(...),
    nombre: str = Form(default=""),
    sexo: str = Form(...),
    raza_id: str = Form(default=""),
    fecha_nacimiento: str = Form(default=""),
    madre_crotal: str = Form(default=""),
    padre_crotal: str = Form(default=""),
    lote_id: str = Form(default=""),
    estado: str = Form(...),
    peso_entrada: str = Form(default=""),
    fecha_alta: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if db.query(Animal).filter(Animal.crotal == crotal).first():
        lotes = db.query(Lote).all()
        return templates.TemplateResponse("animales/form.html", {
            "request": request, "animal": None, "lotes": lotes,
            "error": f"El crotal {crotal} ya existe", "current_user": current_user,
            "estados": EstadoAnimal,
        }, status_code=400)

    raza_obj = db.query(Raza).filter(Raza.id == int(raza_id)).first() if raza_id else None

    animal = Animal(
        crotal=crotal.strip().upper(),
        nombre=nombre.strip() or None,
        sexo=sexo,
        raza=raza_obj.nombre if raza_obj else "Asturiana de la Montaña",
        especie_id=raza_obj.especie_id if raza_obj else None,
        fecha_nacimiento=date.fromisoformat(fecha_nacimiento) if fecha_nacimiento else None,
        madre_crotal=madre_crotal.strip().upper() or None,
        padre_crotal=padre_crotal.strip().upper() or None,
        lote_id=int(lote_id) if lote_id else None,
        estado=estado,
        peso_entrada=float(peso_entrada) if peso_entrada else None,
        fecha_alta=date.fromisoformat(fecha_alta) if fecha_alta else date.today(),
        observaciones=observaciones.strip() or None,
    )
    db.add(animal)
    db.commit()
    return RedirectResponse(url=f"/animales/{animal.crotal}?guardado=1", status_code=302)


# ── Importación masiva ────────────────────────────────────────────────────────
# IMPORTANTE: estos endpoints deben ir ANTES de /{crotal} para que FastAPI
# no interprete "importar" como un valor de crotal.

# Guarda el fichero subido en el preview para que la confirmación no obligue
# a volver a seleccionarlo — se guarda por usuario y se descarta al confirmar.
_import_cache: dict[int, tuple[str, bytes]] = {}

@router.get("/importar/plantilla")
def descargar_plantilla(current_user: Usuario = Depends(get_current_user)):
    contenido = generar_plantilla_excel()
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_animales.xlsx"},
    )


@router.get("/importar", response_class=HTMLResponse)
def importar_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    lotes = db.query(Lote).all()
    return templates.TemplateResponse("animales/importar.html", {
        "request": request,
        "lotes": lotes,
        "current_user": current_user,
        "preview": None,
    })


@router.post("/importar/preview", response_class=HTMLResponse)
async def importar_preview(
    request: Request,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    contenido = await archivo.read()
    nombre = archivo.filename.lower()

    if nombre.endswith(".xlsx") or nombre.endswith(".xls"):
        filas = parsear_excel(contenido)
    elif nombre.endswith(".csv"):
        filas = parsear_csv(contenido)
    else:
        lotes = db.query(Lote).all()
        return templates.TemplateResponse("animales/importar.html", {
            "request": request, "lotes": lotes, "current_user": current_user,
            "error": "Formato no soportado. Usa .xlsx o .csv",
            "preview": None,
        })

    # Marcar duplicados
    crotales_existentes = {a.crotal for a in db.query(Animal.crotal).all()}
    for f in filas:
        if f.crotal in crotales_existentes:
            f.errores.append(f"El crotal {f.crotal} ya existe en la base de datos")

    _import_cache[current_user.id] = (archivo.filename, contenido)

    lotes = db.query(Lote).all()
    return templates.TemplateResponse("animales/importar.html", {
        "request": request,
        "lotes": lotes,
        "current_user": current_user,
        "preview": filas,
        "archivo_nombre": archivo.filename,
        "total": len(filas),
        "validas": sum(1 for f in filas if f.valida),
        "con_errores": sum(1 for f in filas if not f.valida),
    })


@router.post("/importar/confirmar")
def importar_confirmar(
    request: Request,
    lote_defecto_id: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    cached = _import_cache.pop(current_user.id, None)
    if not cached:
        lotes = db.query(Lote).all()
        return templates.TemplateResponse("animales/importar.html", {
            "request": request, "lotes": lotes, "current_user": current_user,
            "error": "El fichero ya no está disponible (o ha pasado demasiado tiempo) — vuelve a subirlo.",
            "preview": None,
        })
    nombre_archivo, contenido = cached
    nombre = nombre_archivo.lower()

    if nombre.endswith(".xlsx") or nombre.endswith(".xls"):
        filas = parsear_excel(contenido)
    else:
        filas = parsear_csv(contenido)

    lote_id_defecto = int(lote_defecto_id) if lote_defecto_id else None
    lotes_por_nombre = {l.nombre.lower(): l.id for l in db.query(Lote).all()}
    crotales_existentes = {a.crotal for a in db.query(Animal.crotal).all()}

    importados = 0
    errores = []

    for f in filas:
        if not f.valida:
            errores.append(f"Fila {f.fila}: {'; '.join(f.errores)}")
            continue
        if f.crotal in crotales_existentes:
            errores.append(f"Fila {f.fila}: {f.crotal} ya existe — omitido")
            continue

        lote_id = lotes_por_nombre.get(f.lote.lower()) if f.lote else lote_id_defecto

        animal = Animal(
            crotal=f.crotal,
            nombre=f.nombre or None,
            sexo=f.sexo,
            fecha_nacimiento=f.fecha_nacimiento,
            estado=f.estado,
            madre_crotal=f.madre_crotal or None,
            padre_crotal=f.padre_crotal or None,
            lote_id=lote_id,
            raza=f.raza or "Asturiana de la Montaña",
            peso_entrada=f.peso_entrada,
            fecha_alta=f.fecha_alta or date.today(),
            observaciones=f.observaciones or None,
        )
        db.add(animal)
        crotales_existentes.add(f.crotal)
        importados += 1

    db.commit()

    lotes = db.query(Lote).all()
    return templates.TemplateResponse("animales/importar.html", {
        "request": request,
        "lotes": lotes,
        "current_user": current_user,
        "preview": None,
        "resultado": {"importados": importados, "errores": errores},
    })


# ── Ficha y acciones por crotal ───────────────────────────────────────────────

@router.get("/{crotal}", response_class=HTMLResponse)
def ficha_animal(
    crotal: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    animal = db.query(Animal).filter(Animal.crotal == crotal.upper()).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal no encontrado")
    reproducciones = db.query(Reproduccion).filter(
        Reproduccion.animal_crotal == crotal.upper()
    ).order_by(Reproduccion.fecha_cubricion.desc()).all()
    lotes = db.query(Lote).all()
    especies = db.query(Especie).order_by(Especie.nombre).all()

    tratamientos_animal = sorted(animal.tratamientos, key=lambda t: t.fecha, reverse=True)
    desparasitaciones_rebano = db.query(Desparasitacion).filter(Desparasitacion.aplica_todo_rebano == True).all()
    desparasitaciones_animal = sorted(
        list(animal.desparasitaciones) + desparasitaciones_rebano,
        key=lambda d: d.fecha, reverse=True,
    )

    return templates.TemplateResponse("animales/ficha.html", {
        "request": request,
        "animal": animal,
        "reproducciones": reproducciones,
        "lotes": lotes,
        "especies": especies,
        "cria_label": CRIA_LABEL,
        "foto_url": foto_url(animal.crotal),
        "tratamientos_animal": tratamientos_animal,
        "desparasitaciones_animal": desparasitaciones_animal,
        "hoy": date.today(),
        "current_user": current_user,
    })


@router.post("/{crotal}/foto")
async def subir_foto_animal(
    crotal: str,
    foto: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    animal = db.query(Animal).filter(Animal.crotal == crotal.upper()).first()
    if not animal:
        raise HTTPException(status_code=404)
    if not (foto.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")
    contenido = await foto.read()
    if len(contenido) > MAX_FOTO_BYTES:
        raise HTTPException(status_code=400, detail="La imagen es demasiado grande (máx. 15 MB)")
    guardar_foto(animal.crotal, contenido)
    return RedirectResponse(url=f"/animales/{crotal}?guardado=1", status_code=302)


@router.post("/{crotal}/foto/eliminar")
def eliminar_foto_animal(
    crotal: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    animal = db.query(Animal).filter(Animal.crotal == crotal.upper()).first()
    if not animal:
        raise HTTPException(status_code=404)
    eliminar_foto(animal.crotal)
    return RedirectResponse(url=f"/animales/{crotal}", status_code=302)


@router.post("/{crotal}/editar")
def editar_animal(
    crotal: str,
    nombre: str = Form(default=""),
    raza_id: str = Form(default=""),
    estado: str = Form(...),
    lote_id: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    animal = db.query(Animal).filter(Animal.crotal == crotal.upper()).first()
    if not animal:
        raise HTTPException(status_code=404)
    animal.nombre = nombre.strip() or animal.nombre
    if raza_id:
        raza_obj = db.query(Raza).filter(Raza.id == int(raza_id)).first()
        if raza_obj:
            animal.raza = raza_obj.nombre
            animal.especie_id = raza_obj.especie_id
    animal.estado = estado
    animal.lote_id = int(lote_id) if lote_id else None
    animal.observaciones = observaciones.strip() or None
    db.commit()
    return RedirectResponse(url=f"/animales/{crotal}?guardado=1", status_code=302)


@router.post("/{crotal}/baja")
def dar_baja(
    crotal: str,
    fecha_baja: str = Form(...),
    tipo_baja: str = Form(...),
    motivo_baja: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    animal = db.query(Animal).filter(Animal.crotal == crotal.upper()).first()
    if not animal:
        raise HTTPException(status_code=404)
    animal.fecha_baja = date.fromisoformat(fecha_baja)
    animal.motivo_baja = motivo_baja
    animal.estado = tipo_baja
    db.commit()
    return RedirectResponse(url="/animales?guardado=1", status_code=302)
