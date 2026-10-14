"""Modelos de chat de LangChain construidos desde los perfiles de providers.toml.

Es el equivalente de `LLMClient.from_profile` para las cadenas LCEL del Taller 2, pero con la
**integración nativa de LangChain para cada proveedor** (`ChatGoogleGenerativeAI`, `ChatAnthropic`,
`ChatOllama`), no con el endpoint compatible con OpenAI que usa el Taller 1. LangChain es la capa
agnóstica: las cadenas solo ven un `BaseChatModel`, y qué clase se instancia lo decide la sección
`[providers.<nombre>.langchain]` de providers.toml.

Por qué nativo y no compatible: la verificación local mostró que, por la capa compatible de
Anthropic, el pensamiento adaptativo de Haiku 5.5 da 400 y `reasoning_effort` se ignora; con
`ChatAnthropic` ambos se controlan. Lo mismo con el razonamiento de Gemma 4 en `ChatOllama`.

Se mantienen las reglas del Taller 1: perfiles `por_implementar` bloqueados, `omit_params`,
`params` por proveedor, `max_tokens_min` y claves con errores accionables.
Requiere el extra `langchain` de genai-common.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from .config import ConfigError, ProviderProfile, get_profile
from .llm import _extraer_json

# Cada integración nombra distinto los mismos conceptos. Esta tabla es lo único que el código sabe
# de cada una; los valores concretos (modelos, parámetros) viven en providers.toml.
_INTEGRACIONES: dict[str, dict[str, str]] = {
    "google_genai": {"max_tokens": "max_output_tokens", "api_key": "google_api_key"},
    "anthropic": {"max_tokens": "max_tokens", "api_key": "api_key"},
    "ollama": {"max_tokens": "num_predict", "api_key": ""},
}


def _clase(integracion: str) -> type[BaseChatModel]:
    if integracion == "google_genai":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI
    if integracion == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic
    if integracion == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama
    raise ConfigError(
        f"Integración de LangChain desconocida: '{integracion}'. "
        f"Disponibles: {', '.join(_INTEGRACIONES)}."
    )


def chat_model_from_profile(
    name: str | None = None,
    model_role: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 800,
    profile: ProviderProfile | None = None,
) -> BaseChatModel:
    """Modelo de chat nativo de LangChain para un perfil de providers.toml.

    `model` tiene prioridad sobre `model_role`; si no se da ninguno, se usa el modelo por defecto
    del perfil. Con el perfil `fake` devuelve un `FakeChatModel` (sin red).
    """
    perfil = profile or get_profile(name)
    if perfil.name == "fake":
        return FakeChatModel()
    if perfil.status == "por_implementar":
        raise ConfigError(
            f"El proveedor '{perfil.name}' está marcado como 'por_implementar' en providers.toml "
            "y no ha sido probado. Pruébalo manualmente y cambia su estado a 'implementado'."
        )
    nativo = dict(perfil.extra.get("langchain", {}))
    integracion = nativo.get("integracion", "")
    if integracion not in _INTEGRACIONES:
        raise ConfigError(
            f"El proveedor '{perfil.name}' no declara su integración de LangChain: añade "
            f"[providers.{perfil.name}.langchain] con integracion = "
            f"{' | '.join(repr(i) for i in _INTEGRACIONES)} en providers.toml."
        )
    nombres = _INTEGRACIONES[integracion]

    argumentos: dict[str, Any] = {
        "model": model or perfil.model_for(model_role),
        "temperature": temperature,
        # Los modelos que razonan gastan parte de max_tokens pensando: el perfil fija un mínimo.
        nombres["max_tokens"]: max(max_tokens, int(perfil.extra.get("max_tokens_min", 0))),
    }
    if nombres["api_key"]:
        argumentos[nombres["api_key"]] = perfil.api_key()
    if nativo.get("base_url"):
        argumentos["base_url"] = nativo["base_url"]
    if integracion != "ollama":
        argumentos["max_retries"] = 6
    # Mismo contrato que LLMClient: cada proveedor declara qué parámetros rechaza y cuáles añade.
    for parametro in [*perfil.extra.get("omit_params", []), *nativo.get("omit_params", [])]:
        argumentos.pop(parametro, None)
    argumentos.update(nativo.get("params", {}))
    return _clase(integracion)(**argumentos)


def invoke_json(
    llm: BaseChatModel,
    mensajes: list[BaseMessage],
    required_keys: tuple[str, ...] = (),
) -> tuple[dict[str, Any] | None, list[str], list[AIMessage]]:
    """Como `LLMClient.chat_json()` pero con un modelo de LangChain: exige un objeto JSON con
    `required_keys` y, si no llega, reintenta una vez pidiendo la corrección.

    Devuelve (datos o None, textos crudos de cada intento, mensajes del modelo).
    """
    respuesta = llm.invoke(mensajes)
    texto = StrOutputParser().invoke(respuesta)
    intentos, respuestas = [texto], [respuesta]
    datos = _extraer_json(texto, required_keys)
    if datos is None:
        correccion = [
            *mensajes,
            AIMessage(texto),
            HumanMessage(
                "Tu respuesta no fue un objeto JSON válido con las claves "
                f"{list(required_keys) or 'requeridas'}. Responde de nuevo con SOLO el objeto "
                "JSON, sin texto adicional ni bloques de código."
            ),
        ]
        respuesta = llm.invoke(correccion)
        texto = StrOutputParser().invoke(respuesta)
        intentos.append(texto)
        respuestas.append(respuesta)
        datos = _extraer_json(texto, required_keys)
    return datos, intentos, respuestas


Rule = tuple[str, str]  # (patrón regex sobre el prompt, respuesta)


class FakeChatModel(BaseChatModel):
    """Modelo de chat falso, determinista y sin red, con reglas patrón -> respuesta.

    Es el FakeLLMClient del Taller 1 con la interfaz de LangChain: se puede usar dentro de una
    cadena LCEL y registra cada prompt recibido en `calls` para que los tests lo inspeccionen.
    """

    rules: list[Rule] = Field(default_factory=list)
    default: str | Callable[[str], str] = "Respuesta falsa por defecto."
    calls: list[list[BaseMessage]] = Field(default_factory=list)
    model_name: str = "fake-determinista"

    @property
    def _llm_type(self) -> str:
        return "fake-reglas"

    def add_rule(self, pattern: str, response: str) -> FakeChatModel:
        """Encadenable: añade una regla patrón -> respuesta."""
        self.rules.append((pattern, response))
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls.append(list(messages))
        prompt = "\n".join(str(m.content) for m in messages)
        salida = self._resolver(prompt)
        mensaje = AIMessage(
            content=salida,
            usage_metadata={
                "input_tokens": len(prompt.split()),
                "output_tokens": len(salida.split()),
                "total_tokens": len(prompt.split()) + len(salida.split()),
            },
            response_metadata={"model_name": self.model_name},
        )
        return ChatResult(generations=[ChatGeneration(message=mensaje)])

    def _resolver(self, prompt: str) -> str:
        for patron, salida in self.rules:
            if re.search(patron, prompt, re.IGNORECASE | re.DOTALL):
                return salida
        if callable(self.default):
            return self.default(prompt)
        return self.default
