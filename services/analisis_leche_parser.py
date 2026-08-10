import io
import re
from datetime import datetime

from pypdf import PdfReader

# Patrones ajustados al formato de informe de LILA Asturias (laboratorio
# interprofesional lechero de Asturias). Cada valor numérico va pegado, sin
# salto de línea, a la etiqueta y a la unidad ("194 ufc/ml (x1000)17/07/2026"),
# así que basta con capturar hasta la unidad e ignorar lo que venga después.
_PATRONES = {
    "numero_informe": r"N[ºo]\s*Informe de ensayo:\s*(\d+)",
    "numero_recepcion": r"N[ºo]\s*Recepci[oó]n:\s*([A-Za-z0-9\-]+)",
    "fecha_emision_informe": r"Fecha emisi[oó]n informe:\s*(\d{2}/\d{2}/\d{4})",
    "descripcion_muestra": r"Descripci[oó]n cliente:\s*(.+?)\s*(?:\(3\)|\n)",
    "producto": r"Producto:\s*(.+?)\s*(?:\(3\)|\n)",
    "numero_muestra": r"N[ºo]\s*de muestra:\s*(\d+)",
    "fecha_toma": r"Fecha toma:\s*(\d{2}/\d{2}/\d{4})",
    "fecha_recepcion": r"Fecha recepci[oó]n:\s*(\d{2}/\d{2}/\d{4})",
    "bactoscan": r"Bactoscan\.\s*([\d.,]+)\s*ufc/ml",
    "celulas_somaticas": r"Fossomatic\.\s*([\d.,]+)\s*c[ée]lulas/ml",
    "crioscopia": r"crioscopio\.\s*([\d.,]+)\s*-?\s*m[ºo]c",
    "extracto_seco_magro": r"Extracto seco magro\.\s*M[ée]todo infrarrojo\.\s*([\d.,]+)\s*%",
    "materia_grasa": r"Materia grasa\.\s*M[ée]todo infrarrojo\.\s*([\d.,]+)\s*%",
    "lactosa": r"Lactosa\.\s*M[ée]todo infrarrojo\.\s*([\d.,]+)\s*%",
    "proteina": r"Prote[ií]na\.\s*M[ée]todo infrarrojo\.\s*([\d.,]+)\s*%",
    "urea": r"Urea\.\s*M[ée]todo infrarrojo\.\s*([\d.,]+)\s*mg/l",
    "inhibidores": r"Detecci[oó]n inhibidores\s*(Negativo|Positivo)",
}

_CAMPOS_FECHA = {"fecha_emision_informe", "fecha_toma", "fecha_recepcion"}
_CAMPOS_NUMERICOS = {
    "bactoscan", "celulas_somaticas", "crioscopia", "extracto_seco_magro",
    "materia_grasa", "lactosa", "proteina", "urea",
}


def _fecha_iso(texto_dd_mm_aaaa: str) -> str:
    return datetime.strptime(texto_dd_mm_aaaa, "%d/%m/%Y").date().isoformat()


def parsear_pdf_lila(contenido: bytes) -> dict:
    """Extrae los campos de un informe de análisis de leche en PDF.

    Devuelve un dict con clave por campo (valores en formato ya listo para
    precargar en un <input>: fechas en ISO, números como string). Los campos
    que no se hayan podido reconocer quedan como cadena vacía, para que el
    usuario los revise/complete a mano en el formulario de confirmación —
    nunca se bloquea la importación por un formato ligeramente distinto.
    """
    lector = PdfReader(io.BytesIO(contenido))
    texto = "\n".join(pagina.extract_text() or "" for pagina in lector.pages)

    resultado = {}
    for campo, patron in _PATRONES.items():
        m = re.search(patron, texto, re.IGNORECASE)
        if not m:
            resultado[campo] = ""
            continue
        valor = m.group(1).strip()
        if campo in _CAMPOS_FECHA:
            try:
                valor = _fecha_iso(valor)
            except ValueError:
                valor = ""
        elif campo in _CAMPOS_NUMERICOS:
            valor = valor.replace(",", ".")
        resultado[campo] = valor

    return resultado
