"""Librería compartida de los talleres de IA Generativa."""

from .config import (
    ConfigError,
    ProviderProfile,
    default_provider,
    find_repo_root,
    get_profile,
    list_profiles,
    load_env,
)
from .fake import FakeLLMClient, json_response
from .llm import LLMClient, LLMResponse
from .prompts import PromptError, load_prompts, render, variables_of
from .runs import RunRecord, RunRecorder

__all__ = [
    "ConfigError",
    "FakeLLMClient",
    "LLMClient",
    "LLMResponse",
    "PromptError",
    "ProviderProfile",
    "RunRecord",
    "RunRecorder",
    "default_provider",
    "find_repo_root",
    "get_profile",
    "json_response",
    "list_profiles",
    "load_env",
    "load_prompts",
    "render",
    "variables_of",
]
