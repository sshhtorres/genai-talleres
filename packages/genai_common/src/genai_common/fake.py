"""Proveedor falso determinístico: los tests y la CI nunca llaman a una API real."""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from .config import ProviderProfile
from .llm import LLMClient, LLMResponse, Message, _extraer_json

Rule = tuple[str, str]  # (patrón regex sobre el prompt, respuesta)


class FakeLLMClient(LLMClient):
    """Responde según reglas patrón -> respuesta, sin red ni API key."""

    def __init__(
        self,
        profile: ProviderProfile | None = None,
        model: str = "fake-determinista",
        rules: list[Rule] | None = None,
        default: str | Callable[[str], str] = "Respuesta falsa por defecto.",
    ) -> None:
        self.profile = profile or ProviderProfile(
            name="fake", base_url="", api_key_env="", model=model, status="tests"
        )
        self.model = model
        self.rules = list(rules or [])
        self.default = default
        self.calls: list[list[Message]] = []

    def add_rule(self, pattern: str, response: str) -> FakeLLMClient:
        """Encadenable: añade una regla patrón -> respuesta."""
        self.rules.append((pattern, response))
        return self

    def chat(
        self,
        messages: list[Message],
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> LLMResponse:
        self.calls.append(messages)
        texto_prompt = "\n".join(m.get("content", "") for m in messages)
        salida = self._resolver(texto_prompt)
        return LLMResponse(
            text=salida,
            provider="fake",
            model=self.model,
            latency_s=0.0,
            prompt_tokens=len(texto_prompt.split()),
            completion_tokens=len(salida.split()),
            finish_reason="stop",
        )

    def chat_json(
        self,
        messages: list[Message],
        required_keys: tuple[str, ...] = (),
        temperature: float = 0.0,
        max_tokens: int = 800,
    ) -> LLMResponse:
        respuesta = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        respuesta.data = _extraer_json(respuesta.text, required_keys)
        respuesta.raw_attempts = [respuesta.text]
        return respuesta

    def _resolver(self, prompt: str) -> str:
        for patron, salida in self.rules:
            if re.search(patron, prompt, re.IGNORECASE | re.DOTALL):
                return salida
        if callable(self.default):
            return self.default(prompt)
        return self.default


def json_response(payload: dict) -> str:
    """Azúcar para declarar reglas que devuelven JSON."""
    return json.dumps(payload, ensure_ascii=False)
