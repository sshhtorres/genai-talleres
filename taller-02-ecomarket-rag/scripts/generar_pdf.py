"""Genera data/kb/terminos-y-condiciones.pdf a partir de su fuente en Markdown.

El PDF es el cuarto formato de la base de conocimiento. A propósito lleva un encabezado y un pie de
página repetidos en cada hoja (con el número de página), como los PDF reales: así la etapa de
limpieza del cargador tiene ruido que quitar, y se puede mostrar qué pasa si no se quita.

Uso (desde la raíz del repositorio):
    uv sync --all-groups --all-extras --all-packages    # instala reportlab (extra "scripts")
    uv run python taller-02-ecomarket-rag/scripts/generar_pdf.py

El PDF se genera en modo invariante (sin fecha de creación ni identificadores aleatorios): volver a
generarlo sin cambiar la fuente produce exactamente el mismo archivo.
"""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

KB_DIR = Path(__file__).resolve().parents[1] / "data" / "kb"
FUENTE = KB_DIR / "fuentes" / "terminos-y-condiciones.md"
DESTINO = KB_DIR / "terminos-y-condiciones.pdf"

ENCABEZADO = "EcoMarket S.A.S. — Términos y condiciones de compra — Versión {version}"
PIE = "Documento sintético para el Taller 2 de IA Generativa · Página {pagina}"


def _front_matter(texto: str) -> tuple[dict[str, str], str]:
    """Separa el front matter (clave: valor) del cuerpo."""
    if not texto.startswith("---"):
        return {}, texto
    _, cabecera, cuerpo = texto.split("---", 2)
    datos = {}
    for linea in cabecera.strip().splitlines():
        clave, _, valor = linea.partition(":")
        datos[clave.strip()] = valor.strip().strip('"')
    return datos, cuerpo


def _bloques(cuerpo: str) -> list[tuple[str, str | list[str]]]:
    """Encabezados, párrafos y listas del Markdown sencillo de la fuente."""
    bloques: list[tuple[str, str | list[str]]] = []
    for crudo in re.split(r"\n\s*\n", cuerpo.strip()):
        lineas = [linea.strip() for linea in crudo.strip().splitlines()]
        if not lineas:
            continue
        if lineas[0].startswith("#"):
            nivel = len(lineas[0]) - len(lineas[0].lstrip("#"))
            bloques.append((f"h{nivel}", lineas[0].lstrip("# ").strip()))
        elif all(linea.startswith("- ") for linea in lineas):
            bloques.append(("lista", [linea[2:] for linea in lineas]))
        else:
            bloques.append(("p", " ".join(lineas)))
    return bloques


def generar(fuente: Path = FUENTE, destino: Path = DESTINO) -> Path:
    datos, cuerpo = _front_matter(fuente.read_text(encoding="utf-8"))
    estilos = getSampleStyleSheet()
    historia = []
    for tipo, contenido in _bloques(cuerpo):
        if tipo == "h1":
            historia += [Paragraph(str(contenido), estilos["Title"]), Spacer(1, 0.3 * cm)]
        elif tipo.startswith("h"):
            historia.append(Paragraph(str(contenido), estilos["Heading3"]))
        elif tipo == "lista":
            items = [ListItem(Paragraph(i, estilos["BodyText"])) for i in contenido]
            historia.append(ListFlowable(items, bulletType="bullet"))
        else:
            historia.append(Paragraph(str(contenido), estilos["BodyText"]))

    version = datos.get("version", "")

    def _marco(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        ancho, alto = LETTER
        canvas.drawString(2 * cm, alto - 1.3 * cm, ENCABEZADO.format(version=version))
        canvas.drawString(2 * cm, 1.2 * cm, PIE.format(pagina=doc.page))
        canvas.restoreState()

    documento = SimpleDocTemplate(
        str(destino),
        pagesize=LETTER,
        topMargin=2.2 * cm,
        bottomMargin=2.2 * cm,
        title=datos.get("titulo", ""),
        author="EcoMarket (sintético)",
        invariant=1,
    )
    documento.build(historia, onFirstPage=_marco, onLaterPages=_marco)
    return destino


if __name__ == "__main__":
    print(f"PDF generado: {generar()}")
