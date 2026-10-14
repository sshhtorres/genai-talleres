"""Cliente único de LLM sobre endpoints compatibles con la API de OpenAI."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from .config import ConfigError, ProviderProfile, get_profile

Message = dict[str, str]

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


@dataclass
class LLMResponse:
    """Respuesta de una llamada, con los metadatos que usan los reportes."""

    text: str
    provider: str
    model: str
    latency_s: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    data: dict[str, Any] | None = None  # solo en chat_json
    raw_attempts: list[str] = field(default_factory=list)
    finish_reason: str | None = None  # "length" = se cortó por max_tokens

    def as_metadata(self) -> dict[str, Any]:
        return {
            "proveedor": self.provider,
            "modelo": self.model,
            "latencia_s": round(self.latency_s, 3),
            "tokens_entrada": self.prompt_tokens,
            "tokens_salida": self.completion_tokens,
            "finish_reason": self.finish_reason,
        }


def _es_reintentable(exc: BaseException) -> bool:
    """Reintentar solo ante límites de tasa, 5xx y problemas de red."""
    if isinstance(exc, RateLimitError | APIConnectionError):
        return True
    return isinstance(exc, APIStatusError) and exc.status_code >= 500


class LLMClient:
    """Envoltorio delgado sobre el SDK openai, configurado por perfil de proveedor."""

    def __init__(self, profile: ProviderProfile, model: str, timeout: float = 60.0) -> None:
        self.profile = profile
        self.model = model
        if profile.status == "por_implementar":
            raise ConfigError(
                f"El proveedor '{profile.name}' está marcado como 'por_implementar' en "
                "providers.toml y no ha sido probado. Usa gemini o anthropic."
            )
        self._client = OpenAI(
            api_key=profile.api_key(),
            base_url=profile.base_url or None,
            timeout=timeout,
        )

    @classmethod
    def from_profile(
        cls,
        name: str | None = None,
        model_role: str | None = None,
        model: str | None = None,
    ) -> LLMClient:
        """Crea el cliente desde providers.toml (o desde LLM_PROVIDER si name es None)."""
        perfil = get_profile(name)
        if perfil.name == "fake":
            from .fake import FakeLLMClient

            return FakeLLMClient(perfil, model or perfil.model)
        return cls(perfil, model or perfil.model_for(model_role))

    # -- llamadas --------------------------------------------------------

    def chat(
        self,
        messages: list[Message],
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> LLMResponse:
        """Una llamada de conversación; devuelve texto y metadatos."""
        inicio = time.perf_counter()
        respuesta = self._completion(messages, temperature, max_tokens)
        latencia = time.perf_counter() - inicio
        uso = getattr(respuesta, "usage", None)
        return LLMResponse(
            text=(respuesta.choices[0].message.content or "").strip(),
            provider=self.profile.name,
            model=self.model,
            latency_s=latencia,
            prompt_tokens=getattr(uso, "prompt_tokens", None),
            completion_tokens=getattr(uso, "completion_tokens", None),
            finish_reason=getattr(respuesta.choices[0], "finish_reason", None),
        )

    def chat_json(
        self,
        messages: list[Message],
        required_keys: tuple[str, ...] = (),
        temperature: float = 0.0,
        max_tokens: int = 800,
    ) -> LLMResponse:
        """Como chat(), pero exige un objeto JSON. Reintenta una vez pidiendo corrección."""
        respuesta = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        intentos = [respuesta.text]
        datos = _extraer_json(respuesta.text, required_keys)

        if datos is None:
            correccion = [
                *messages,
                {"role": "assistant", "content": respuesta.text},
                {
                    "role": "user",
                    "content": (
                        "Tu respuesta no fue un objeto JSON válido con las claves "
                        f"{list(required_keys) or 'requeridas'}. Responde de nuevo con "
                        "SOLO el objeto JSON, sin texto adicional ni bloques de código."
                    ),
                },
            ]
            respuesta = self.chat(correccion, temperature=0.0, max_tokens=max_tokens)
            intentos.append(respuesta.text)
            datos = _extraer_json(respuesta.text, required_keys)

        respuesta.data = datos
        respuesta.raw_attempts = intentos
        return respuesta

    # -- interno ---------------------------------------------------------

    # Los tiers gratuitos limitan las peticiones por minuto (Gemini flash-lite: 15/min) y piden
    # esperas de ~30 s. La espera acumulada llega a ~2 minutos, suficiente para esa ventana.
    @retry(
        retry=retry_if_exception(_es_reintentable),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        stop=stop_after_attempt(6),
        reraise=True,
    )
    def _completion(self, messages: list[Message], temperature: float, max_tokens: int):
        argumentos: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            # Los modelos que razonan gastan parte de max_tokens pensando: el perfil fija un mínimo.
            # Sin esto, Haiku 5.5 cortó a la mitad una respuesta de las cadenas del Taller 1.
            "max_tokens": max(max_tokens, int(self.profile.extra.get("max_tokens_min", 0))),
        }
        # Cada proveedor declara en providers.toml qué parámetros no acepta y cuáles añade.
        # Así el código común no conoce las particularidades de ningún proveedor.
        for parametro in self.profile.extra.get("omit_params", []):
            argumentos.pop(parametro, None)
        argumentos.update(self.profile.extra.get("params", {}))
        # Parámetros propios del proveedor: el SDK de OpenAI solo los acepta dentro de extra_body.
        if self.profile.extra.get("extra_body"):
            argumentos["extra_body"] = dict(self.profile.extra["extra_body"])
        return self._client.chat.completions.create(**argumentos)


def _extraer_json(texto: str, required_keys: tuple[str, ...] = ()) -> dict[str, Any] | None:
    """Extrae el primer objeto JSON válido del texto; tolera bloques ```json."""
    candidatos: list[str] = []
    fence = _JSON_FENCE.search(texto)
    if fence:
        candidatos.append(fence.group(1))
    candidatos.append(texto)
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio != -1 and fin > inicio:
        candidatos.append(texto[inicio : fin + 1])

    for candidato in candidatos:
        try:
            datos = json.loads(candidato.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(datos, dict) and all(clave in datos for clave in required_keys):
            return datos
    return None
