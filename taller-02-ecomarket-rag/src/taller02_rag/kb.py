"""Lectura de la base de conocimiento sintética (data/kb/) y del set de evaluación.

Funciones puras y sin LangChain: las usan los loaders, los tests de integridad y la evaluación.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .config import EVAL_DIR, KB_DIR

DOC_POLITICAS = "politicas-y-faq"
DOC_CREDITO = "reglas-credito"
DOC_CATALOGO = "catalogo"
DOC_TERMINOS = "terminos-y-condiciones"
DOCUMENTOS = (DOC_POLITICAS, DOC_CREDITO, DOC_CATALOGO, DOC_TERMINOS)

SEPARADOR_RUTA = " › "

_ENCABEZADO = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def front_matter(texto: str) -> tuple[dict[str, str], str]:
    """Separa el front matter sencillo (clave: valor) del cuerpo de un Markdown."""
    if not texto.startswith("---"):
        return {}, texto
    _, cabecera, cuerpo = texto.split("---", 2)
    datos: dict[str, str] = {}
    for linea in cabecera.strip().splitlines():
        clave, _, valor = linea.partition(":")
        datos[clave.strip()] = valor.strip().strip('"')
    return datos, cuerpo.lstrip("\n")


@dataclass(frozen=True)
class Seccion:
    """Una sección de un Markdown: la ruta de encabezados y el texto que va debajo."""

    ruta: tuple[str, ...]
    cuerpo: str

    @property
    def nombre(self) -> str:
        return SEPARADOR_RUTA.join(self.ruta)


def secciones_markdown(cuerpo: str) -> list[Seccion]:
    """Secciones con texto propio, en orden. Las que solo agrupan subsecciones no se devuelven."""
    secciones: list[Seccion] = []
    ruta: list[str] = []
    lineas: list[str] = []

    def cerrar() -> None:
        texto = "\n".join(lineas).strip()
        if texto and ruta:
            secciones.append(Seccion(tuple(ruta), texto))
        lineas.clear()

    for linea in cuerpo.splitlines():
        coincidencia = _ENCABEZADO.match(linea)
        if coincidencia:
            cerrar()
            nivel = len(coincidencia.group(1))
            ruta[:] = [*ruta[: nivel - 1], coincidencia.group(2)]
        else:
            lineas.append(linea)
    cerrar()
    return secciones


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios colapsados: para comparar texto entre formatos."""
    plano = unicodedata.normalize("NFKD", texto.lower())
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", plano).strip()


# -- carga de cada documento ----------------------------------------------------


@lru_cache(maxsize=1)
def politicas() -> tuple[dict[str, str], list[Seccion]]:
    datos, cuerpo = front_matter((KB_DIR / "politicas-y-faq.md").read_text(encoding="utf-8"))
    return datos, secciones_markdown(cuerpo)


@lru_cache(maxsize=1)
def reglas_credito() -> dict[str, Any]:
    return json.loads((KB_DIR / "reglas-credito.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def catalogo() -> list[dict[str, str]]:
    with (KB_DIR / "catalogo.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@lru_cache(maxsize=1)
def terminos_fuente() -> tuple[dict[str, str], list[Seccion]]:
    """Fuente en Markdown del PDF de términos (el PDF se genera desde aquí)."""
    ruta = KB_DIR / "fuentes" / "terminos-y-condiciones.md"
    datos, cuerpo = front_matter(ruta.read_text(encoding="utf-8"))
    return datos, secciones_markdown(cuerpo)


def unidad(doc_id: str, seccion_o_id: str) -> str | None:
    """Texto de la unidad que un caso de evaluación espera recuperar, o None si no existe.

    - políticas: la sección por su ruta completa ("Envíos › Cobertura").
    - crédito: la regla por su id ("CR-05").
    - catálogo: la ficha por su sku ("P-106").
    - términos: la sección por su título ("5. Facturación electrónica").
    """
    if doc_id == DOC_POLITICAS:
        return next((s.cuerpo for s in politicas()[1] if s.nombre == seccion_o_id), None)
    if doc_id == DOC_CREDITO:
        regla = next((r for r in reglas_credito()["reglas"] if r["id"] == seccion_o_id), None)
        return " ".join(str(v) for v in regla.values()) if regla else None
    if doc_id == DOC_CATALOGO:
        fila = next((f for f in catalogo() if f["sku"] == seccion_o_id), None)
        return " ".join(fila.values()) if fila else None
    if doc_id == DOC_TERMINOS:
        return next((s.cuerpo for s in terminos_fuente()[1] if s.ruta[-1] == seccion_o_id), None)
    return None


@lru_cache(maxsize=1)
def casos_rag() -> list[dict[str, Any]]:
    """Casos del set de evaluación (data/eval/casos_rag.jsonl)."""
    lineas = (EVAL_DIR / "casos_rag.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(linea) for linea in lineas if linea.strip()]
