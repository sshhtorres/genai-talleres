"""Modelos de chat de LangChain construidos desde los perfiles de providers.toml.

Es el equivalente de `LLMClient.from_profile` para las cadenas LCEL del Taller 2: mismas reglas
(perfiles `por_implementar` bloqueados, `omit_params` y `params` por proveedor, claves con errores
accionables), pero devolviendo un `BaseChatModel` que se puede encadenar con `|`.
Requiere el extra `langchain` de genai-common.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from .config import ConfigError, ProviderProfile, get_profile


def chat_model_from_profile(
    name: str | None = None,
    model_role: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 800,
    profile: ProviderProfile | None = None,
) -> BaseChatModel:
    """`ChatOpenAI` apuntando al endpoint compatible con OpenAI del proveedor.

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

    from langchain_openai import ChatOpenAI

    argumentos: dict[str, Any] = {
        "model": model or perfil.model_for(model_role),
        "base_url": perfil.base_url or None,
        "api_key": perfil.api_key(),
        "temperature": temperature,
        # Modelos que razonan gastan parte de max_tokens pensando: el perfil fija un mínimo.
        "max_tokens": max(max_tokens, int(perfil.extra.get("max_tokens_min", 0))),
        "max_retries": 6,
        "stream_usage": True,
    }
    # Mismo contrato que LLMClient: cada proveedor declara qué parámetros rechaza y cuáles añade.
    for parametro in perfil.extra.get("omit_params", []):
        argumentos.pop(parametro, None)
    extra = dict(perfil.extra.get("params", {}))
    if extra:
        argumentos["model_kwargs"] = extra
    return ChatOpenAI(**argumentos)


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
