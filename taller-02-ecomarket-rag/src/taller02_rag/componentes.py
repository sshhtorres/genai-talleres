"""Arma las piezas (embeddings, base vectorial y LLM) desde la configuración activa.

Las opciones explícitas (`--embeddings`, `--proveedor`) tienen prioridad sobre `RAG_CONFIG`.
Con `backend="memoria"` la base se indexa al vuelo: sirve para tests, demostraciones sin Docker y
el notebook con el proveedor `fake`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from genai_common.configuraciones import ConfiguracionRAG, resolver_configuracion
from genai_common.embeddings import EmbeddingProfile, build_embeddings, get_embedding_profile
from genai_common.lc import FakeChatModel, chat_model_from_profile

from . import indexing
from .chunking import ESTRATEGIA_POR_DEFECTO
from .config import CACHE_DIR
from .store import AlmacenVectorial, crear_almacen


@dataclass
class Componentes:
    config: ConfiguracionRAG
    perfil_embeddings: EmbeddingProfile
    embeddings: Embeddings
    almacen: AlmacenVectorial


def perfil_embeddings(nombre: str | None = None) -> EmbeddingProfile:
    if nombre:
        return get_embedding_profile(nombre)
    return resolver_configuracion().embeddings


def armar_embeddings(perfil: EmbeddingProfile, cache: bool = True) -> Embeddings:
    return build_embeddings(perfil, cache_dir=CACHE_DIR if cache else None)


def armar_almacen(
    embeddings_nombre: str | None = None,
    backend: str = "pgvector",
    estrategia: str = ESTRATEGIA_POR_DEFECTO,
    sufijo: str = "",
) -> Componentes:
    """Base vectorial lista para consultar. En memoria, se indexa en el momento."""
    config = resolver_configuracion()
    perfil = perfil_embeddings(embeddings_nombre)
    embeddings = armar_embeddings(perfil)
    almacen = crear_almacen(
        embeddings, perfil, backend=backend, estrategia=estrategia, sufijo=sufijo
    )
    if backend == "memoria":
        indexing.indexar(almacen, indexing.preparar_chunks(estrategia), pausa_s=0)
    return Componentes(config, perfil, embeddings, almacen)


def armar_llm(
    proveedor: str | None = None,
    model_role: str | None = None,
    max_tokens: int = 600,
) -> BaseChatModel:
    """LLM de la configuración activa, o del proveedor indicado con su modelo por defecto/rol."""
    if proveedor:
        modelo = chat_model_from_profile(proveedor, model_role=model_role, max_tokens=max_tokens)
        return _fake_extractivo(modelo)
    config = resolver_configuracion()
    return _fake_extractivo(
        chat_model_from_profile(
            profile=config.llm,
            model=config.llm_model,
            model_role=None if config.llm_model else model_role,
            max_tokens=max_tokens,
        )
    )


_FRAGMENTO = re.compile(r'<fragmento fuente="([^"]+)"[^>]*>\s*(.*?)</fragmento>', re.DOTALL)


def respuesta_extractiva(prompt: str) -> str:
    """Respuesta del modelo falso: la primera frase del mejor fragmento, con su cita.

    No "entiende" nada, pero produce respuestas con la forma correcta (texto + [fuente]), así la
    CLI y el notebook muestran la cadena completa sin claves de API.
    """
    contexto = prompt[prompt.rfind("<contexto>") :]
    fragmentos = _FRAGMENTO.findall(contexto)
    if not fragmentos:
        return "No tengo información sobre eso en los documentos de EcoMarket."
    fuente, texto = fragmentos[0]
    cuerpo = texto.split("\n\n", 1)[-1].strip()
    frase = re.split(r"(?<=[.!?])\s", " ".join(cuerpo.split()), maxsplit=1)[0]
    return f"{frase} [{unescape(fuente)}]"


def _fake_extractivo(modelo: BaseChatModel) -> BaseChatModel:
    if isinstance(modelo, FakeChatModel):
        modelo.default = respuesta_extractiva
    return modelo
