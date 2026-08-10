"""Reinicia la base de datos de una instancia DEMO y la rellena con datos de
ejemplo ficticios (ninguno son datos reales de un cliente). Pensado para
correr una vez al aprovisionar la demo y, si DEMO_MODE=true, cada noche vía
el scheduler (ver scheduler.py) para que quede siempre "limpia" de lo que
haya tocado quien la esté probando.

Las referencias SIGPAC de las parcelas son reales (verificadas contra la API
pública de SIGPAC, https://sigpac-hubcloud.es) para que el visor de mapa
funcione de verdad en la demo, no solo con datos inventados.
"""
import logging
from datetime import date, timedelta

from database import SessionLocal
# Registra TODOS los modelos en el mapper de SQLAlchemy antes de tocar la BD —
# necesario cuando este módulo se ejecuta solo (p.ej. `python -m services.demo_seed`
# por SSH), ya que si no, relationships como Animal.especie ("Especie") fallan
# al no estar esa clase registrada todavía.
from models import (animal, reproduccion, lote, sanidad, alimentacion, economia,
                     alerta, usuario, maestros, cuaderno, tarea, presupuesto,
                     queseria, analisis_leche, maquinaria, agroturismo)
from models.usuario import Usuario, RolUsuario
from models.lote import (Lote, Parcela, OcupacionParcela, AsignacionToro,
                          AbonoParcela, TratamientoParcela, SubParcela, OcupacionSubParcela)
from models.animal import Animal, EstadoAnimal, SexoAnimal
from models.reproduccion import Reproduccion
from models.sanidad import Tratamiento, Desparasitacion, PlanVacunal
from models.maquinaria import Maquina, RevisionMaquina
from models.analisis_leche import AnalisisLeche
from models.queseria import CuajoProducto, Estanteria, LoteQueso, MovimientoQueso, TipoQueso, EtapaQueso
from models.economia import Venta, Gasto, TipoVenta, CategoriaGasto
from models.alimentacion import Alimento, StockMovimiento, RacionTipo, CompraAlimento
from models.tarea import Tarea
from models.alerta import Alerta
from models.cuaderno import ConfigExplotacion
from models.presupuesto import PresupuestoPartida
from models.agroturismo import ActividadTurismo, ReservaTurismo, EstadoReserva
from auth import hash_password

logger = logging.getLogger(__name__)

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo1234"


def _limpiar(db):
    """Borra todos los datos de la explotación (no toca especies/razas maestras)."""
    for modelo in [
        Alerta, MovimientoQueso, LoteQueso, CuajoProducto, Estanteria,
        AnalisisLeche, RevisionMaquina, Maquina,
        Tratamiento, Desparasitacion, PlanVacunal,
        Venta, Gasto, CompraAlimento, StockMovimiento, RacionTipo, Alimento,
        ReservaTurismo, ActividadTurismo,
        Tarea, Reproduccion, PresupuestoPartida, ConfigExplotacion,
        OcupacionSubParcela, SubParcela, AbonoParcela, TratamientoParcela,
        OcupacionParcela, AsignacionToro,
        Animal, Parcela, Lote, Usuario,
    ]:
        db.query(modelo).delete()
    db.commit()


def _sembrar(db):
    hoy = date.today()

    admin = Usuario(
        nombre="Demo",
        username=DEMO_USERNAME,
        password_hash=hash_password(DEMO_PASSWORD),
        rol=RolUsuario.admin,
    )
    db.add(admin)

    # --- Configuración de la explotación (Cuaderno de explotación) ---
    db.add(ConfigExplotacion(
        id=1, nombre_razon_social="Explotación Demo, S.L.", nif="B12345678",
        n_registro_nacional="ES330000000001", n_registro_autonomico="AS-33-000001",
        direccion="Camino de La Pomarada, s/n", localidad="Llanera", cp="33420",
        provincia="Asturias", telefono_fijo="985000000", telefono_movil="600000000",
        email="demo@granjamanager.com", titular_nombre="Explotación Demo, S.L.",
        titular_nif="B12345678", tipo_explotacion_gip="AE", hora_alertas="07:00",
    ))

    # --- Lotes y parcelas ---
    lote_produccion = Lote(nombre="Vacas en producción", descripcion="Lactantes y gestantes")
    lote_recria = Lote(nombre="Recría")
    lote_secado = Lote(nombre="Secado")
    db.add_all([lote_produccion, lote_recria, lote_secado])
    db.flush()

    # Referencias SIGPAC reales (provincia 33 = Asturias, municipio 900 = Llanera,
    # polígono 6 — verificadas vía la API pública de SIGPAC) para que el botón
    # "Ver en mapa" funcione de verdad en la demo.
    p_prado = Parcela(nombre="Prado Grande", hectareas=3.5, municipio="Llanera",
                       especie_cultivo="Pradera / Pasto",
                       provincia_codigo=33, municipio_codigo=900, poligono=6, parcela_sigpac=106)
    p_pomarada = Parcela(nombre="La Pomarada", hectareas=0.8, municipio="Llanera",
                          especie_cultivo="Manzanos (pomarada)", variedad_cultivo="De la Riega",
                          provincia_codigo=33, municipio_codigo=900, poligono=6, parcela_sigpac=111)
    p_siega = Parcela(nombre="Prado del Río", hectareas=2.1, municipio="Llanera",
                       especie_cultivo="Prado de siega",
                       provincia_codigo=33, municipio_codigo=900, poligono=6, parcela_sigpac=134)
    p_monte = Parcela(nombre="Monte Alto", hectareas=5.0, municipio="Llanera",
                       especie_cultivo="Monte / Bosque",
                       observaciones="Sin referencia SIGPAC todavía — pendiente de localizar")
    db.add_all([p_prado, p_pomarada, p_siega, p_monte])
    db.flush()

    db.add(OcupacionParcela(lote_id=lote_produccion.id, parcela_id=p_prado.id,
                             fecha_entrada=hoy - timedelta(days=20)))
    db.add(OcupacionParcela(lote_id=lote_recria.id, parcela_id=p_siega.id,
                             fecha_entrada=hoy - timedelta(days=8)))

    # --- Animales ---
    animales_datos = [
        ("ES330000101", "Luna", "hembra", EstadoAnimal.lactante, lote_produccion.id, "Asturiana de la Montaña", 900),
        ("ES330000102", "Estrella", "hembra", EstadoAnimal.gestante, lote_produccion.id, "Asturiana de la Montaña", 780),
        ("ES330000103", "Paloma", "hembra", EstadoAnimal.vacia, lote_produccion.id, "Frisona", 1600),
        ("ES330000104", "Cariñosa", "hembra", EstadoAnimal.lactante, lote_produccion.id, "Frisona", 1450),
        ("ES330000105", "Reina", "hembra", EstadoAnimal.gestante, lote_secado.id, "Asturiana de la Montaña", 820),
        ("ES330000106", "Nube", "hembra", EstadoAnimal.lactante, lote_produccion.id, "Asturiana de la Montaña", 870),
        ("ES330000107", None, "hembra", EstadoAnimal.recria, lote_recria.id, "Asturiana de la Montaña", 320),
        ("ES330000108", None, "hembra", EstadoAnimal.recria, lote_recria.id, "Frisona", 340),
        ("ES330000109", None, "hembra", EstadoAnimal.ternero, lote_recria.id, "Asturiana de la Montaña", 60),
        ("ES330000110", None, "macho", EstadoAnimal.ternero, lote_recria.id, "Asturiana de la Montaña", 65),
        ("ES330000111", "Pepe", "macho", EstadoAnimal.semental, None, "Asturiana de la Montaña", 1100),
        ("ES330000112", "Marquesa", "hembra", EstadoAnimal.vendido, None, "Frisona", 1550),
    ]
    for crotal, nombre, sexo, estado, lote_id, raza, peso in animales_datos:
        es_baja = estado in (EstadoAnimal.vendido, EstadoAnimal.muerto, EstadoAnimal.baja)
        a = Animal(
            crotal=crotal, nombre=nombre, sexo=sexo, estado=estado, lote_id=lote_id,
            raza=raza, peso_entrada=peso,
            fecha_nacimiento=hoy - timedelta(days=365 * 4),
            fecha_alta=hoy - timedelta(days=365 * 3),
            fecha_baja=hoy - timedelta(days=45) if es_baja else None,
            motivo_baja="Venta — Matadero Comarcal" if es_baja else None,
        )
        db.add(a)
    db.flush()

    # --- Reproducción ---
    db.add(Reproduccion(
        animal_crotal="ES330000102", toro_crotal="ES330000111",
        fecha_cubricion=hoy - timedelta(days=200),
        fecha_parto_estimada=hoy + timedelta(days=85),
    ))
    db.add(Reproduccion(
        animal_crotal="ES330000105", toro_crotal="ES330000111",
        fecha_cubricion=hoy - timedelta(days=260),
        fecha_parto_estimada=hoy + timedelta(days=25),
    ))
    db.add(Reproduccion(
        animal_crotal="ES330000101", toro_crotal="ES330000111",
        fecha_cubricion=hoy - timedelta(days=400),
        fecha_parto_estimada=hoy - timedelta(days=115),
        parto_fecha=hoy - timedelta(days=115), parto_tipo="normal",
        ternero_crotal="ES330000109", ternero_sexo="hembra", ternero_peso_nacimiento=38,
    ))
    db.add(Reproduccion(
        animal_crotal="ES330000106", toro_crotal="ES330000111",
        fecha_cubricion=hoy - timedelta(days=395),
        fecha_parto_estimada=hoy - timedelta(days=110),
        parto_fecha=hoy - timedelta(days=110), parto_tipo="normal",
        ternero_crotal="ES330000110", ternero_sexo="macho", ternero_peso_nacimiento=41,
    ))

    # --- Sanidad: se muestran los 3 ámbitos posibles (todo el rebaño / por
    #     lote / individual) tanto en tratamientos como en desparasitaciones ---
    db.add(Tratamiento(
        animal_crotal="ES330000104", fecha=hoy - timedelta(days=10),
        medicamento="Mastilyt", dosis="1 jeringa intramamaria", via_administracion="intramamario",
        dias_tiempo_espera=5, fecha_fin_espera=hoy - timedelta(days=5),
        veterinario="Clínica Veterinaria Llanera", es_ecologico=False,
        observaciones="Mastitis leve cuarto trasero izquierdo",
    ))
    db.add(Tratamiento(
        aplica_todo_rebano=True, fecha=hoy - timedelta(days=45),
        medicamento="Corrector mineral inyectable", via_administracion="inyectable SC",
        dias_tiempo_espera=0, veterinario="Clínica Veterinaria Llanera", es_ecologico=True,
        observaciones="Suplementación de todo el rebaño tras análisis de sangre",
    ))
    db.add(Tratamiento(
        lote_id=lote_recria.id, fecha=hoy - timedelta(days=30),
        medicamento="Antiinflamatorio Metacam", via_administracion="inyectable SC",
        dias_tiempo_espera=15, fecha_fin_espera=hoy - timedelta(days=15),
        veterinario="Clínica Veterinaria Llanera",
        observaciones="Brote respiratorio leve en el lote de recría",
    ))
    db.add(Desparasitacion(
        fecha=hoy - timedelta(days=60), producto="Ivomec", principio_activo="Ivermectina",
        aplica_todo_rebano=True, periodicidad_meses=6, proxima_fecha=hoy + timedelta(days=120),
    ))
    db.add(Desparasitacion(
        fecha=hoy - timedelta(days=15), producto="Dectomax", principio_activo="Doramectina",
        aplica_todo_rebano=False, lote_id=lote_recria.id,
        periodicidad_meses=4, proxima_fecha=hoy + timedelta(days=105),
        observaciones="Solo recría, tras detectar carga parasitaria alta",
    ))
    db.add(Desparasitacion(
        fecha=hoy - timedelta(days=5), producto="Albendazol", principio_activo="Albendazol",
        aplica_todo_rebano=False, animal_crotal="ES330000111",
        observaciones="Solo el semental, antes de la cubrición",
    ))
    db.add(PlanVacunal(
        nombre="Vacunación IBR/BVD", vacuna="Bovilis IBR", periodicidad_meses=12,
        aplica_a="por_lote", lote_id=lote_produccion.id,
        proxima_fecha=hoy + timedelta(days=25),
    ))
    db.add(PlanVacunal(
        nombre="Clostridiosis terneros", vacuna="Covexin 10", periodicidad_meses=6,
        aplica_a="terneros", proxima_fecha=hoy + timedelta(days=200),
    ))
    db.add(PlanVacunal(
        nombre="Vacunación anual rebaño", vacuna="Rispoval", periodicidad_meses=12,
        aplica_a="todo_rebano", proxima_fecha=hoy - timedelta(days=3),
        ultima_fecha=hoy - timedelta(days=368),
    ))

    # --- Maquinaria: incluye una revisión ya vencida además de las próximas ---
    tractor = Maquina(nombre="Tractor New Holland", tipo="Tractor", marca="New Holland",
                       modelo="TD5.90", matricula="O-1234-BC", activa=True)
    ordenadora = Maquina(nombre="Ordeñadora", tipo="Ordeñadora", marca="DeLaval", activa=True)
    remolque = Maquina(nombre="Remolque esparcidor", tipo="Remolque", marca="Fedelma",
                        matricula="O-5678-BD", activa=True)
    db.add_all([tractor, ordenadora, remolque])
    db.flush()
    db.add(RevisionMaquina(
        maquina_id=tractor.id, fecha=hoy - timedelta(days=150),
        tipo_revision="Revisión periódica", taller="Talleres Rodríguez",
        coste=180.0, horas_km=3200, periodicidad_meses=6,
        proxima_fecha=hoy + timedelta(days=30),
    ))
    db.add(RevisionMaquina(
        maquina_id=ordenadora.id, fecha=hoy - timedelta(days=340),
        tipo_revision="Mantenimiento anual", taller="DeLaval Asturias",
        coste=95.0, periodicidad_meses=12, proxima_fecha=hoy + timedelta(days=25),
    ))
    db.add(RevisionMaquina(
        maquina_id=remolque.id, fecha=hoy - timedelta(days=400),
        tipo_revision="ITV", taller="ITV Asturias", coste=45.0,
        periodicidad_meses=12, proxima_fecha=hoy - timedelta(days=35),
        observaciones="Pendiente de pasar, ya vencida",
    ))

    # --- Análisis de leche: historial de 3 muestras para ver la evolución ---
    db.add(AnalisisLeche(
        numero_informe="85911", numero_recepcion="VT-DEMO-003", numero_muestra="690000000003",
        descripcion_muestra="Muestra tanque", producto="Leche de vaca cruda", laboratorio="LILA Asturias",
        fecha_toma=hoy - timedelta(days=7), fecha_recepcion=hoy - timedelta(days=7),
        fecha_emision_informe=hoy - timedelta(days=4),
        bactoscan=95, celulas_somaticas=210, crioscopia=522,
        extracto_seco_magro=8.85, materia_grasa=3.9, lactosa=4.7, proteina=3.4, urea=180,
        inhibidores="Negativo",
    ))
    db.add(AnalisisLeche(
        numero_informe="85870", numero_recepcion="VT-DEMO-002", numero_muestra="690000000002",
        descripcion_muestra="Muestra tanque", producto="Leche de vaca cruda", laboratorio="LILA Asturias",
        fecha_toma=hoy - timedelta(days=21), fecha_recepcion=hoy - timedelta(days=21),
        fecha_emision_informe=hoy - timedelta(days=18),
        bactoscan=110, celulas_somaticas=245, crioscopia=521,
        extracto_seco_magro=8.79, materia_grasa=3.85, lactosa=4.68, proteina=3.36, urea=175,
        inhibidores="Negativo",
    ))
    db.add(AnalisisLeche(
        numero_informe="85820", numero_recepcion="VT-DEMO-001", numero_muestra="690000000001",
        descripcion_muestra="Muestra tanque", producto="Leche de vaca cruda", laboratorio="LILA Asturias",
        fecha_toma=hoy - timedelta(days=35), fecha_recepcion=hoy - timedelta(days=35),
        fecha_emision_informe=hoy - timedelta(days=32),
        bactoscan=340, celulas_somaticas=430, crioscopia=520,
        extracto_seco_magro=8.7, materia_grasa=3.7, lactosa=4.6, proteina=3.3, urea=165,
        inhibidores="Positivo", observaciones="Antibiótico residual — se descartó el tanque",
    ))

    # --- Quesería ---
    cuajo = CuajoProducto(marca="Cuamix", registro_sanitario="RS-40001234",
                           lote_actual="L2026-04", caducidad_actual=hoy + timedelta(days=200))
    db.add(cuajo)
    db.add(Estanteria(nombre="Cámara 1"))
    db.add(Estanteria(nombre="Cámara 2"))
    lote_queso_listo = LoteQueso(
        codigo="Q2026-001", fecha_elaboracion=hoy - timedelta(days=90),
        turno_ordeno="manana", litros_leche=180, tipo_queso=TipoQueso.curado,
        num_piezas_inicial=6, etapa=EtapaQueso.listo,
        fecha_moldeado=hoy - timedelta(days=89), fecha_inicio_curacion=hoy - timedelta(days=88),
        dias_curacion_objetivo=60, peso_inicial_kg=12.5, fecha_listo=hoy - timedelta(days=28),
        es_ecologico=True, cuajo_marca="Cuamix", cuajo_registro_sanitario="RS-40001234",
        estanteria="Cámara 1", fila=1, columna=1,
    )
    lote_queso_curando = LoteQueso(
        codigo="Q2026-002", fecha_elaboracion=hoy - timedelta(days=15),
        turno_ordeno="tarde", litros_leche=165, tipo_queso=TipoQueso.semicurado,
        num_piezas_inicial=5, etapa=EtapaQueso.curacion,
        fecha_moldeado=hoy - timedelta(days=14), fecha_inicio_curacion=hoy - timedelta(days=13),
        dias_curacion_objetivo=30, es_ecologico=True,
        estanteria="Cámara 1", fila=2, columna=1,
    )
    lote_queso_nuevo = LoteQueso(
        codigo="Q2026-003", fecha_elaboracion=hoy - timedelta(days=1),
        turno_ordeno="manana", litros_leche=190, tipo_queso=TipoQueso.afuega_el_pitu,
        etapa=EtapaQueso.cuajado, es_ecologico=True,
    )
    db.add_all([lote_queso_listo, lote_queso_curando, lote_queso_nuevo])
    db.flush()
    db.add(MovimientoQueso(
        lote_id=lote_queso_listo.id, fecha=hoy - timedelta(days=10), tipo="venta",
        peso_kg=4.0, num_piezas=2, cliente="Tienda Ecológica El Horreo", precio_total=64.0,
    ))
    db.add(MovimientoQueso(
        lote_id=lote_queso_listo.id, fecha=hoy - timedelta(days=3), tipo="obsequio",
        peso_kg=1.0, num_piezas=1, cliente="Feria de la Ganadería de Llanera",
    ))

    # --- Alimentación ---
    heno = Alimento(nombre="Heno de prado", tipo="heno_propio", es_ecologico=True, unidad="kg")
    concentrado = Alimento(nombre="Pienso concentrado ecológico", tipo="concentrado", es_ecologico=True, unidad="kg")
    db.add_all([heno, concentrado])
    db.flush()
    db.add(RacionTipo(estado_productivo="lactante", alimento_id=concentrado.id, kg_por_animal_dia=6.5))
    db.add(RacionTipo(estado_productivo="gestante", alimento_id=heno.id, kg_por_animal_dia=8.0))
    db.add(StockMovimiento(alimento_id=heno.id, fecha=hoy - timedelta(days=60),
                            tipo_movimiento="entrada", cantidad_kg=4000))
    db.add(StockMovimiento(alimento_id=heno.id, fecha=hoy - timedelta(days=1),
                            tipo_movimiento="consumo", cantidad_kg=120))
    db.add(StockMovimiento(alimento_id=concentrado.id, fecha=hoy - timedelta(days=10),
                            tipo_movimiento="entrada", cantidad_kg=1000))
    db.add(StockMovimiento(alimento_id=concentrado.id, fecha=hoy - timedelta(days=1),
                            tipo_movimiento="consumo", cantidad_kg=45))
    db.add(CompraAlimento(alimento_id=concentrado.id, proveedor="Piensos Asturias",
                           fecha=hoy - timedelta(days=10), cantidad_kg=1000,
                           precio_total=420.0, certificado_eco="CAAE-33-00123"))

    # --- Economía ---
    db.add(Venta(
        animal_crotal="ES330000112", fecha=hoy - timedelta(days=45), tipo_venta=TipoVenta.desvieje,
        kg_peso=620, precio_kg=2.1, importe_total=1302.0,
        comprador="Matadero Comarcal", num_factura="F2026-0034",
    ))
    db.add(Venta(
        animal_crotal="ES330000109", fecha=hoy - timedelta(days=200), tipo_venta=TipoVenta.ternero_destete,
        kg_peso=180, precio_kg=3.4, importe_total=612.0, comprador="Ganadería vecina",
    ))
    db.add(Gasto(
        fecha=hoy - timedelta(days=5), categoria=CategoriaGasto.alimentacion,
        concepto="Pienso concentrado", importe=420.0, proveedor="Piensos Asturias",
        num_factura="F2026-0102",
    ))
    db.add(Gasto(
        fecha=hoy - timedelta(days=20), categoria=CategoriaGasto.maquinaria,
        concepto="Reparación tractor", importe=180.0, proveedor="Talleres Rodríguez",
    ))
    db.add(Gasto(
        fecha=hoy - timedelta(days=35), categoria=CategoriaGasto.sanidad,
        concepto="Visita veterinaria y vacunas", importe=210.0, proveedor="Clínica Veterinaria Llanera",
    ))
    db.add(Gasto(
        fecha=hoy - timedelta(days=60), categoria=CategoriaGasto.seguros,
        concepto="Seguro de responsabilidad civil ganadera", importe=340.0, proveedor="Agroseguro",
    ))

    # --- Agroturismo y Reservas ---
    visita_queseria = ActividadTurismo(
        nombre="Visita guiada a la quesería", tipo="visita", capacidad_maxima=12,
        precio_persona=8.0, duracion_horas=1.5,
        descripcion="Recorrido por la explotación y la quesería, con degustación final.",
    )
    degustacion = ActividadTurismo(
        nombre="Degustación de quesos ecológicos", tipo="degustacion", capacidad_maxima=20,
        precio_persona=15.0, duracion_horas=1.0,
        descripcion="Cata guiada de los quesos de la explotación con maridaje de sidra.",
    )
    apartamento = ActividadTurismo(
        nombre="Apartamento rural \"La Pomarada\"", tipo="alojamiento", capacidad_maxima=4,
        precio_persona=45.0,
        descripcion="Apartamento de 2 habitaciones con vistas a la pomarada.",
    )
    db.add_all([visita_queseria, degustacion, apartamento])
    db.flush()
    db.add(ReservaTurismo(
        actividad_id=visita_queseria.id, fecha_inicio=hoy + timedelta(days=3), fecha_fin=hoy + timedelta(days=3),
        num_personas=6, nombre_visitante="Colegio Público de Llanera", telefono="985111222",
        estado=EstadoReserva.confirmada, precio_total=48.0, pagado=True,
        observaciones="Salida escolar, grupo de 4º de primaria",
    ))
    db.add(ReservaTurismo(
        actividad_id=degustacion.id, fecha_inicio=hoy + timedelta(days=6), fecha_fin=hoy + timedelta(days=6),
        num_personas=4, nombre_visitante="Ana García", email="ana.garcia@example.com", telefono="600999888",
        estado=EstadoReserva.pendiente, precio_total=60.0, pagado=False,
    ))
    db.add(ReservaTurismo(
        actividad_id=apartamento.id, fecha_inicio=hoy + timedelta(days=10), fecha_fin=hoy + timedelta(days=13),
        num_personas=2, nombre_visitante="Familia Pérez", email="perez.familia@example.com",
        estado=EstadoReserva.confirmada, precio_total=270.0, pagado=True,
        observaciones="3 noches, llegan sobre las 18:00",
    ))
    db.add(ReservaTurismo(
        actividad_id=visita_queseria.id, fecha_inicio=hoy - timedelta(days=15), fecha_fin=hoy - timedelta(days=15),
        num_personas=8, nombre_visitante="Asociación de Jubilados de Siero", telefono="985222333",
        estado=EstadoReserva.completada, precio_total=64.0, pagado=True,
    ))

    # --- Presupuesto anual ---
    anio = hoy.year
    db.add(PresupuestoPartida(anio=anio, tipo="ingreso", categoria=TipoVenta.desvieje, importe_previsto=6000))
    db.add(PresupuestoPartida(anio=anio, tipo="ingreso", categoria=TipoVenta.ternero_destete, importe_previsto=4500))
    db.add(PresupuestoPartida(anio=anio, tipo="gasto", categoria=CategoriaGasto.alimentacion, importe_previsto=5200))
    db.add(PresupuestoPartida(anio=anio, tipo="gasto", categoria=CategoriaGasto.sanidad, importe_previsto=1200))
    db.add(PresupuestoPartida(anio=anio, tipo="gasto", categoria=CategoriaGasto.maquinaria, importe_previsto=1800))

    # --- Tareas ---
    db.add(Tarea(titulo="Revisar cerca prado del río", prioridad="media",
                  fecha_limite=hoy + timedelta(days=5), fecha_creacion=hoy))
    db.add(Tarea(titulo="Pedir cita veterinario para Reina (parto próximo)", prioridad="alta",
                  fecha_limite=hoy + timedelta(days=15), fecha_creacion=hoy))
    db.add(Tarea(titulo="Pasar la ITV del remolque", prioridad="alta",
                  fecha_limite=hoy - timedelta(days=5), fecha_creacion=hoy - timedelta(days=40)))
    db.add(Tarea(titulo="Renovar el seguro de la explotación", prioridad="baja",
                  fecha_limite=hoy - timedelta(days=200), fecha_creacion=hoy - timedelta(days=260),
                  completada=True, fecha_completada=hoy - timedelta(days=210)))

    db.commit()


def resetear_y_sembrar_demo():
    db = SessionLocal()
    try:
        _limpiar(db)
        _sembrar(db)
        logger.info("Demo reiniciada y sembrada con datos de ejemplo")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    resetear_y_sembrar_demo()
    print(f"Demo lista. Usuario: {DEMO_USERNAME} / Contraseña: {DEMO_PASSWORD}")
