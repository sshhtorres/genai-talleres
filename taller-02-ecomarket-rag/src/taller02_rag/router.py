"""Router de intención: decide qué cadena atiende cada mensaje.

Dos pasos, del más barato al más caro:

1. **Reglas en código, sin LLM.** Si el mensaje trae un número de seguimiento `ECO-xxxx`, es un
   dato transaccional: va a la cadena de pedido del Taller 1, o a la de devolución si además habla
   de devolver, reembolsar o de un producto dañado. No se gasta la llamada del router.
2. **Clasificación con el LLM** (modelo del rol `router`), con salida JSON validada y un reintento
   de corrección, el mismo patrón que `chat_json()` del Taller 1. Si la etiqueta no es válida, el
   mensaje se trata como fuera de alcance: ante la duda, no se improvisa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from genai_common import load_prompts, render
from genai_common.lc import invoke_json
from taller01 import chains as t1_chains
from taller01 import data as t1

from .config import PROMPTS_DIR

INTENCIONES = ("estado_pedido", "devolucion", "credito", "consulta_general", "fuera_de_alcance")

_SENALES_DEVOLUCION = re.compile(
    r"\b(devol\w*|devuelv\w*|reembols\w*|retract\w*|garant[ií]a\w*|cambiar\s+(el|la|los|las)\s+"
    r"producto\w*|return\w*|refund\w*)\b",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def cargar_prompts() -> dict[str, Any]:
    return load_prompts(PROMPTS_DIR / "router.toml")


@dataclass
class Clasificacion:
    intencion: str
    origen: str  # "tracking" | "llm" | "respaldo" | "rescate_rag" (ver atencion.py)
    trackings: list[str] = field(default_factory=list)
    llamadas: int = 0
    intentos: list[str] = field(default_factory=list)
    respuestas: list[AIMessage] = field(default_factory=list, repr=False)

    def resumen(self) -> dict[str, Any]:
        return {
            "intencion": self.intencion,
            "origen": self.origen,
            "trackings": self.trackings,
            "llamadas": self.llamadas,
            "intentos": self.intentos,
        }


def habla_de_devolucion(mensaje: str) -> bool:
    return bool(_SENALES_DEVOLUCION.search(mensaje) or t1_chains._SENALES_DEFECTO.search(mensaje))


def construir_mensajes(mensaje: str) -> list[BaseMessage]:
    prompts = cargar_prompts()
    mensajes: list[BaseMessage] = [SystemMessage(prompts["system"])]
    for ejemplo in prompts.get("ejemplos", []):
        mensajes += [
            HumanMessage(render(prompts["user"], mensaje=ejemplo["mensaje"])),
            AIMessage(ejemplo["salida"]),
        ]
    mensajes.append(HumanMessage(render(prompts["user"], mensaje=mensaje)))
    return mensajes


def clasificar(mensaje: str, llm: BaseChatModel) -> Clasificacion:
    """Intención del mensaje. Con tracking no se llama al LLM."""
    trackings = t1.extraer_trackings(mensaje)
    if trackings:
        intencion = "devolucion" if habla_de_devolucion(mensaje) else "estado_pedido"
        return Clasificacion(intencion, "tracking", trackings)

    datos, intentos, respuestas = invoke_json(
        llm, construir_mensajes(mensaje), required_keys=("intencion",)
    )
    intencion = str((datos or {}).get("intencion", "")).strip().lower()
    if intencion in INTENCIONES:
        return Clasificacion(intencion, "llm", [], len(intentos), intentos, respuestas)
    return Clasificacion("fuera_de_alcance", "respaldo", [], len(intentos), intentos, respuestas)
