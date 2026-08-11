from io import BytesIO
from collections import defaultdict


def generar_pdf_factura(factura, cliente, config) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, white
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    VERDE = HexColor("#198754")
    GRIS = HexColor("#f2f2f2")
    GRIS_HEADER = HexColor("#dee2e6")
    ROJO = HexColor("#dc3545")
    PAGE_W, PAGE_H = A4
    MARGIN = 1.8 * cm
    TW = PAGE_W - 2 * MARGIN

    styles = getSampleStyleSheet()
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=9, leading=12)
    bold = ParagraphStyle("bold", parent=normal, fontName="Helvetica-Bold")
    small = ParagraphStyle("small", parent=normal, fontSize=7.5, leading=10)
    titulo = ParagraphStyle("titulo", parent=styles["Normal"], fontSize=20, leading=24,
                             fontName="Helvetica-Bold", alignment=TA_RIGHT, textColor=VERDE)
    right = ParagraphStyle("right", parent=normal, alignment=TA_RIGHT)
    right_bold = ParagraphStyle("right_bold", parent=bold, alignment=TA_RIGHT)
    header_cell = ParagraphStyle("header_cell", parent=normal, fontName="Helvetica-Bold",
                                  textColor=white, fontSize=8.5)

    buffer = BytesIO()
    c = config
    estado_watermark = None
    if factura.estado == "borrador":
        estado_watermark = "BORRADOR — no es una factura válida hasta emitirse"
    elif factura.estado == "anulada":
        estado_watermark = "FACTURA ANULADA"

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(HexColor("#6c757d"))
        pie = f"{c.nombre_razon_social or ''}"
        if c.nif:
            pie += f" · NIF {c.nif}"
        canvas.drawString(MARGIN, MARGIN * 0.5, pie)
        canvas.drawRightString(PAGE_W - MARGIN, MARGIN * 0.5, f"Página {doc.page}")
        if estado_watermark:
            canvas.saveState()
            try:
                canvas.setFillAlpha(0.18)
            except Exception:
                pass
            canvas.setFillColor(ROJO)
            canvas.setFont("Helvetica-Bold", 26)
            canvas.translate(PAGE_W / 2, PAGE_H / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, estado_watermark)
            canvas.restoreState()
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN * 1.3,
        title=f"Factura {factura.numero or '(borrador)'}",
    )

    story = []

    # --- Cabecera: emisor a la izquierda, "FACTURA" + numero a la derecha ---
    emisor_lines = [c.nombre_razon_social or "—"]
    if c.nif:
        emisor_lines.append(f"NIF: {c.nif}")
    if c.direccion:
        emisor_lines.append(c.direccion)
    linea_loc = " ".join(x for x in [c.cp, c.localidad] if x)
    if linea_loc:
        emisor_lines.append(linea_loc)
    if c.telefono_fijo or c.telefono_movil:
        emisor_lines.append(" / ".join(x for x in [c.telefono_fijo, c.telefono_movil] if x))
    if c.email:
        emisor_lines.append(c.email)
    emisor_para = Paragraph("<br/>".join(emisor_lines), normal)

    numero_txt = factura.numero or "(borrador, sin numerar)"
    cabecera_der = [
        Paragraph("FACTURA", titulo),
        Spacer(1, 4),
        Paragraph(f"Nº {numero_txt}", right_bold),
        Paragraph(f"Fecha: {factura.fecha_emision.strftime('%d/%m/%Y')}", right),
    ]

    t_cab = Table([[emisor_para, cabecera_der]], colWidths=[TW * 0.55, TW * 0.45])
    t_cab.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(t_cab)
    story.append(Spacer(1, 18))

    # --- Cliente ---
    cliente_lines = [f"<b>Facturar a:</b>", cliente.nombre]
    if cliente.nif:
        cliente_lines.append(f"NIF: {cliente.nif}")
    if cliente.direccion:
        cliente_lines.append(cliente.direccion)
    linea_loc_cli = " ".join(x for x in [cliente.cp, cliente.localidad] if x)
    if linea_loc_cli:
        cliente_lines.append(linea_loc_cli)
    t_cli = Table([[Paragraph("<br/>".join(cliente_lines), normal)]], colWidths=[TW])
    t_cli.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t_cli)
    story.append(Spacer(1, 16))

    # --- Líneas ---
    headers = ["Concepto", "Cant.", "Precio ud.", "IVA", "Importe"]
    col_widths = [TW * 0.46, TW * 0.11, TW * 0.15, TW * 0.10, TW * 0.18]
    data = [[Paragraph(h, header_cell) for h in headers]]
    for linea in factura.lineas:
        data.append([
            Paragraph(linea.concepto, normal),
            Paragraph(f"{linea.cantidad:g}", right),
            Paragraph(f"{linea.precio_unitario:.2f} €", right),
            Paragraph(f"{linea.tipo_iva:g}%", right),
            Paragraph(f"{linea.importe:.2f} €", right),
        ])
    t_lineas = Table(data, colWidths=col_widths, repeatRows=1)
    estilo_lineas = [
        ("BACKGROUND", (0, 0), (-1, 0), VERDE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, GRIS_HEADER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            estilo_lineas.append(("BACKGROUND", (0, i), (-1, i), GRIS))
    t_lineas.setStyle(TableStyle(estilo_lineas))
    story.append(t_lineas)
    story.append(Spacer(1, 14))

    # --- Totales (desglose de IVA por tipo) ---
    por_tipo = defaultdict(float)
    for linea in factura.lineas:
        por_tipo[linea.tipo_iva] += linea.importe * linea.tipo_iva / 100

    filas_totales = [[Paragraph("Base imponible", bold), Paragraph(f"{factura.base_imponible:.2f} €", right)]]
    for tipo, cuota in sorted(por_tipo.items()):
        filas_totales.append([Paragraph(f"IVA ({tipo:g}%)", normal), Paragraph(f"{cuota:.2f} €", right)])
    if factura.total_irpf:
        filas_totales.append([Paragraph("Retención IRPF", normal), Paragraph(f"-{factura.total_irpf:.2f} €", right)])
    filas_totales.append([Paragraph("TOTAL", right_bold), Paragraph(f"{factura.total:.2f} €", right_bold)])

    t_tot = Table(filas_totales, colWidths=[TW * 0.75, TW * 0.25])
    t_tot.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEABOVE", (0, -1), (-1, -1), 1, VERDE),
        ("TOPPADDING", (0, -1), (-1, -1), 6),
    ]))
    story.append(t_tot)
    story.append(Spacer(1, 20))

    if factura.forma_pago:
        story.append(Paragraph(f"<b>Forma de pago:</b> {factura.forma_pago}", small))
    if factura.observaciones:
        story.append(Spacer(1, 4))
        story.append(Paragraph(factura.observaciones, small))

    if factura.hash_actual:
        story.append(Spacer(1, 16))
        story.append(Paragraph(f"Huella del documento: {factura.hash_actual[:32]}…", small))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return buffer.getvalue()
