"""Utilidades compartidas por los tests del Taller 2: todo sin red ni servicios externos."""

import pytest


@pytest.fixture
def sin_env(monkeypatch):
    """Aísla los tests del .env local de quien los ejecuta."""
    import genai_common.configuraciones as configuraciones
    from taller02_rag import config

    monkeypatch.setattr(configuraciones, "load_env", lambda *args, **kwargs: None)
    monkeypatch.setattr(config, "load_env", lambda *args, **kwargs: None)
    for variable in (
        "RAG_CONFIG",
        "RAG_LLM",
        "LOCAL_TIER",
        "PG_HOST",
        "PG_PORT",
        "PG_USER",
        "PG_PASSWORD",
        "PG_DB",
    ):
        monkeypatch.delenv(variable, raising=False)
    return monkeypatch
