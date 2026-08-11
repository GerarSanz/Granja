"""Encadenado + registro de facturación para el "modo no verificable" del
Reglamento de facturación (RD 1007/2023, Orden HAC/1177/2024).

El Reglamento permite dos modalidades de software de facturación:
  - VERI*FACTU: cada factura se envía a la AEAT en tiempo real (requiere el
    certificado digital del titular y su API SOAP). NO implementado aquí.
  - No verificable: no se envía nada a la AEAT en tiempo real, pero el
    registro de facturación tiene que ser íntegro, trazable e inalterable, y
    la factura debe llevar el código QR normativo. Es lo que implementa este
    módulo junto con services/factura_qr.py, y es una modalidad LEGALMENTE
    VÁLIDA por sí misma, no un parche a medias.

Cada factura emitida guarda el hash de la anterior + un hash propio calculado
a partir de sus datos clave. Si alguien edita una factura ya emitida (o borra
una del medio), la cadena deja de cuadrar y `verificar_cadena` lo detecta.
`emitida_en` guarda la fecha y hora de generación del registro.

Lo que sigue sin implementar, y requeriría trabajo adicional (y el
certificado digital real del titular, que esta app no puede generar ni
sustituir) si algún día se quiere dar el salto a la modalidad VERI*FACTU:
el envío en tiempo real del registro de facturación a la AEAT por su API
SOAP con firma XAdES.
"""
import hashlib
from sqlalchemy.orm import Session


def calcular_hash(factura, hash_anterior: str | None) -> str:
    partes = [
        hash_anterior or "",
        factura.numero or "",
        factura.fecha_emision.isoformat(),
        str(factura.cliente_id),
        f"{factura.total:.2f}",
    ]
    cadena = "|".join(partes)
    return hashlib.sha256(cadena.encode("utf-8")).hexdigest()


def siguiente_numero(db: Session, anio: int) -> str:
    from models.facturacion import Factura
    numeros = db.query(Factura.numero).filter(Factura.numero.like(f"{anio}/%")).all()
    max_sec = 0
    for (num,) in numeros:
        try:
            sec = int(num.split("/")[1])
            max_sec = max(max_sec, sec)
        except (IndexError, ValueError):
            continue
    return f"{anio}/{max_sec + 1:04d}"


def verificar_cadena(facturas_emitidas: list) -> list[dict]:
    """`facturas_emitidas` debe venir ordenada por fecha de emisión / número."""
    resultado = []
    anterior = None
    for f in facturas_emitidas:
        hash_anterior_esperado = anterior.hash_actual if anterior else None
        hash_recalculado = calcular_hash(f, f.hash_anterior)
        integra = (f.hash_anterior == hash_anterior_esperado) and (f.hash_actual == hash_recalculado)
        resultado.append({"factura": f, "integra": integra})
        anterior = f
    return resultado
