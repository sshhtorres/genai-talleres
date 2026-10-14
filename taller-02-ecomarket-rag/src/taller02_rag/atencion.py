"""Punto de entrada único del asistente: router → cadena de la ruta → validación.

- `estado_pedido`: cadena del Taller 1. Es un dato transaccional: se consulta, no se recupera.
- `devolucion`: cadena del Taller 1 con la política RECUPERADA por el RAG (filtro
  `area=devoluciones`); la decisión sigue saliendo de `evaluar_devolucion()`.
- `credito`: cadena RAG filtrada a las reglas de crédito, con las reglas de "no decidir".
- `consulta_general`: cadena RAG sobre toda la base.
- `fuera_de_alcance`: respuesta desde código, sin LLM.

Las cadenas del Taller 1 se importan, no se copian: usan `LLMClient` (endpoint compatible con
OpenAI), mientras que el router y el RAG usan los modelos nativos de LangChain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from genai_common import LLMClient
from taller01 import chains as t1_chains

from . import checks, router
from .chains import ResultadoRAG, cargar_prompts, formatear_contexto, responder
from .retrieval import recuperar
from .store import AlmacenVectorial

FILTRO_DEVOLUCIONES = {"area": "devoluciones"}
FILTRO_CREDITO = {"tipo": "credito"}


@dataclass
class ResultadoAtencion:
    mensaje: str
    ruta: str
    clasificacion: router.Clasificacion
    respuesta: str
    checks: list[checks.Check] = field(default_factory=list)
    fuentes: list[str] = field(default_factory=list)
    llamadas: int = 0
    pasos: dict[str, Any] = field(default_factory=dict)
    metadatos: dict[str, Any] = field(default_factory=dict)
    detalle: Any = None  # ResultadoRAG o ResultadoCadena del Taller 1

    @property
    def ok(self) -> bool:
        return all(ok for _, ok, _ in self.checks)


def atender(
    mensaje: str,
    almacen: AlmacenVectorial,
    llm: BaseChatModel,
    cliente_t1: LLMClient,
    llm_router: BaseChatModel | None = None,
    variante: str = "mejorado",
    k: int | None = None,
) -> ResultadoAtencion:
    """Clasifica el mensaje y lo atiende con la cadena de su ruta."""
    clasificacion = router.clasificar(mensaje, llm_router or llm)
    ruta = clasificacion.intencion
    base = {"0_router": clasificacion.resumen()}

    if ruta == "estado_pedido":
        # contexto="registro": solo el pedido consultado llega al prompt (la mejora del Taller 1
        # frente a pegar todos los pedidos, que filtraba datos de otros clientes).
        r = t1_chains.consultar_pedido(mensaje, cliente_t1, variante=variante, contexto="registro")
        return _desde_t1(mensaje, ruta, clasificacion, r, base, [])

    if ruta == "devolucion":
        politica = recuperar(almacen, mensaje, k=k, filtro=FILTRO_DEVOLUCIONES, umbral=0.0)
        r = t1_chains.gestionar_devolucion(
            mensaje,
            cliente_t1,
            tracking=clasificacion.trackings[0] if clasificacion.trackings else None,
            variante=variante,
            politica=formatear_contexto(politica.chunks),
        )
        base["politica_recuperada"] = [c.resumen() for c in politica.chunks]
        return _desde_t1(mensaje, ruta, clasificacion, r, base, politica.fuentes)

    if ruta == "credito":
        r = responder(
            mensaje,
            almacen,
            llm,
            variante=variante,
            k=k,
            filtro=FILTRO_CREDITO,
            reglas_extra=cargar_prompts()["credito"]["reglas"],
            es_credito=True,
        )
        extra = [] if r.abstuvo else checks.validar_credito(r.respuesta)
        return _desde_rag(mensaje, ruta, clasificacion, r, base, extra)

    if ruta == "consulta_general":
        r = responder(mensaje, almacen, llm, variante=variante, k=k)
        return _desde_rag(mensaje, ruta, clasificacion, r, base, [])

    respuesta = router.cargar_prompts()["fuera_de_alcance"][checks.detectar_idioma(mensaje)]
    return ResultadoAtencion(
        mensaje=mensaje,
        ruta=ruta,
        clasificacion=clasificacion,
        respuesta=respuesta,
        llamadas=clasificacion.llamadas,
        pasos={**base, "1_respuesta": "desde código: fuera de alcance (no se llamó al LLM)"},
    )


def _desde_rag(mensaje, ruta, clasificacion, r: ResultadoRAG, base, extra) -> ResultadoAtencion:
    return ResultadoAtencion(
        mensaje=mensaje,
        ruta=ruta,
        clasificacion=clasificacion,
        respuesta=r.respuesta,
        checks=r.checks + extra,
        fuentes=r.recuperacion.fuentes,
        llamadas=clasificacion.llamadas + r.llamadas,
        pasos={**base, **r.pasos()},
        metadatos=r.metadatos,
        detalle=r,
    )


def _desde_t1(mensaje, ruta, clasificacion, r, base, fuentes) -> ResultadoAtencion:
    return ResultadoAtencion(
        mensaje=mensaje,
        ruta=ruta,
        clasificacion=clasificacion,
        respuesta=r.respuesta,
        checks=list(r.checks),
        fuentes=fuentes,
        llamadas=clasificacion.llamadas + r.llamadas,
        pasos={**base, **r.pasos},
        metadatos=r.metadatos,
        detalle=r,
    )
