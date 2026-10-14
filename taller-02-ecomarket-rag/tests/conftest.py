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


@pytest.fixture(scope="session")
def chunks_por_tipo():
    from taller02_rag import indexing

    return indexing.preparar_chunks("por_tipo")


@pytest.fixture(scope="session")
def almacen_memoria(chunks_por_tipo):
    """Base vectorial en memoria con los embeddings falsos (léxicos), ya indexada."""
    from genai_common.embeddings import build_embeddings, get_embedding_profile
    from taller02_rag import indexing
    from taller02_rag.store import crear_almacen

    perfil = get_embedding_profile("fake")
    almacen = crear_almacen(build_embeddings(perfil), perfil, backend="memoria")
    indexing.indexar(almacen, chunks_por_tipo, pausa_s=0)
    return almacen
