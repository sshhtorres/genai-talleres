"""Cadena RAG con LCEL explícito: recuperar → formatear contexto → prompt → LLM → texto → validar.

No se usa `RetrievalQA`: cada eslabón es visible y sus resultados intermedios quedan en
`ResultadoRAG` (pregunta, chunks con *score*, prompt renderizado, respuesta, fuentes citadas, si se
abstuvo), en la línea de `ResultadoCadena` del Taller 1. Si el mejor chunk no supera el umbral, la
respuesta sale de código y **no se llama al LLM**.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import lru_cache
from html import escape
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable, RunnableLambda

from genai_common import load_prompts, render

from . import checks
from .config import PROMPTS_DIR
from .retrieval import ChunkRecuperado, Recuperacion, como_runnable, recuperar
from .store import AlmacenVectorial

VARIANTES = ("basico", "mejorado")


@lru_cache(maxsize=4)
def cargar_prompts(nombre: str = "rag") -> dict[str, Any]:
    return load_prompts(PROMPTS_DIR / f"{nombre}.toml")


@dataclass
class ResultadoRAG:
    """Respuesta final + trazabilidad completa de la cadena."""

    pregunta: str
    variante: str
    respuesta: str
    recuperacion: Recuperacion
    prompt: list[dict[str, str]] = field(default_factory=list)
    abstuvo_por_umbral: bool = False
    llamadas: int = 0
    checks: list[checks.Check] = field(default_factory=list)
    metadatos: dict[str, Any] = field(default_factory=dict)

    @property
    def fuentes_citadas(self) -> list[str]:
        return checks.citas(self.respuesta)

    @property
    def abstuvo(self) -> bool:
        return self.abstuvo_por_umbral or checks.es_abstencion(self.respuesta)

    @property
    def ok(self) -> bool:
        return all(ok for _, ok, _ in self.checks)

    def pasos(self) -> dict[str, Any]:
        """Resumen de los pasos intermedios, para la CLI, los reportes y el notebook."""
        return {
            "1_recuperacion": {
                "k": self.recuperacion.k,
                "filtro": self.recuperacion.filtro,
                "umbral": self.recuperacion.umbral,
                "mejor_score": self.recuperacion.mejor_score,
                "chunks": [c.resumen() for c in self.recuperacion.chunks],
            },
            "2_decision": (
                "sin evidencia: abstención desde código (no se llamó al LLM)"
                if self.abstuvo_por_umbral
                else "hay evidencia: se llama al LLM"
            ),
            "3_fuentes_citadas": self.fuentes_citadas,
            "4_validacion": checks.resumen(self.checks),
        }


# -- formateo ------------------------------------------------------------------------


def formatear_contexto(chunks: list[ChunkRecuperado], variante: str = "mejorado") -> str:
    """El "stuff" del RAG: pegar los chunks recuperados en un único bloque de texto.

    La variante mejorada delimita cada fragmento con su fuente e idioma para poder citarlo.
    La básica los pega uno tras otro, como el RetrievalQA del script de clase.
    """
    if variante == "basico":
        return "\n\n".join(c.texto for c in chunks)
    return "\n".join(
        f'<fragmento fuente="{escape(c.fuente)}" idioma="{c.idioma}">\n{c.texto}\n</fragmento>'
        for c in chunks
    )


def construir_mensajes(
    pregunta: str,
    chunks: list[ChunkRecuperado],
    variante: str = "mejorado",
    reglas_extra: str = "",
) -> list[BaseMessage]:
    """El prompt aumentado: instrucciones + fragmentos con su fuente + pregunta."""
    if variante not in VARIANTES:
        raise ValueError(f"Variante desconocida: '{variante}'. Disponibles: {VARIANTES}.")
    prompts = cargar_prompts()
    contexto = formatear_contexto(chunks, variante)
    if variante == "basico":
        return [
            HumanMessage(render(prompts["basico"]["user"], contexto=contexto, pregunta=pregunta))
        ]

    mejorado = prompts["mejorado"]
    mensajes: list[BaseMessage] = [SystemMessage(mejorado["system"] + reglas_extra)]
    for ejemplo in mejorado.get("ejemplos", []):
        mensajes += [HumanMessage(ejemplo["usuario"]), AIMessage(ejemplo["asistente"])]
    mensajes.append(HumanMessage(render(mejorado["user"], contexto=contexto, pregunta=pregunta)))
    return mensajes


def mensajes_como_texto(mensajes: list[BaseMessage]) -> list[dict[str, str]]:
    return [{"rol": m.type, "contenido": str(m.content)} for m in mensajes]


def mensaje_abstencion(pregunta: str) -> str:
    return cargar_prompts()["abstencion"][checks.detectar_idioma(pregunta)]


# -- cadenas LCEL ----------------------------------------------------------------------


def cadena_generacion(llm: BaseChatModel) -> Runnable:
    """prompt → LLM: recibe {"pregunta", "chunks", "variante", "reglas_extra"} y devuelve el
    AIMessage (con su uso de tokens). El texto se extrae después con StrOutputParser."""
    return RunnableLambda(lambda x: construir_mensajes(**x)) | llm


def cadena_rag_lcel(
    almacen: AlmacenVectorial,
    llm: BaseChatModel,
    variante: str = "mejorado",
    k: int | None = None,
) -> Runnable:
    """La cadena completa en una sola expresión LCEL, para explicarla eslabón por eslabón.

        pregunta ─► recuperador ─► formatear contexto + prompt ─► LLM ─► texto

    No aplica el umbral: es la versión "de libro" (como RetrievalQA, pero visible). `responder()`
    es la versión que se usa en el asistente, con umbral, validación y trazabilidad.
    """
    recuperador = como_runnable(almacen, k=k)
    return (
        recuperador
        | RunnableLambda(
            lambda r: construir_mensajes(r.pregunta, r.chunks, variante)  # type: ignore[attr-defined]
        )
        | llm
        | StrOutputParser()
    )


def responder(
    pregunta: str,
    almacen: AlmacenVectorial,
    llm: BaseChatModel,
    variante: str = "mejorado",
    k: int | None = None,
    filtro: dict[str, Any] | None = None,
    umbral: float | None = None,
    reglas_extra: str = "",
    es_credito: bool = False,
) -> ResultadoRAG:
    """Recupera, decide si hay evidencia, genera (solo si la hay) y valida."""
    recuperacion = recuperar(almacen, pregunta, k=k, filtro=filtro, umbral=umbral)

    if not recuperacion.hay_evidencia:
        respuesta = mensaje_abstencion(pregunta)
        resultado = ResultadoRAG(
            pregunta=pregunta,
            variante=variante,
            respuesta=respuesta,
            recuperacion=recuperacion,
            abstuvo_por_umbral=True,
            llamadas=0,
        )
        resultado.checks = checks.validar_rag(respuesta, pregunta, [], "", True)
        return resultado

    entrada = {
        "pregunta": pregunta,
        "chunks": recuperacion.chunks,
        "variante": variante,
        "reglas_extra": reglas_extra,
    }
    mensajes = construir_mensajes(**entrada)
    inicio = time.perf_counter()
    mensaje_ia = cadena_generacion(llm).invoke(entrada)
    latencia = time.perf_counter() - inicio
    respuesta = StrOutputParser().invoke(mensaje_ia).strip()

    contexto = formatear_contexto(recuperacion.chunks, variante)
    resultado = ResultadoRAG(
        pregunta=pregunta,
        variante=variante,
        respuesta=respuesta,
        recuperacion=recuperacion,
        prompt=mensajes_como_texto(mensajes),
        llamadas=1,
        metadatos=metadatos_de(mensaje_ia, llm, latencia),
    )
    resultado.checks = checks.validar_rag(
        respuesta, pregunta, recuperacion.fuentes, contexto, False, es_credito=es_credito
    )
    return resultado


def metadatos_de(mensaje: AIMessage, llm: BaseChatModel, latencia_s: float) -> dict[str, Any]:
    """Proveedor, modelo, latencia y tokens, con las mismas claves que los reportes del T1."""
    uso = getattr(mensaje, "usage_metadata", None) or {}
    modelo = (
        mensaje.response_metadata.get("model_name")
        or getattr(llm, "model_name", None)
        or getattr(llm, "model", "?")
    )
    return {
        "modelo": modelo,
        "latencia_s": round(latencia_s, 3),
        "tokens_entrada": uso.get("input_tokens"),
        "tokens_salida": uso.get("output_tokens"),
    }
