"""Arma las piezas (embeddings, base vectorial y LLM) desde la configuración activa.

Las opciones explícitas (`--embeddings`, `--proveedor`) tienen prioridad sobre `RAG_CONFIG`.
Con `backend="memoria"` la base se indexa al vuelo: sirve para tests, demostraciones sin Docker y
el notebook con el proveedor `fake`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from genai_common import FakeLLMClient, LLMClient
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
        chunks = indexing.preparar_chunks(estrategia, enriquecer_ingles=sufijo == "enriq")
        indexing.indexar(almacen, chunks, pausa_s=0)
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


_PALABRAS_RUTA = (
    ("credito", ("cuota", "credito", "crédito", "financ", "endeud", "mora", "cupo")),
    ("devolucion", ("devolver", "devolución", "devolucion", "reembolso", "garantía", "roto")),
    (
        "consulta_general",
        (
            "envío",
            "envio",
            "pago",
            "cupón",
            "cupon",
            "factura",
            "producto",
            "envase",
            "empaque",
            "cuenta",
            "datos",
            "botella",
            "café",
            "cafe",
        ),
    ),
)


def respuesta_falsa(prompt: str) -> str:
    """Modelo falso para la demo sin claves: clasifica por palabras clave si es el router y, si
    no, responde de forma extractiva."""
    if "Clasifica el mensaje." in prompt:
        mensaje = prompt[prompt.rfind("<mensaje>") :].lower()
        for intencion, palabras in _PALABRAS_RUTA:
            if any(p in mensaje for p in palabras):
                return json.dumps({"intencion": intencion})
        return json.dumps({"intencion": "fuera_de_alcance"})
    return respuesta_extractiva(prompt)


def _fake_extractivo(modelo: BaseChatModel) -> BaseChatModel:
    if isinstance(modelo, FakeChatModel):
        modelo.default = respuesta_falsa
    return modelo


def _bloque(prompt: str, etiqueta: str) -> str:
    """Contenido de la última etiqueta que abre línea (no cuentan las menciones en las reglas)."""
    inicio = prompt.rfind(f"<{etiqueta}>\n")
    fin = prompt.find(f"</{etiqueta}>", inicio)
    return prompt[inicio + len(etiqueta) + 3 : fin] if inicio != -1 and fin != -1 else ""


def _respuesta_falsa_t1(prompt: str) -> str:
    """Cliente falso de las cadenas del Taller 1: JSON vacío en los pasos estructurados (el código
    del T1 cae en sus reglas) y una redacción que repite la decisión o el estado verificados."""
    if "Devuelve SOLO un objeto JSON" in prompt:
        return "{}"
    decision = _bloque(prompt, "decision_verificada")
    if decision:
        datos = json.loads(decision)
        return f"(respuesta simulada) Decisión: {datos.get('elegible')}. {datos.get('motivo', '')}"
    pedidos = _bloque(prompt, "pedidos")
    estado = re.search(r'"estado": "(\w+)"', pedidos)
    enlace = re.search(r'"link_rastreo": "([^"]+)"', pedidos)
    if estado:
        partes = [f"(respuesta simulada) Su pedido está en estado {estado.group(1)}."]
        if enlace:
            partes.append(f"Puede rastrearlo aquí: {enlace.group(1)}")
        return " ".join(partes)
    return "(respuesta simulada)"


def armar_cliente_t1(proveedor: str | None = None) -> LLMClient:
    """Cliente de las cadenas del Taller 1 (endpoint compatible con OpenAI), con el mismo
    proveedor y modelo que la configuración activa."""
    if proveedor:
        cliente = LLMClient.from_profile(proveedor)
    else:
        config = resolver_configuracion()
        cliente = LLMClient.from_profile(config.llm.name, model=config.llm_model)
    if isinstance(cliente, FakeLLMClient):
        cliente.default = _respuesta_falsa_t1
    return cliente
