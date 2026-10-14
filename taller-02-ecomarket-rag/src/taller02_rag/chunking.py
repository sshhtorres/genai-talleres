"""Paso 3 de la indexación: dividir los documentos en chunks, la unidad de recuperación.

No hay una estrategia mejor en abstracto; hay una mejor para cada forma de documento:

- `fija(n)`: cada n caracteres, sin mirar el texto. Línea base del experimento E2.
- `recursiva`: separadores en orden (secciones, párrafos, frases). PDF de términos.
- `estructural`: por encabezados; cada pregunta frecuente es un chunk. Políticas y FAQ.
- `por_registro`: un registro = un chunk. Reglas de crédito y catálogo.
- `por_tipo`: despacha según el `tipo` del documento. La estrategia recomendada.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from . import kb
from .config import parametros
from .loaders import TIPO_CREDITO, TIPO_POLITICAS, TIPO_PRODUCTO, TIPO_TERMINOS

ESTRATEGIA_POR_DEFECTO = "por_tipo"
_ENCABEZADOS = [("#", "h1"), ("##", "h2"), ("###", "h3")]


def _parametros() -> dict:
    return parametros()["chunking"]


def estrategias_disponibles() -> list[str]:
    return [ESTRATEGIA_POR_DEFECTO, *_parametros()["fijas"]]


def slug(texto: str) -> str:
    """Primera palabra en minúsculas y sin tildes: 'Devoluciones y garantías' -> 'devoluciones'."""
    plano = unicodedata.normalize("NFKD", texto.split()[0].lower())
    return "".join(c for c in plano if not unicodedata.combining(c))


# -- estrategias ------------------------------------------------------------------


def fija(documentos: list[Document], tamano: int) -> list[Document]:
    """Corta cada documento cada `tamano` caracteres, sin solapamiento ni respeto por el texto.

    Los registros de un mismo documento (reglas, fichas, páginas) se unen antes de cortar, como si
    el archivo se hubiera tratado como texto plano. Es lo que hace un pipeline ingenuo.
    """
    salida: list[Document] = []
    for grupo in _agrupar_por_documento(documentos):
        texto = "\n\n".join(d.page_content for d in grupo)
        base = _metadatos_comunes(grupo)
        for inicio in range(0, len(texto), tamano):
            trozo = texto[inicio : inicio + tamano].strip()
            if trozo:
                salida.append(Document(page_content=trozo, metadata=dict(base)))
    return salida


def recursiva(documentos: list[Document]) -> list[Document]:
    """RecursiveCharacterTextSplitter con los parámetros de parametros.toml."""
    p = _parametros()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=p["chunk_size"],
        chunk_overlap=p["chunk_overlap"],
        separators=p["separadores"],
        keep_separator=True,
    )
    return [d for d in splitter.split_documents(documentos) if d.page_content.strip()]


def estructural(documentos: list[Document]) -> list[Document]:
    """Por encabezados (#, ##, ###) y recursivo dentro de las secciones demasiado largas.

    La ruta de encabezados se antepone al texto que se embebe ("Envíos › Costos de envío"): un chunk
    que dice "no aplica en estos casos" sin su título es irrecuperable. También se guarda en los
    metadatos `seccion`, `area` (para filtrar) y `es_faq`.
    """
    p = _parametros()
    por_encabezados = MarkdownHeaderTextSplitter(_ENCABEZADOS, strip_headers=True)
    salida: list[Document] = []
    for documento in documentos:
        for seccion in por_encabezados.split_text(documento.page_content):
            ruta = [seccion.metadata[n] for _, n in _ENCABEZADOS if n in seccion.metadata]
            if not ruta or not seccion.page_content.strip():
                continue
            nombre = kb.SEPARADOR_RUTA.join(ruta)
            cabecera = f"{nombre}\n\n"
            # El cuerpo se divide con el presupuesto que deja la cabecera: el chunk final, con la
            # ruta incluida, respeta chunk_size.
            presupuesto = max(p["chunk_size"] - len(cabecera), 200)
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=presupuesto,
                chunk_overlap=min(p["chunk_overlap"], presupuesto // 4),
                separators=p["separadores"],
                keep_separator=True,
            )
            metadatos = {
                **documento.metadata,
                "seccion": nombre,
                "area": slug(ruta[0]),
                "es_faq": len(ruta) >= 2 and ruta[1] == "Preguntas frecuentes",
            }
            for trozo in splitter.split_text(seccion.page_content.strip()):
                salida.append(Document(page_content=cabecera + trozo, metadata=dict(metadatos)))
    return salida


def por_registro(documentos: list[Document]) -> list[Document]:
    """Cada registro ya es un chunk: no se divide ni se mezcla con otro."""
    return [Document(page_content=d.page_content, metadata=dict(d.metadata)) for d in documentos]


_POR_TIPO: dict[str, Callable[[list[Document]], list[Document]]] = {
    TIPO_POLITICAS: estructural,
    TIPO_CREDITO: por_registro,
    TIPO_PRODUCTO: por_registro,
    TIPO_TERMINOS: recursiva,
}


def por_tipo(documentos: list[Document]) -> list[Document]:
    """La estrategia recomendada: cada tipo de documento con la suya."""
    salida: list[Document] = []
    for tipo, funcion in _POR_TIPO.items():
        salida += funcion([d for d in documentos if d.metadata["tipo"] == tipo])
    return salida


def dividir(documentos: list[Document], estrategia: str = ESTRATEGIA_POR_DEFECTO) -> list[Document]:
    """Aplica una estrategia por nombre: `por_tipo` o una fija de parametros.toml (`fija300`…)."""
    fijas = _parametros()["fijas"]
    if estrategia == "por_tipo":
        chunks = por_tipo(documentos)
    elif estrategia in fijas:
        chunks = fija(documentos, fijas[estrategia])
    else:
        raise ValueError(
            f"Estrategia desconocida: '{estrategia}'. Disponibles: {estrategias_disponibles()}."
        )
    for chunk in chunks:
        chunk.metadata["estrategia"] = estrategia
        chunk.metadata.setdefault("area", "")
        chunk.metadata.setdefault("es_faq", False)
    return chunks


# -- utilidades ---------------------------------------------------------------------


def _agrupar_por_documento(documentos: list[Document]) -> list[list[Document]]:
    grupos: dict[str, list[Document]] = {}
    for documento in documentos:
        grupos.setdefault(documento.metadata["doc_id"], []).append(documento)
    return list(grupos.values())


def _metadatos_comunes(grupo: list[Document]) -> dict:
    """Metadatos que valen para todo el documento (no los de un registro o página concretos)."""
    claves = ("doc_id", "tipo", "fuente", "version")
    base = {k: grupo[0].metadata[k] for k in claves if k in grupo[0].metadata}
    # El idioma solo se conserva si todo el documento lo comparte; el catálogo es bilingüe y un
    # chunk de tamaño fijo puede mezclar fichas de los dos idiomas.
    idiomas = {d.metadata.get("idioma", "es") for d in grupo}
    base["idioma"] = idiomas.pop() if len(idiomas) == 1 else "mixto"
    return base


def tokens_aproximados(texto: str) -> int:
    """Estimación barata: ~4 caracteres por token en español."""
    return max(1, round(len(re.sub(r"\s+", " ", texto)) / 4))
