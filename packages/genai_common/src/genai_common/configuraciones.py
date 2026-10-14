"""Configuraciones de ejecución del RAG: `nube`, `hibrida`, `local` (y `pruebas`, sin red).

Es el único lugar que decide qué proveedores se usan. Lee `RAG_CONFIG`, `RAG_LLM` y `LOCAL_TIER`
del entorno (o del .env) y las secciones `[configuraciones.*]` y `[niveles.*]` de providers.toml.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ConfigError, ProviderProfile, _load_raw, find_repo_root, get_profile, load_env
from .embeddings import EmbeddingProfile, get_embedding_profile


@dataclass(frozen=True)
class ConfiguracionRAG:
    """Perfiles efectivos de una configuración de ejecución."""

    nombre: str
    embeddings: EmbeddingProfile
    llm: ProviderProfile
    llm_model: str | None = None  # None = el modelo por defecto del perfil
    nivel: str | None = None
    nivel_por_defecto: bool = False  # True si LOCAL_TIER no estaba definido
    descripcion: str = ""

    @property
    def tabla(self) -> str:
        return self.embeddings.table_name


def _secciones(root: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    crudo = _load_raw(str(root))
    return crudo.get("configuraciones", {}), crudo.get("niveles", {}), crudo.get("rag_default", "")


def listar_configuraciones(root: Path | None = None) -> list[str]:
    raiz = root or find_repo_root()
    configuraciones, _, _ = _secciones(raiz)
    return list(configuraciones)


def listar_niveles(root: Path | None = None) -> dict[str, dict[str, Any]]:
    raiz = root or find_repo_root()
    _, niveles, _ = _secciones(raiz)
    return dict(niveles)


def resolver_configuracion(
    nombre: str | None = None,
    llm: str | None = None,
    nivel: str | None = None,
    root: Path | None = None,
) -> ConfiguracionRAG:
    """Resuelve la configuración activa. Los argumentos tienen prioridad sobre el entorno.

    - `nube`: embeddings y LLM de Gemini.
    - `hibrida`: embeddings locales (Ollama) + LLM en la nube elegido con `RAG_LLM`.
    - `local`: todo en Ollama; el modelo de chat lo fija el nivel de hardware (`LOCAL_TIER`).
    """
    raiz = root or find_repo_root()
    load_env(raiz)
    configuraciones, niveles, por_defecto = _secciones(raiz)

    elegido = nombre or os.getenv("RAG_CONFIG") or por_defecto
    if elegido not in configuraciones:
        raise ConfigError(
            f"Configuración RAG desconocida: '{elegido}'. Define RAG_CONFIG en .env con una de: "
            f"{', '.join(configuraciones)}."
        )
    datos = configuraciones[elegido]
    embeddings = get_embedding_profile(datos["embeddings"], raiz)

    llm_permitidos = list(datos.get("llm_opciones", []))
    if llm_permitidos:
        nombre_llm = llm or os.getenv("RAG_LLM") or ""
        if nombre_llm not in llm_permitidos:
            raise ConfigError(
                f"La configuración '{elegido}' necesita elegir el LLM: define RAG_LLM en .env con "
                f"uno de: {', '.join(llm_permitidos)}."
                + (f" (valor actual: '{nombre_llm}')" if nombre_llm else "")
            )
    else:
        nombre_llm = llm or datos["llm"]
    perfil_llm = get_profile(nombre_llm, raiz)

    llm_model: str | None = None
    rol = dict(datos.get("rol_llm", {})).get(perfil_llm.name)
    if rol:
        llm_model = perfil_llm.model_for(rol)

    nivel_elegido: str | None = None
    nivel_explicito = bool(nivel or os.getenv("LOCAL_TIER"))
    if datos.get("usa_niveles"):
        nivel_elegido = nivel or os.getenv("LOCAL_TIER") or datos.get("nivel_por_defecto", "")
        if nivel_elegido not in niveles:
            raise ConfigError(
                f"Nivel de hardware desconocido: '{nivel_elegido}'. Define LOCAL_TIER en .env "
                f"con uno de: {', '.join(niveles)}. `taller02 proveedores --recomendar` sugiere "
                "uno según la RAM del equipo."
            )
        llm_model = niveles[nivel_elegido]["llm_model"]

    return ConfiguracionRAG(
        nombre=elegido,
        embeddings=embeddings,
        llm=perfil_llm,
        llm_model=llm_model,
        nivel=nivel_elegido,
        nivel_por_defecto=bool(nivel_elegido) and not nivel_explicito,
        descripcion=datos.get("descripcion", ""),
    )


def recomendar_nivel(ram_gb: float, root: Path | None = None) -> str | None:
    """Nivel de CPU más exigente cuya RAM mínima cabe en el equipo. No mira la GPU a propósito.

    Se tolera un 10%: un equipo "de 16 GB" reporta unos 15,5 GB porque parte la reserva el sistema.
    """
    candidatos = [
        (datos["ram_min_gb"], nombre)
        for nombre, datos in listar_niveles(root).items()
        if datos.get("ram_min_gb") is not None and ram_gb >= 0.9 * datos["ram_min_gb"]
    ]
    return max(candidatos)[1] if candidatos else None
