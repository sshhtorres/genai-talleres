"""Paso 1 de la indexación: cargar cada tipo de documento como `Document`s de LangChain.

Un *loader* por formato. Cada `Document` sale con los metadatos base (`doc_id`, `tipo`, `fuente`,
`version`, `idioma`) que luego permiten filtrar ("solo crédito") y citar la fuente.

- Markdown (políticas): un solo `Document` con el texto completo; el chunking estructural lo divide.
- JSON (crédito) y CSV (catálogo): un `Document` por registro, ya serializado como texto natural.
  Un registro es una unidad de significado completa: partirlo o mezclarlo con otro lo estropea.
- PDF (términos): un `Document` por página, después de limpiar el encabezado y el pie repetidos.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import Path

from langchain_core.documents import Document

from . import kb
from .config import KB_DIR

TIPO_POLITICAS = "politicas"
TIPO_CREDITO = "credito"
TIPO_PRODUCTO = "producto"
TIPO_TERMINOS = "terminos"


def limpiar_texto(texto: str) -> str:
    """Unicode NFC, sin espacios al final de línea y sin más de una línea en blanco seguida."""
    texto = unicodedata.normalize("NFC", texto)
    texto = "\n".join(linea.rstrip() for linea in texto.splitlines())
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


# -- Markdown -------------------------------------------------------------------


def cargar_politicas(ruta: Path | None = None) -> list[Document]:
    ruta = ruta or KB_DIR / "politicas-y-faq.md"
    datos, cuerpo = kb.front_matter(ruta.read_text(encoding="utf-8"))
    return [
        Document(
            page_content=limpiar_texto(cuerpo),
            metadata={
                "doc_id": kb.DOC_POLITICAS,
                "tipo": TIPO_POLITICAS,
                "fuente": ruta.name,
                "version": datos.get("version", ""),
                "vigente_desde": datos.get("vigente_desde", ""),
                "idioma": "es",
            },
        )
    ]


# -- JSON -----------------------------------------------------------------------


def serializar_regla(regla: dict) -> str:
    """Una regla de crédito como texto autocontenido: el tema viaja con la regla."""
    return (
        f"Tema: {regla['tema']}.\n"
        f"Regla: {regla['regla']}\n"
        f"Condiciones: {regla['condiciones']}\n"
        f"Ejemplo: {regla['ejemplo']}"
    )


def cargar_credito() -> list[Document]:
    documento = kb.reglas_credito()
    return [
        Document(
            page_content=serializar_regla(regla),
            metadata={
                "doc_id": kb.DOC_CREDITO,
                "tipo": TIPO_CREDITO,
                "fuente": "reglas-credito.json",
                "version": documento.get("version", ""),
                "vigente_desde": regla["vigente_desde"],
                "idioma": "es",
                "id_regla": regla["id"],
                "tema": regla["tema"],
                "seccion": f"Reglas de crédito{kb.SEPARADOR_RUTA}{regla['id']} · {regla['tema']}",
            },
        )
        for regla in documento["reglas"]
    ]


# -- CSV ------------------------------------------------------------------------

# Las etiquetas van en el idioma de la ficha: así la subiría el vendedor. Mezclar etiquetas en
# español con contenido en inglés le daría al embedding una pista que un caso real no tendría.
_ETIQUETAS = {
    "es": {
        "nombre": "Producto",
        "categoria": "Categoría",
        "retornable": "Retornable",
        "descripcion": "Descripción",
        "materiales": "Materiales",
        "modo_de_uso": "Modo de uso",
        "cuidados": "Cuidados",
        "certificaciones": "Certificaciones",
        "nota_retorno": "Condiciones de devolución",
        "si": "sí",
        "no": "no",
    },
    "en": {
        "nombre": "Product",
        "categoria": "Category",
        "retornable": "Returnable",
        "descripcion": "Description",
        "materiales": "Materials",
        "modo_de_uso": "How to use",
        "cuidados": "Care",
        "certificaciones": "Certifications",
        "nota_retorno": "Return conditions",
        "si": "yes",
        "no": "no",
    },
}


def serializar_producto(fila: dict[str, str]) -> str:
    """Una fila del CSV como ficha de texto. Un CSV no tiene párrafos: sin esto, un splitter
    podría dejar media fila de un producto y media del siguiente en el mismo chunk."""
    etiquetas = _ETIQUETAS[fila["idioma"]]
    retornable = etiquetas["si"] if fila["retornable"] == "true" else etiquetas["no"]
    campos = [
        "descripcion",
        "materiales",
        "modo_de_uso",
        "cuidados",
        "certificaciones",
        "nota_retorno",
    ]
    lineas = [
        f"{etiquetas['nombre']}: {fila['nombre']}.",
        f"{etiquetas['categoria']}: {fila['categoria'].replace('_', ' ')}.",
        f"{etiquetas['retornable']}: {retornable}.",
        *(f"{etiquetas[c]}: {fila[c]}" for c in campos),
    ]
    return "\n".join(lineas)


def cargar_catalogo(enriquecer_ingles: bool = False) -> list[Document]:
    """Una ficha por producto. Con `enriquecer_ingles`, a las fichas en inglés se les antepone el
    resumen en español guardado en data/kb/.enriquecido/ (experimento E7)."""
    return [
        Document(
            page_content=_texto_ficha(fila, enriquecer_ingles),
            metadata={
                "doc_id": kb.DOC_CATALOGO,
                "tipo": TIPO_PRODUCTO,
                "fuente": "catalogo.csv",
                "version": "",
                "idioma": fila["idioma"],
                "sku": fila["sku"],
                "categoria": fila["categoria"],
                "retornable": fila["retornable"] == "true",
                "seccion": f"Catálogo{kb.SEPARADOR_RUTA}{fila['sku']} · {fila['nombre']}",
                "enriquecido": enriquecer_ingles and fila["idioma"] == "en",
            },
        )
        for fila in kb.catalogo()
    ]


def _texto_ficha(fila: dict[str, str], enriquecer_ingles: bool) -> str:
    texto = serializar_producto(fila)
    if not enriquecer_ingles or fila["idioma"] != "en":
        return texto
    from genai_common import ConfigError

    from .enriquecimiento import leer_resumen

    resumen = leer_resumen(fila["sku"])
    if resumen is None:
        raise ConfigError(
            f"Falta el resumen en español de {fila['sku']}: genera los resúmenes con "
            "`taller02 enriquecer` antes de indexar con --enriquecer-ingles."
        )
    return f"Resumen en español: {resumen}\n\n{texto}"


# -- PDF ------------------------------------------------------------------------


def lineas_repetidas(paginas: list[str], minimo: float = 0.6) -> set[str]:
    """Líneas que se repiten en la mayoría de las páginas: encabezados y pies de página.

    Los dígitos se normalizan antes de contar para que "Página 1" y "Página 2" cuenten como la
    misma línea. Con una sola página no se puede distinguir ruido de contenido: no se quita nada.
    """
    if len(paginas) < 2:
        return set()
    conteo: Counter[str] = Counter()
    for pagina in paginas:
        conteo.update({re.sub(r"\d+", "#", linea.strip()) for linea in pagina.splitlines()})
    return {linea for linea, n in conteo.items() if linea and n / len(paginas) >= minimo}


def limpiar_paginas(paginas: list[str]) -> list[str]:
    ruido = lineas_repetidas(paginas)
    limpias = []
    for pagina in paginas:
        lineas = [
            linea
            for linea in pagina.splitlines()
            if re.sub(r"\d+", "#", linea.strip()) not in ruido
        ]
        limpias.append(limpiar_texto("\n".join(lineas)))
    return limpias


def cargar_terminos(ruta: Path | None = None, limpiar: bool = True) -> list[Document]:
    """PDF de términos, una página por `Document`, sin el encabezado y el pie repetidos.

    Se lee con `pypdf` directamente: es lo mismo que hace `PyPDFLoader` (un envoltorio delgado de
    pypdf), sin sumar `langchain-community` y sus dependencias solo para esto.
    `limpiar=False` deja el ruido, para mostrar qué pasa si no se limpia.
    """
    from pypdf import PdfReader

    ruta = ruta or KB_DIR / "terminos-y-condiciones.pdf"
    datos, _ = kb.terminos_fuente()
    paginas = [pagina.extract_text() or "" for pagina in PdfReader(ruta).pages]
    textos = limpiar_paginas(paginas) if limpiar else [limpiar_texto(p) for p in paginas]
    return [
        Document(
            page_content=texto,
            metadata={
                "doc_id": kb.DOC_TERMINOS,
                "tipo": TIPO_TERMINOS,
                "fuente": ruta.name,
                "version": datos.get("version", ""),
                "vigente_desde": datos.get("vigente_desde", ""),
                "idioma": "es",
                "pagina": numero,
                "seccion": f"Términos y condiciones{kb.SEPARADOR_RUTA}página {numero}",
            },
        )
        for numero, texto in enumerate(textos, start=1)
        if texto
    ]


def cargar_todo(enriquecer_ingles: bool = False) -> list[Document]:
    """Los cuatro tipos de documento de la base de conocimiento."""
    return [
        *cargar_politicas(),
        *cargar_credito(),
        *cargar_catalogo(enriquecer_ingles),
        *cargar_terminos(),
    ]
