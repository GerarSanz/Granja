from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import extract
from datetime import date
from io import BytesIO

from database import get_db
from auth import get_current_user
from models.cuaderno import ConfigExplotacion, AplicadorFito, EquipoAplicacion
from models.lote import Parcela, TratamientoParcela, AbonoParcela
from models.usuario import Usuario

router = APIRouter(prefix="/cuaderno", tags=["cuaderno"])
templates = Jinja2Templates(directory="templates")

# Campos que debería tener rellenos el cuaderno antes de una inspección
CAMPOS_OBLIGATORIOS = [
    ("nombre_razon_social", "Nombre / razón social"),
    ("nif", "NIF"),
    ("n_registro_nacional", "Nº registro nacional"),
    ("direccion", "Dirección"),
]


def _campos_faltantes(config):
    if not config:
        return [label for _, label in CAMPOS_OBLIGATORIOS]
    return [label for campo, label in CAMPOS_OBLIGATORIOS if not getattr(config, campo, None)]


@router.get("", response_class=HTMLResponse)
def index_cuaderno(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    config = db.query(ConfigExplotacion).first()
    aplicadores = db.query(AplicadorFito).order_by(AplicadorFito.id).all()
    equipos = db.query(EquipoAplicacion).order_by(EquipoAplicacion.id).all()
    anio_actual = date.today().year
    return templates.TemplateResponse("cuaderno/index.html", {
        "request": request,
        "config": config,
        "aplicadores": aplicadores,
        "equipos": equipos,
        "anio_actual": anio_actual,
        "campos_faltantes": _campos_faltantes(config),
        "current_user": current_user,
    })


@router.post("/config")
def guardar_config(
    nombre_razon_social: str = Form(default=""),
    nif: str = Form(default=""),
    n_registro_nacional: str = Form(default=""),
    n_registro_autonomico: str = Form(default=""),
    direccion: str = Form(default=""),
    localidad: str = Form(default=""),
    cp: str = Form(default=""),
    provincia: str = Form(default=""),
    telefono_fijo: str = Form(default=""),
    telefono_movil: str = Form(default=""),
    email: str = Form(default=""),
    titular_nombre: str = Form(default=""),
    titular_nif: str = Form(default=""),
    asesor_nombre: str = Form(default=""),
    asesor_nif: str = Form(default=""),
    asesor_n_identificacion: str = Form(default=""),
    tipo_explotacion_gip: str = Form(default="AE"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    config = db.query(ConfigExplotacion).first()
    if not config:
        config = ConfigExplotacion(id=1)
        db.add(config)
    config.nombre_razon_social = nombre_razon_social.strip() or None
    config.nif = nif.strip() or None
    config.n_registro_nacional = n_registro_nacional.strip() or None
    config.n_registro_autonomico = n_registro_autonomico.strip() or None
    config.direccion = direccion.strip() or None
    config.localidad = localidad.strip() or None
    config.cp = cp.strip() or None
    config.provincia = provincia.strip() or None
    config.telefono_fijo = telefono_fijo.strip() or None
    config.telefono_movil = telefono_movil.strip() or None
    config.email = email.strip() or None
    config.titular_nombre = titular_nombre.strip() or None
    config.titular_nif = titular_nif.strip() or None
    config.asesor_nombre = asesor_nombre.strip() or None
    config.asesor_nif = asesor_nif.strip() or None
    config.asesor_n_identificacion = asesor_n_identificacion.strip() or None
    config.tipo_explotacion_gip = tipo_explotacion_gip or "AE"
    db.commit()
    return RedirectResponse(url="/cuaderno", status_code=302)


@router.post("/aplicador/nuevo")
def nuevo_aplicador(
    nombre: str = Form(...),
    nif: str = Form(default=""),
    n_inscripcion_ropo: str = Form(default=""),
    tipo_carne: str = Form(default="basico"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db.add(AplicadorFito(
        nombre=nombre.strip(),
        nif=nif.strip() or None,
        n_inscripcion_ropo=n_inscripcion_ropo.strip() or None,
        tipo_carne=tipo_carne or "basico",
    ))
    db.commit()
    return RedirectResponse(url="/cuaderno", status_code=302)


@router.post("/aplicador/{aplicador_id}/eliminar")
def eliminar_aplicador(
    aplicador_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    a = db.query(AplicadorFito).filter(AplicadorFito.id == aplicador_id).first()
    if a:
        db.delete(a)
        db.commit()
    return RedirectResponse(url="/cuaderno", status_code=302)


@router.post("/equipo/nuevo")
def nuevo_equipo(
    descripcion: str = Form(...),
    n_inscripcion_roma: str = Form(default=""),
    fecha_adquisicion: str = Form(default=""),
    fecha_ultima_inspeccion: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    db.add(EquipoAplicacion(
        descripcion=descripcion.strip(),
        n_inscripcion_roma=n_inscripcion_roma.strip() or None,
        fecha_adquisicion=fecha_adquisicion.strip() or None,
        fecha_ultima_inspeccion=fecha_ultima_inspeccion.strip() or None,
    ))
    db.commit()
    return RedirectResponse(url="/cuaderno", status_code=302)


@router.post("/equipo/{equipo_id}/eliminar")
def eliminar_equipo(
    equipo_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    e = db.query(EquipoAplicacion).filter(EquipoAplicacion.id == equipo_id).first()
    if e:
        db.delete(e)
        db.commit()
    return RedirectResponse(url="/cuaderno", status_code=302)


@router.get("/pdf")
def generar_pdf(
    anio: int = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not anio:
        anio = date.today().year

    config = db.query(ConfigExplotacion).first()
    aplicadores = db.query(AplicadorFito).order_by(AplicadorFito.id).all()
    equipos = db.query(EquipoAplicacion).order_by(EquipoAplicacion.id).all()
    parcelas = db.query(Parcela).order_by(Parcela.id).all()

    tratamientos = (
        db.query(TratamientoParcela)
        .filter(extract("year", TratamientoParcela.fecha) == anio)
        .order_by(TratamientoParcela.fecha)
        .all()
    )
    abonos = (
        db.query(AbonoParcela)
        .filter(extract("year", AbonoParcela.fecha) == anio)
        .order_by(AbonoParcela.fecha)
        .all()
    )

    pdf_bytes = _build_pdf(config, aplicadores, equipos, parcelas, tratamientos, abonos, anio)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=cuaderno_explotacion_{anio}.pdf"},
    )


# ─── PDF generation ───────────────────────────────────────────────────────────

def _build_pdf(config, aplicadores, equipos, parcelas, tratamientos, abonos, anio):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, white, black, Color
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table, TableStyle,
                                     Spacer, PageBreak, KeepTogether)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    VERDE = HexColor("#198754")
    VERDE_CLARO = HexColor("#d1e7dd")
    GRIS = HexColor("#f2f2f2")
    GRIS_HEADER = HexColor("#dee2e6")
    PAGE_W, PAGE_H = landscape(A4)
    MARGIN = 1.5 * cm
    TW = PAGE_W - 2 * MARGIN  # usable table width ≈ 756 pt

    styles = getSampleStyleSheet()
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=7, leading=9)
    bold = ParagraphStyle("bold", parent=normal, fontName="Helvetica-Bold")
    titulo = ParagraphStyle("titulo", parent=styles["Normal"],
                             fontSize=14, leading=17, fontName="Helvetica-Bold",
                             alignment=TA_CENTER, spaceAfter=4)
    subtitulo = ParagraphStyle("subtitulo", parent=styles["Normal"],
                                fontSize=10, leading=13, alignment=TA_CENTER, spaceAfter=8)
    sec_header = ParagraphStyle("sec", parent=styles["Normal"],
                                 fontSize=8, leading=10, fontName="Helvetica-Bold",
                                 alignment=TA_CENTER)
    small = ParagraphStyle("small", parent=normal, fontSize=6.5, leading=8)

    buffer = BytesIO()
    c = config or ConfigExplotacion()
    titular_line = (c.titular_nombre or c.nombre_razon_social or "")
    anio_str = str(anio)

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(HexColor("#6c757d"))
        canvas.drawString(MARGIN, MARGIN * 0.6,
                          f"Explotación / Titular: {titular_line}   —   Año: {anio_str}")
        canvas.drawRightString(PAGE_W - MARGIN, MARGIN * 0.6,
                               f"Hoja {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN * 1.4,
        title=f"Cuaderno de Explotación {anio}",
    )

    story = []

    def sec_title(text):
        data = [[Paragraph(text, sec_header)]]
        t = Table(data, colWidths=[TW])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), VERDE),
            ("TEXTCOLOR", (0, 0), (-1, -1), white),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("BOX", (0, 0), (-1, -1), 0.5, VERDE),
        ]))
        return t

    def data_table(headers, rows, col_widths, zebra=True):
        header_row = [Paragraph(h, bold) for h in headers]
        data = [header_row]
        for i, row in enumerate(rows):
            data.append([Paragraph(str(c) if c is not None else "—", normal) for c in row])
        t = Table(data, colWidths=col_widths, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), GRIS_HEADER),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("LEADING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#ced4da")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        if zebra:
            for i in range(1, len(data)):
                if i % 2 == 0:
                    style.append(("BACKGROUND", (0, i), (-1, i), GRIS))
        t.setStyle(TableStyle(style))
        return t

    # ── PORTADA ──────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph("CUADERNO DE EXPLOTACIÓN DE PRODUCTOS FITOSANITARIOS", titulo))
    story.append(Paragraph(f"Ministerio de Agricultura, Pesca y Alimentación · Campaña {anio}", subtitulo))
    story.append(Spacer(1, 0.5 * cm))

    campos_faltantes = _campos_faltantes(config)
    if campos_faltantes:
        aviso_style = ParagraphStyle("aviso", parent=bold, fontSize=8, leading=11,
                                      textColor=HexColor("#842029"))
        aviso_table = Table(
            [[Paragraph(
                f"⚠ FALTAN DATOS OBLIGATORIOS DE LA EXPLOTACIÓN: {', '.join(campos_faltantes)}. "
                "Complétalos en /cuaderno antes de presentar este documento en una inspección.",
                aviso_style,
            )]],
            colWidths=[TW],
        )
        aviso_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#f8d7da")),
            ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#842029")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(aviso_table)
        story.append(Spacer(1, 0.4 * cm))

    # ── SECCIÓN 1.1 ──────────────────────────────────────────────────────────
    story.append(sec_title("1.1  DATOS GENERALES DE LA EXPLOTACIÓN"))
    story.append(Spacer(1, 2))
    datos_11 = [
        ["Nombre / Razón social", c.nombre_razon_social or "", "NIF", c.nif or ""],
        ["Nº Registro Nacional", c.n_registro_nacional or "", "Nº Registro Autonómico", c.n_registro_autonomico or ""],
        ["Dirección", c.direccion or "", "Localidad", c.localidad or ""],
        ["C. Postal", c.cp or "", "Provincia", c.provincia or ""],
        ["Teléfono fijo", c.telefono_fijo or "", "Teléfono móvil", c.telefono_movil or ""],
        ["E-mail", c.email or "", "", ""],
        ["Titular / Nombre y apellidos", c.titular_nombre or "", "NIF titular", c.titular_nif or ""],
        ["Asesor", c.asesor_nombre or "", "NIF asesor", c.asesor_nif or ""],
        ["Nº identificación asesor", c.asesor_n_identificacion or "", "Sistema GIP", c.tipo_explotacion_gip or "AE"],
    ]
    cw_11 = [TW * 0.2, TW * 0.3, TW * 0.2, TW * 0.3]
    t11_rows = []
    for row in datos_11:
        t11_rows.append([
            Paragraph(row[0], bold), Paragraph(row[1], normal),
            Paragraph(row[2], bold), Paragraph(row[3], normal),
        ])
    t11 = Table(t11_rows, colWidths=cw_11)
    t11.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("LEADING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#ced4da")),
        ("BACKGROUND", (0, 0), (0, -1), GRIS),
        ("BACKGROUND", (2, 0), (2, -1), GRIS),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(t11)
    story.append(Spacer(1, 0.4 * cm))

    # ── SECCIÓN 1.2 APLICADORES ───────────────────────────────────────────────
    story.append(sec_title("1.2  PERSONAS O EMPRESAS QUE INTERVIENEN EN EL TRATAMIENTO"))
    story.append(Spacer(1, 2))
    if aplicadores:
        hdrs_12 = ["Nº", "Nombre y apellidos / Empresa", "NIF", "Nº Inscripción ROPO", "Tipo de carné"]
        rows_12 = [(i + 1, a.nombre, a.nif or "—", a.n_inscripcion_ropo or "—", a.tipo_carne or "—")
                   for i, a in enumerate(aplicadores)]
        cw_12 = [TW * 0.05, TW * 0.38, TW * 0.15, TW * 0.22, TW * 0.20]
        story.append(data_table(hdrs_12, rows_12, cw_12))
    else:
        story.append(Paragraph("(Sin aplicadores registrados)", small))
    story.append(Spacer(1, 0.4 * cm))

    # ── SECCIÓN 1.3 EQUIPOS ───────────────────────────────────────────────────
    story.append(sec_title("1.3  EQUIPOS DE APLICACIÓN DE PRODUCTOS FITOSANITARIOS"))
    story.append(Spacer(1, 2))
    if equipos:
        hdrs_13 = ["Nº", "Descripción del equipo (tipo, marca, modelo)", "Nº Inscripción ROMA", "Fecha adquisición", "Fecha última inspección"]
        rows_13 = [(i + 1, e.descripcion, e.n_inscripcion_roma or "—",
                    e.fecha_adquisicion or "—", e.fecha_ultima_inspeccion or "—")
                   for i, e in enumerate(equipos)]
        cw_13 = [TW * 0.05, TW * 0.40, TW * 0.20, TW * 0.175, TW * 0.175]
        story.append(data_table(hdrs_13, rows_13, cw_13))
    else:
        story.append(Paragraph("(Sin equipos registrados)", small))
    story.append(PageBreak())

    # ── SECCIÓN 2.1 PARCELAS ──────────────────────────────────────────────────
    story.append(sec_title("2. IDENTIFICACIÓN DE LAS PARCELAS DE LA EXPLOTACIÓN"))
    story.append(Spacer(1, 2))
    story.append(sec_title("2.1  DATOS IDENTIFICATIVOS Y AGRONÓMICOS DE LAS PARCELAS"))
    story.append(Spacer(1, 2))
    if parcelas:
        hdrs_21 = ["Nº", "Nombre", "Prov.", "T. Municipal", "Polígono", "Parcela",
                   "Uso SIGPAC", "Sup. SIGPAC (ha)", "Sup. Cult. (ha)",
                   "Especie", "Variedad", "Sec./Reg.", "Protección", "GIP"]
        rows_21 = []
        for i, p in enumerate(parcelas):
            rows_21.append((
                i + 1,
                p.nombre,
                p.provincia_codigo or "33",
                p.municipio or "—",
                p.poligono or "—",
                p.parcela_sigpac or "—",
                "—",
                f"{p.hectareas:.2f}",
                f"{p.hectareas:.2f}",
                p.especie_cultivo or "Pradera Natural",
                p.variedad_cultivo or "—",
                p.regadio or "SEC",
                p.tipo_proteccion or "AL",
                c.tipo_explotacion_gip or "AE",
            ))
        cw_21 = [TW*0.04, TW*0.09, TW*0.04, TW*0.09, TW*0.055, TW*0.055,
                 TW*0.06, TW*0.065, TW*0.065, TW*0.09, TW*0.08, TW*0.05, TW*0.055, TW*0.04]
        story.append(data_table(hdrs_21, rows_21, cw_21))
    else:
        story.append(Paragraph("(Sin parcelas registradas)", small))
    story.append(PageBreak())

    # ── SECCIÓN 3.1 TRATAMIENTOS ──────────────────────────────────────────────
    story.append(sec_title("3. INFORMACIÓN SOBRE TRATAMIENTOS FITOSANITARIOS"))
    story.append(Spacer(1, 2))
    story.append(sec_title("3.1  REGISTRO DE ACTUACIONES FITOSANITARIAS DE LA PARCELA"))
    story.append(Spacer(1, 2))

    # Build parcela index map for quick lookup
    parcela_num = {p.id: (i + 1) for i, p in enumerate(parcelas)}

    if tratamientos:
        hdrs_31 = ["Nº\nParc.", "Especie", "Variedad", "Fecha", "Sup.\n(ha)",
                   "Problema\nfitosanitario", "Aplicador", "Nombre comercial",
                   "Nº Registro", "Dosis\n(kg/ha o l/ha)", "Eficacia", "Observaciones"]
        rows_31 = []
        for t in tratamientos:
            p = t.parcela
            pnum = parcela_num.get(t.parcela_id, "?")
            rows_31.append((
                pnum,
                (p.especie_cultivo or "Pradera Natural") if p else "—",
                (p.variedad_cultivo or "—") if p else "—",
                t.fecha.strftime("%d/%m/%Y"),
                f"{t.superficie_ha:.2f}" if t.superficie_ha else "—",
                t.problema_fitosanitario or "—",
                t.aplicador_nombre or "—",
                t.producto,
                t.num_registro_fito or "—",
                t.dosis or "—",
                t.eficacia or "—",
                t.observaciones or "—",
            ))
        cw_31 = [TW*0.045, TW*0.08, TW*0.07, TW*0.065, TW*0.045,
                 TW*0.11, TW*0.08, TW*0.13, TW*0.07, TW*0.07, TW*0.06, TW*0.125]
        story.append(data_table(hdrs_31, rows_31, cw_31))
    else:
        story.append(Paragraph(f"(Sin tratamientos fitosanitarios registrados en {anio})", small))
    story.append(PageBreak())

    # ── SECCIÓN 6 FERTILIZACIÓN ───────────────────────────────────────────────
    story.append(sec_title("6. REGISTRO DE FERTILIZACIÓN"))
    story.append(Spacer(1, 2))
    if abonos:
        hdrs_6 = ["Fecha", "Nº Parce.", "Especie", "Variedad",
                  "Tipo abono / Producto", "Nº Albarán",
                  "Riqueza N/P/K", "Dosis (kg/ha, m³/ha)", "Tipo\nFertiliz.", "Observaciones"]
        rows_6 = []
        for a in abonos:
            p = a.parcela
            pnum = parcela_num.get(a.parcela_id, "?")
            tipo_abono = _tipo_abono_codigo(a.tipo)
            rows_6.append((
                a.fecha.strftime("%d/%m/%Y"),
                pnum,
                (p.especie_cultivo or "Pradera Natural") if p else "—",
                (p.variedad_cultivo or "—") if p else "—",
                f"{tipo_abono} — {a.producto or a.tipo}",
                a.albaran or "—",
                a.riqueza_npk or "—",
                f"{a.cantidad} {a.unidad}/ha" if a.cantidad and a.unidad else "—",
                a.tipo_fertilizacion or "AF",
                a.observaciones or "—",
            ))
        cw_6 = [TW*0.07, TW*0.05, TW*0.09, TW*0.08, TW*0.16,
                TW*0.07, TW*0.08, TW*0.10, TW*0.055, TW*0.135]
        story.append(data_table(hdrs_6, rows_6, cw_6))
    else:
        story.append(Paragraph(f"(Sin abonados registrados en {anio})", small))

    # ── FOOTER FIRMA ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.6 * cm))
    firma_data = [
        [Paragraph("La persona firmante se hace responsable de la veracidad de los datos consignados.", small),
         Paragraph("Firma del titular o representante:", small)],
        ["", Spacer(1, 1.5 * cm)],
        ["", Paragraph(f"Fecha: ___/___/______", small)],
    ]
    t_firma = Table(firma_data, colWidths=[TW * 0.6, TW * 0.4])
    t_firma.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (1, 0), (1, -1), 0.5, HexColor("#ced4da")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_firma)

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return buffer.getvalue()


def _tipo_abono_codigo(tipo: str) -> str:
    codigos = {
        "estiércol": "EB",
        "purín": "PP",
        "compost": "C",
        "abono verde": "O",
        "mineral": "O",
        "orgánico": "O",
        "otro": "O",
    }
    return codigos.get(tipo.lower(), "O") if tipo else "O"
