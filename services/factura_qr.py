"""Código QR normativo del Reglamento de facturación (RD 1007/2023 y Orden
HAC/1177/2024) para el "modo no verificable" — ver services/facturacion_hash.py
para la explicación completa de qué cubre y qué no cubre este módulo frente
al Reglamento VERI*FACTU.

El QR es el mismo en ambos modos (VERI*FACTU y no verificable): apunta al
validador público de la AEAT con los 4 datos mínimos de la factura. La
diferencia entre modos no está en el QR en sí, sino en si el emisor ha
enviado antes el registro de facturación a la AEAT — aquí NO se envía, así
que al escanearlo la AEAT devolverá "factura no verificable" en vez de
confirmarla contra un registro ya recibido.

Formato verificado contra la documentación pública de la AEAT en
sede.agenciatributaria.gob.es (consultada agosto 2026):
  https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR
    ?nif=<NIF emisor>&numserie=<nº factura>&fecha=<DD-MM-YYYY>&importe=<0.00>
Si la AEAT cambia el formato, este es el único sitio que hay que tocar.
"""
from datetime import date
from io import BytesIO
from urllib.parse import quote

URL_VALIDACION_QR = "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR"

LEYENDA_NO_VERIFICABLE = "Factura no verificable en la sede electrónica de la AEAT"


def url_validacion(nif_emisor: str, numero_factura: str, fecha_emision: date, importe_total: float) -> str:
    return (
        f"{URL_VALIDACION_QR}"
        f"?nif={quote(nif_emisor or '', safe='')}"
        f"&numserie={quote(numero_factura or '', safe='/')}"
        f"&fecha={fecha_emision.strftime('%d-%m-%Y')}"
        f"&importe={importe_total:.2f}"
    )


def generar_qr_png(nif_emisor: str, numero_factura: str, fecha_emision: date, importe_total: float) -> bytes:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M

    url = url_validacion(nif_emisor, numero_factura, fecha_emision, importe_total)
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    imagen = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()
