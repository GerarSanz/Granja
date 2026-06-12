from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date
from database import get_db
from auth import get_current_user
from models.animal import Animal
from models.sanidad import Tratamiento, PlanVacunal
from models.usuario import Usuario

router = APIRouter(prefix="/sanidad", tags=["sanidad"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
def lista_sanidad(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()
    tratamientos = db.query(Tratamiento).order_by(Tratamiento.fecha.desc()).limit(50).all()
    plan_vacunal = db.query(PlanVacunal).filter(PlanVacunal.activo == True).order_by(PlanVacunal.proxima_fecha).all()
    animales = db.query(Animal).filter(Animal.fecha_baja.is_(None)).order_by(Animal.crotal).all()

    # Tiempos de espera activos
    en_espera = db.query(Tratamiento).filter(
        Tratamiento.fecha_fin_espera >= hoy,
    ).order_by(Tratamiento.fecha_fin_espera).all()

    return templates.TemplateResponse("sanidad/lista.html", {
        "request": request,
        "tratamientos": tratamientos,
        "plan_vacunal": plan_vacunal,
        "animales": animales,
        "en_espera": en_espera,
        "hoy": hoy,
        "current_user": current_user,
    })


@router.post("/tratamiento/nuevo")
def nuevo_tratamiento(
    animal_crotal: str = Form(...),
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
        animal_crotal=animal_crotal.upper(),
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
    return RedirectResponse(url="/sanidad", status_code=302)


@router.post("/vacuna/nueva")
def nueva_vacuna(
    nombre: str = Form(...),
    vacuna: str = Form(...),
    descripcion: str = Form(default=""),
    periodicidad_meses: str = Form(default=""),
    aplica_a: str = Form(default="todo_rebano"),
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
        proxima_fecha=date.fromisoformat(proxima_fecha) if proxima_fecha else None,
    )
    db.add(pv)
    db.commit()
    return RedirectResponse(url="/sanidad", status_code=302)


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
    return RedirectResponse(url="/sanidad", status_code=302)
