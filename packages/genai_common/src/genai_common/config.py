"""Carga de configuración: .env + providers.toml -> ProviderProfile."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROVIDERS_FILENAME = "providers.toml"


class ConfigError(RuntimeError):
    """Error de configuración con un mensaje accionable para el usuario."""


def find_repo_root(start: Path | None = None) -> Path:
    """Sube por el árbol de directorios hasta encontrar providers.toml."""
    current = (start or Path(__file__)).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / PROVIDERS_FILENAME).is_file():
            return candidate
    raise ConfigError(
        f"No se encontró {PROVIDERS_FILENAME}. Ejecuta los comandos desde el repositorio del curso."
    )


@dataclass(frozen=True)
class ProviderProfile:
    """Perfil de un proveedor de LLM tal como está declarado en providers.toml."""

    name: str
    base_url: str
    api_key_env: str
    model: str
    models: dict[str, str] = field(default_factory=dict)
    status: str = "implementado"
    notas: str = ""
    extra: dict[str, object] = field(default_factory=dict)

    def model_for(self, role: str | None = None) -> str:
        """Devuelve el ID del modelo para un rol (liviano/router/robusto)."""
        if not role:
            return self.model
        modelo = self.models.get(role)
        if not modelo:
            raise ConfigError(
                f"El proveedor '{self.name}' no define el rol '{role}'. "
                f"Roles disponibles: {sorted(self.models) or 'ninguno'}."
            )
        return modelo

    @property
    def requires_key(self) -> bool:
        return bool(self.api_key_env)

    @property
    def key_configured(self) -> bool:
        """True si la key está disponible (o si el proveedor no necesita ninguna)."""
        if not self.requires_key:
            return True
        return bool(os.getenv(self.api_key_env))

    def api_key(self) -> str:
        """Devuelve la API key o explica exactamente qué falta."""
        if not self.requires_key:
            return "ollama"  # placeholder: los endpoints locales ignoran la key
        valor = os.getenv(self.api_key_env)
        if not valor:
            raise ConfigError(
                f"Falta la variable de entorno {self.api_key_env} para el proveedor "
                f"'{self.name}'. Copia .env.example a .env y define "
                f"{self.api_key_env}=<tu clave>. {_donde_conseguir(self.name)}"
            )
        return valor


def _donde_conseguir(provider: str) -> str:
    urls = {
        "gemini": "Consíguela gratis en https://aistudio.google.com/apikey",
        "anthropic": "Consíguela en https://console.anthropic.com/settings/keys",
    }
    return urls.get(provider, "")


@lru_cache(maxsize=1)
def _load_raw(root: str) -> dict:
    with (Path(root) / PROVIDERS_FILENAME).open("rb") as fh:
        return tomllib.load(fh)


def load_env(root: Path | None = None) -> None:
    """Carga el .env de la raíz del repositorio (si existe)."""
    raiz = root or find_repo_root()
    load_dotenv(raiz / ".env", override=False)


def default_provider(root: Path | None = None) -> str:
    """Proveedor por defecto: LLM_PROVIDER del entorno o el 'default' de providers.toml."""
    raiz = root or find_repo_root()
    load_env(raiz)
    return os.getenv("LLM_PROVIDER") or _load_raw(str(raiz)).get("default", "gemini")


def list_profiles(root: Path | None = None) -> list[ProviderProfile]:
    """Todos los perfiles declarados, en el orden del archivo."""
    raiz = root or find_repo_root()
    load_env(raiz)
    crudo = _load_raw(str(raiz)).get("providers", {})
    return [_build(nombre, datos) for nombre, datos in crudo.items()]


def get_profile(name: str | None = None, root: Path | None = None) -> ProviderProfile:
    """Perfil de un proveedor por nombre; si es None, usa el proveedor por defecto."""
    raiz = root or find_repo_root()
    load_env(raiz)
    nombre = name or default_provider(raiz)
    crudo = _load_raw(str(raiz)).get("providers", {})
    if nombre not in crudo:
        raise ConfigError(
            f"Proveedor desconocido: '{nombre}'. Disponibles: {', '.join(sorted(crudo))}."
        )
    return _build(nombre, crudo[nombre])


def _build(nombre: str, datos: dict) -> ProviderProfile:
    conocidas = {"base_url", "api_key_env", "model", "models", "status", "notas"}
    return ProviderProfile(
        name=nombre,
        base_url=datos.get("base_url", ""),
        api_key_env=datos.get("api_key_env", ""),
        model=datos.get("model", ""),
        models=dict(datos.get("models", {})),
        status=datos.get("status", "implementado"),
        notas=datos.get("notas", ""),
        extra={k: v for k, v in datos.items() if k not in conocidas},
    )
