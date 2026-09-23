"""Carga de prompts en TOML y renderizado de plantillas {{variable}}."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

_VARIABLE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


class PromptError(RuntimeError):
    """Plantilla mal formada o variable sin valor."""


def load_prompts(path: str | Path) -> dict[str, Any]:
    """Carga un archivo de prompts TOML."""
    ruta = Path(path)
    if not ruta.is_file():
        raise PromptError(f"No existe el archivo de prompts: {ruta}")
    with ruta.open("rb") as fh:
        return tomllib.load(fh)


def render(template: str, **variables: Any) -> str:
    """Reemplaza {{variable}} y falla si queda alguna sin valor."""
    faltantes: list[str] = []

    def _sub(match: re.Match[str]) -> str:
        nombre = match.group(1)
        if nombre not in variables:
            faltantes.append(nombre)
            return match.group(0)
        return str(variables[nombre])

    resultado = _VARIABLE.sub(_sub, template)
    if faltantes:
        raise PromptError(
            f"Variables sin valor en la plantilla: {', '.join(sorted(set(faltantes)))}"
        )
    return resultado


def variables_of(template: str) -> set[str]:
    """Nombres de las variables que usa una plantilla."""
    return {m.group(1) for m in _VARIABLE.finditer(template)}
