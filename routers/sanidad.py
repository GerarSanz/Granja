from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import extract, or_, and_
from datetime import date
from database import get_db
from auth import get_current_user
from models.animal import Animal
from models.lote import Lote
from models.sanidad import Tratamiento, PlanVacunal, Desparasitacion
from models.usuario import Usuario

router = APIRouter(prefix="/sanidad", tags=["sanidad"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def lista_sanidad(
    request: Request,
    trat_anio: int = None,
    trat_animal: str = None,
    trat_orden: str = "fecha_desc",
    desp_anio: int = None,
    lote_id: str = None,
    raza: str = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()
    animales = db.query(Animal).filter(Animal.fecha_baja.is_(None)).order_by(Animal.crotal).all()

    # Tratamientos con filtros — los de "todo el rebaño" o "por lote" se muestran
    # siempre que correspondan, igual que en desparasitaciones
    q = db.query(Tratamiento).outerjoin(Animal, Animal.crotal == Tratamiento.animal_crotal)
    if lote_id or raza:
        condiciones_t = [Tratamiento.aplica_todo_rebano == True]
        condiciones_t_animal = [Tratamiento.animal_crotal.isnot(None)]
        if lote_id == "sin_lote":
            condiciones_t_animal.append(Animal.lote_id.is_(None))
        elif lote_id:
            condiciones_t_animal.append(Animal.lote_id == int(lote_id))
            condiciones_t.append(Tratamiento.lote_id == int(lote_id))
        if raza:
            condiciones_t_animal.append(Animal.raza == raza)
        condiciones_t.append(and_(*condiciones_t_animal))
        q = q.filter(or_(*condiciones_t))
    if trat_anio:
        q = q.filter(extract("year", Tratamiento.fecha) == trat_anio)
    if trat_animal:
        q = q.filter(Tratamiento.animal_crotal == trat_animal.upper())
    if trat_orden == "fecha_asc":
        q = q.order_by(Tratamiento.fecha.asc())
    elif trat_orden == "animal_asc":
        q = q.order_by(Tratamiento.animal_crotal.asc(), Tratamiento.fecha.desc())
    elif trat_orden == "medicamento_asc":
        q = q.order_by(Tratamiento.medicamento.asc())
    else:
        q = q.order_by(Tratamiento.fecha.desc())
    tratamientos = q.all()

    anios_trat = sorted(
        {int(r[0]) for r in db.query(extract("year", Tratamiento.fecha)).distinct().all() if r[0]},
        reverse=True,
    )

    # Desparasitaciones con filtros — las de "todo el rebaño" se muestran siempre,
    # ya que también afectaron a los animales del lote/raza filtrado
    q_d = db.query(Desparasitacion).outerjoin(Animal, Animal.crotal == Desparasitacion.animal_crotal)
    if desp_anio:
        q_d = q_d.filter(extract("year", Desparasitacion.fecha) == desp_anio)
    if lote_id or raza:
        condiciones = [Desparasitacion.aplica_todo_rebano == True]
        # animal_crotal.isnot(None) evita que el outer join con Animal (todo NULL en
        # las filas de "todo el rebaño" o "por lote") cuele como Animal.lote_id.is_(None)
        condiciones_animal = [Desparasitacion.animal_crotal.isnot(None)]
        if lote_id == "sin_lote":
            condiciones_animal.append(Animal.lote_id.is_(None))
        elif lote_id:
            condiciones_animal.append(Animal.lote_id == int(lote_id))
            condiciones.append(Desparasitacion.lote_id == int(lote_id))
        if raza:
            condiciones_animal.append(Animal.raza == raza)
        condiciones.append(and_(*condiciones_animal))
        q_d = q_d.filter(or_(*condiciones))
    desparasitaciones = q_d.order_by(Desparasitacion.fecha.desc()).all()

    anios_desp = sorted(
        {int(r[0]) for r in db.query(extract("year", Desparasitacion.fecha)).distinct().all() if r[0]},
        reverse=True,
    )

    plan_vacunal = db.query(PlanVacunal).filter(PlanVacunal.activo == True).order_by(PlanVacunal.proxima_fecha).all()
    proxima_desp = db.query(Desparasitacion).filter(
        Desparasitacion.proxima_fecha.isnot(None)
    ).order_by(Desparasitacion.proxima_fecha.desc()).first()
    en_espera = db.query(Tratamiento).filter(
        Tratamiento.fecha_fin_espera >= hoy,
    ).order_by(Tratamiento.fecha_fin_espera).all()

    lotes = db.query(Lote).order_by(Lote.nombre).all()
    razas_disponibles = sorted({
        r[0] for r in db.query(Animal.raza).filter(Animal.raza.isnot(None)).distinct().all() if r[0]
    })

    # Valores ya usados, para autocompletar y no tener que retipear cada vez
    medicamentos_usados = sorted({r[0] for r in db.query(Tratamiento.medicamento).distinct().all() if r[0]})
    veterinarios_usados = sorted({r[0] for r in db.query(Tratamiento.veterinario).distinct().all() if r[0]})
    productos_desp_usados = sorted({r[0] for r in db.query(Desparasitacion.producto).distinct().all() if r[0]})

    return templates.TemplateResponse("sanidad/lista.html", {
        "request": request,
        "tratamientos": tratamientos,
        "plan_vacunal": plan_vacunal,
        "animales": animales,
        "en_espera": en_espera,
        "desparasitaciones": desparasitaciones,
        "proxima_desp": proxima_desp,
        "hoy": hoy,
        "current_user": current_user,
        "trat_anio": trat_anio,
        "trat_animal": trat_animal,
        "trat_orden": trat_orden,
        "desp_anio": desp_anio,
        "anios_trat": anios_trat,
        "anios_desp": anios_desp,
        "lotes": lotes,
        "razas_disponibles": razas_disponibles,
        "filtro_lote": lote_id,
        "filtro_raza": raza,
        "medicamentos_usados": medicamentos_usados,
        "veterinarios_usados": veterinarios_usados,
        "productos_desp_usados": productos_desp_usados,
    })


@router.post("/tratamiento/nuevo")
def nuevo_tratamiento(
    ambito: str = Form(default="individual"),
    animal_crotal: str = Form(default=""),
    lote_id: str = Form(default=""),
    fecha: str = Form(...),
    medicamento: str = Form(...),
    principio_activo: str = Form(default=""),
    dosis: str = Form(default=""),
    via_administracion: str = Form(default=""),
    dias_tiempo_espera: str = Form(default="0"),
    veterinario: str = Form(default=""),
    num_receta: str = Form(default=""),
    es_ecologico: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    fecha_d = date.fromisoformat(fecha)
    dias_espera = int(dias_tiempo_espera) if dias_tiempo_espera else 0
    from datetime import timedelta
    fecha_fin = fecha_d + timedelta(days=dias_espera) if dias_espera > 0 else None

    t = Tratamiento(
        animal_crotal=animal_crotal.upper() if ambito == "individual" and animal_crotal else None,
        aplica_todo_rebano=(ambito == "todo_rebano"),
        lote_id=int(lote_id) if ambito == "lote" and lote_id else None,
        fecha=fecha_d,
        medicamento=medicamento,
        principio_activo=principio_activo or None,
        dosis=dosis or None,
        via_administracion=via_administracion or None,
        dias_tiempo_espera=dias_espera,
        fecha_fin_espera=fecha_fin,
        veterinario=veterinario or None,
        num_receta=num_receta or None,
        es_ecologico=bool(es_ecologico),
        observaciones=observaciones or None,
    )
    db.add(t)
    db.commit()
    return RedirectResponse(url="/sanidad?guardado=1", status_code=302)


@router.post("/vacuna/nueva")
def nueva_vacuna(
    nombre: str = Form(...),
    vacuna: str = Form(...),
    descripcion: str = Form(default=""),
    periodicidad_meses: str = Form(default=""),
    aplica_a: str = Form(default="todo_rebano"),
    lote_id: str = Form(default=""),
    proxima_fecha: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    pv = PlanVacunal(
        nombre=nombre,
        vacuna=vacuna,
        descripcion=descripcion or None,
        periodicidad_meses=int(periodicidad_meses) if periodicidad_meses else None,
        aplica_a=aplica_a,
        lote_id=int(lote_id) if aplica_a == "por_lote" and lote_id else None,
        proxima_fecha=date.fromisoformat(proxima_fecha) if proxima_fecha else None,
    )
    db.add(pv)
    db.commit()
    return RedirectResponse(url="/sanidad?guardado=1", status_code=302)


@router.post("/vacuna/{vacuna_id}/completar")
def completar_vacuna(
    vacuna_id: int,
    fecha_realizada: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    from datetime import timedelta
    from dateutil.relativedelta import relativedelta
    pv = db.query(PlanVacunal).filter(PlanVacunal.id == vacuna_id).first()
    if pv:
        pv.ultima_fecha = date.fromisoformat(fecha_realizada)
        if pv.periodicidad_meses:
            try:
                pv.proxima_fecha = pv.ultima_fecha + relativedelta(months=pv.periodicidad_meses)
            except Exception:
                pv.proxima_fecha = pv.ultima_fecha + timedelta(days=pv.periodicidad_meses * 30)
        db.commit()
    return RedirectResponse(url="/sanidad?guardado=1", status_code=302)


@router.post("/desparasitacion/nueva")
def nueva_desparasitacion(
    fecha: str = Form(...),
    producto: str = Form(...),
    principio_activo: str = Form(default=""),
    dosis: str = Form(default=""),
    via_administracion: str = Form(default=""),
    ambito: str = Form(default="todo_rebano"),
    animal_crotal: str = Form(default=""),
    lote_id: str = Form(default=""),
    periodicidad_meses: str = Form(default=""),
    proxima_fecha: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    from dateutil.relativedelta import relativedelta
    fecha_d = date.fromisoformat(fecha)
    periodo = int(periodicidad_meses) if periodicidad_meses else None

    if proxima_fecha:
        prox = date.fromisoformat(proxima_fecha)
    elif periodo:
        prox = fecha_d + relativedelta(months=periodo)
    else:
        prox = None

    d = Desparasitacion(
        fecha=fecha_d,
        producto=producto,
        principio_activo=principio_activo or None,
        dosis=dosis or None,
        via_administracion=via_administracion or None,
        aplica_todo_rebano=(ambito == "todo_rebano"),
        animal_crotal=animal_crotal.upper() if ambito == "individual" and animal_crotal else None,
        lote_id=int(lote_id) if ambito == "lote" and lote_id else None,
        periodicidad_meses=periodo,
        proxima_fecha=prox,
        observaciones=observaciones or None,
    )
    db.add(d)
    db.commit()
    return RedirectResponse(url="/sanidad?guardado=1", status_code=302)


@router.post("/tratamiento/{trat_id}/editar")
def editar_tratamiento(
    trat_id: int,
    ambito: str = Form(default="individual"),
    animal_crotal: str = Form(default=""),
    lote_id: str = Form(default=""),
    fecha: str = Form(...),
    medicamento: str = Form(...),
    principio_activo: str = Form(default=""),
    dosis: str = Form(default=""),
    via_administracion: str = Form(default=""),
    dias_tiempo_espera: str = Form(default="0"),
    veterinario: str = Form(default=""),
    num_receta: str = Form(default=""),
    es_ecologico: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    from datetime import timedelta
    t = db.query(Tratamiento).filter(Tratamiento.id == trat_id).first()
    if not t:
        raise HTTPException(status_code=404)
    fecha_d = date.fromisoformat(fecha)
    dias_espera = int(dias_tiempo_espera) if dias_tiempo_espera else 0
    fecha_fin = fecha_d + timedelta(days=dias_espera) if dias_espera > 0 else None
    t.animal_crotal = animal_crotal.upper() if ambito == "individual" and animal_crotal else None
    t.aplica_todo_rebano = (ambito == "todo_rebano")
    t.lote_id = int(lote_id) if ambito == "lote" and lote_id else None
    t.fecha = fecha_d
    t.medicamento = medicamento
    t.principio_activo = principio_activo or None
    t.dosis = dosis or None
    t.via_administracion = via_administracion or None
    t.dias_tiempo_espera = dias_espera
    t.fecha_fin_espera = fecha_fin
    t.veterinario = veterinario or None
    t.num_receta = num_receta or None
    t.es_ecologico = bool(es_ecologico)
    t.observaciones = observaciones or None
    db.commit()
    return RedirectResponse(url="/sanidad?guardado=1", status_code=302)


@router.post("/tratamiento/{trat_id}/eliminar")
def eliminar_tratamiento(
    trat_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    t = db.query(Tratamiento).filter(Tratamiento.id == trat_id).first()
    if t:
        db.delete(t)
        db.commit()
    return RedirectResponse(url="/sanidad", status_code=302)


@router.post("/desparasitacion/{desp_id}/editar")
def editar_desparasitacion(
    desp_id: int,
    fecha: str = Form(...),
    producto: str = Form(...),
    principio_activo: str = Form(default=""),
    dosis: str = Form(default=""),
    via_administracion: str = Form(default=""),
    ambito: str = Form(default="todo_rebano"),
    animal_crotal: str = Form(default=""),
    lote_id: str = Form(default=""),
    periodicidad_meses: str = Form(default=""),
    proxima_fecha: str = Form(default=""),
    observaciones: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    from dateutil.relativedelta import relativedelta
    d = db.query(Desparasitacion).filter(Desparasitacion.id == desp_id).first()
    if not d:
        raise HTTPException(status_code=404)
    fecha_d = date.fromisoformat(fecha)
    periodo = int(periodicidad_meses) if periodicidad_meses else None
    if proxima_fecha:
        prox = date.fromisoformat(proxima_fecha)
    elif periodo:
        prox = fecha_d + relativedelta(months=periodo)
    else:
        prox = None
    d.fecha = fecha_d
    d.producto = producto
    d.principio_activo = principio_activo or None
    d.dosis = dosis or None
    d.via_administracion = via_administracion or None
    d.aplica_todo_rebano = (ambito == "todo_rebano")
    d.animal_crotal = animal_crotal.upper() if ambito == "individual" and animal_crotal else None
    d.lote_id = int(lote_id) if ambito == "lote" and lote_id else None
    d.periodicidad_meses = periodo
    d.proxima_fecha = prox
    d.observaciones = observaciones or None
    db.commit()
    return RedirectResponse(url="/sanidad?guardado=1", status_code=302)


@router.post("/desparasitacion/{desp_id}/eliminar")
def eliminar_desparasitacion(
    desp_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    d = db.query(Desparasitacion).filter(Desparasitacion.id == desp_id).first()
    if d:
        db.delete(d)
        db.commit()
    return RedirectResponse(url="/sanidad", status_code=302)


@router.post("/vacuna/{vacuna_id}/editar")
def editar_vacuna(
    vacuna_id: int,
    nombre: str = Form(...),
    vacuna: str = Form(...),
    aplica_a: str = Form(default="todo_rebano"),
    lote_id: str = Form(default=""),
    periodicidad_meses: str = Form(default=""),
    proxima_fecha: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    pv = db.query(PlanVacunal).filter(PlanVacunal.id == vacuna_id).first()
    if not pv:
        raise HTTPException(status_code=404)
    pv.nombre = nombre
    pv.vacuna = vacuna
    pv.aplica_a = aplica_a
    pv.lote_id = int(lote_id) if aplica_a == "por_lote" and lote_id else None
    pv.periodicidad_meses = int(periodicidad_meses) if periodicidad_meses else None
    if proxima_fecha:
        pv.proxima_fecha = date.fromisoformat(proxima_fecha)
    db.commit()
    return RedirectResponse(url="/sanidad?guardado=1", status_code=302)


@router.post("/vacuna/{vacuna_id}/eliminar")
def eliminar_vacuna(
    vacuna_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    pv = db.query(PlanVacunal).filter(PlanVacunal.id == vacuna_id).first()
    if pv:
        db.delete(pv)
        db.commit()
    return RedirectResponse(url="/sanidad", status_code=302)
