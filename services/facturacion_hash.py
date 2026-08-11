"""Encadenado tipo VERI*FACTU simplificado para facturas emitidas.

Cada factura emitida guarda el hash de la anterior + un hash propio calculado
a partir de sus datos clave. Si alguien edita una factura ya emitida (o borra
una del medio), la cadena deja de cuadrar y `verificar_cadena` lo detecta.

Esto da una evidencia básica de que las facturas no se han alterado después
de emitidas — es la pieza de "no alterable / trazable" del Reglamento
VERI*FACTU. NO es una implementación completa: falta el código QR con el
formato que exige la AEAT y el envío en tiempo real (modalidad VERI*FACTU) o
el registro de facturación firmado (modalidad no verificable completa).
Antes de vender esto como "cumple VERI*FACTU" a un cliente real hace falta
cerrar esa parte.
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
