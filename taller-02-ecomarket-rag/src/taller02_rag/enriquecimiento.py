"""Experimento E7: enriquecer las fichas en inglés con un resumen en español.

El resumen se genera UNA vez con el LLM y se guarda versionado en `data/kb/.enriquecido/<sku>.md`,
para que el experimento sea reproducible sin volver a llamar al modelo. Al indexar con
`--enriquecer-ingles`, el resumen se antepone al texto original (que no se reemplaza) y el
resultado va a una tabla aparte (`…_enriq`).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from genai_common import render

from . import kb
from .chains import cargar_prompts
from .config import KB_DIR

DIR_ENRIQUECIDO = KB_DIR / ".enriquecido"


def ruta_resumen(sku: str) -> Path:
    return DIR_ENRIQUECIDO / f"{sku}.md"


def leer_resumen(sku: str) -> str | None:
    ruta = ruta_resumen(sku)
    if not ruta.is_file():
        return None
    _, cuerpo = kb.front_matter(ruta.read_text(encoding="utf-8"))
    return cuerpo.strip()


def generar(llm: BaseChatModel, forzar: bool = False) -> list[tuple[str, str]]:
    """Genera los resúmenes que falten. Devuelve [(sku, "generado" | "ya existía")]."""
    from .loaders import serializar_producto

    prompts = cargar_prompts()["enriquecimiento"]
    DIR_ENRIQUECIDO.mkdir(parents=True, exist_ok=True)
    estado = []
    for fila in kb.catalogo():
        if fila["idioma"] != "en":
            continue
        if ruta_resumen(fila["sku"]).is_file() and not forzar:
            estado.append((fila["sku"], "ya existía"))
            continue
        mensajes = [
            SystemMessage(prompts["system"]),
            HumanMessage(render(prompts["user"], ficha=serializar_producto(fila))),
        ]
        resumen = StrOutputParser().invoke(llm.invoke(mensajes)).strip()
        modelo = getattr(llm, "model", None) or getattr(llm, "model_name", "?")
        ruta_resumen(fila["sku"]).write_text(
            f'---\nsku: {fila["sku"]}\nmodelo: "{modelo}"\nfecha: "{date.today().isoformat()}"\n'
            f"---\n\n{resumen}\n",
            encoding="utf-8",
        )
        estado.append((fila["sku"], "generado"))
    return estado
