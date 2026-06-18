from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import date
from database import get_db
from auth import get_current_user
from models.animal import Animal, EstadoAnimal, SexoAnimal
from models.lote import Lote
from models.maestros import Raza, Especie
from services.importacion import parsear_excel, parsear_csv, generar_plantilla_excel
from models.reproduccion import Reproduccion
from models.usuario import Usuario

router = APIRouter(prefix="/animales", tags=["animales"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def lista_animales(
    request: Request,
    estado: str = None,
    sexo: str = None,
    lote_id: int = None,
    buscar: str = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    q = db.query(Animal).filter(Animal.fecha_baja.is_(None))
    if estado:
        q = q.filter(Animal.estado == estado)
    if sexo:
        q = q.filter(Animal.sexo == sexo)
    if lote_id:
        q = q.filter(Animal.lote_id == lote_id)
    if buscar:
        q = q.filter(or_(Animal.crotal.contains(buscar), Animal.nombre.contains(buscar)))
    animales = q.order_by(Animal.crotal).all()
    lotes = db.query(Lote).all()
    return templates.TemplateResponse("animales/lista.html", {
        "request": request,
        "animales": animales,
        "lotes": lotes,
        "estados": EstadoAnimal,
        "filtro_estado": estado,
        "filtro_sexo": sexo,
        "filtro_lote": lote_id,
        "buscar": buscar,
        "current_user": current_user,
    })


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
    raza: str = Form(default="Asturiana de la Montaña"),
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

    animal = Animal(
        crotal=crotal.strip().upper(),
        nombre=nombre.strip() or None,
        sexo=sexo,
        raza=raza.strip() or "Asturiana de la Montaña",
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
    return RedirectResponse(url=f"/animales/{animal.crotal}", status_code=302)


# ── Importación masiva ────────────────────────────────────────────────────────
# IMPORTANTE: estos endpoints deben ir ANTES de /{crotal} para que FastAPI
# no interprete "importar" como un valor de crotal.

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
async def importar_confirmar(
    request: Request,
    archivo: UploadFile = File(...),
    lote_defecto_id: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    contenido = await archivo.read()
    nombre = archivo.filename.lower()

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
    return templates.TemplateResponse("animales/ficha.html", {
        "request": request,
        "animal": animal,
        "reproducciones": reproducciones,
        "lotes": lotes,
        "especies": especies,
        "current_user": current_user,
    })


@router.post("/{crotal}/editar")
def editar_animal(
    crotal: str,
    nombre: str = Form(default=""),
    raza: str = Form(default=""),
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
    animal.raza = raza.strip() or animal.raza
    animal.estado = estado
    animal.lote_id = int(lote_id) if lote_id else None
    animal.observaciones = observaciones.strip() or None
    db.commit()
    return RedirectResponse(url=f"/animales/{crotal}", status_code=302)


@router.post("/{crotal}/baja")
def dar_baja(
    crotal: str,
    fecha_baja: str = Form(...),
    motivo_baja: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    animal = db.query(Animal).filter(Animal.crotal == crotal.upper()).first()
    if not animal:
        raise HTTPException(status_code=404)
    animal.fecha_baja = date.fromisoformat(fecha_baja)
    animal.motivo_baja = motivo_baja
    animal.estado = EstadoAnimal.vendido if "venta" in motivo_baja.lower() else EstadoAnimal.baja
    db.commit()
    return RedirectResponse(url="/animales", status_code=302)
