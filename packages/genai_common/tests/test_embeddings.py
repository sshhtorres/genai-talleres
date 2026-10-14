"""Pruebas de los perfiles de embeddings y su fábrica (sin red)."""

import math

import pytest

from genai_common import ConfigError
from genai_common.embeddings import (
    AsymmetricEmbeddings,
    EmbeddingProfile,
    LexicalHashEmbeddings,
    build_embeddings,
    get_embedding_profile,
    list_embedding_profiles,
)


class _Registrador:
    """Modelo de base falso: guarda lo que recibe y devuelve vectores largos (como sin MRL)."""

    def __init__(self, largo: int = 8) -> None:
        self.largo = largo
        self.documentos: list[tuple[list[str], dict]] = []
        self.preguntas: list[tuple[str, dict]] = []

    def embed_documents(self, texts, **kwargs):
        self.documentos.append((list(texts), kwargs))
        return [[1.0] * self.largo for _ in texts]

    def embed_query(self, text, **kwargs):
        self.preguntas.append((text, kwargs))
        return [1.0] * self.largo


def test_perfiles_esperados():
    nombres = {p.name for p in list_embedding_profiles()}
    assert {"gemini", "embeddinggemma", "bge_m3", "fake"} <= nombres


def test_gemini_a_768_con_task_types():
    perfil = get_embedding_profile("gemini")
    assert perfil.dimensions == 768
    assert perfil.task_type_document == "RETRIEVAL_DOCUMENT"
    assert perfil.task_type_query == "RETRIEVAL_QUERY"
    assert perfil.table_name == "kb_gemini_768"


def test_misma_dimension_no_es_misma_tabla():
    """gemini y embeddinggemma son ambos de 768 y deben vivir en tablas distintas."""
    gemini = get_embedding_profile("gemini")
    gemma = get_embedding_profile("embeddinggemma")
    assert gemini.dimensions == gemma.dimensions
    assert gemini.table_name != gemma.table_name
    assert gemini.cache_namespace != gemma.cache_namespace


def test_embeddinggemma_declara_prefijos():
    perfil = get_embedding_profile("embeddinggemma")
    assert perfil.query_prefix == "task: search result | query: "
    assert perfil.document_prefix == "title: none | text: "


def test_perfil_desconocido_falla_con_mensaje_claro():
    with pytest.raises(ConfigError, match="Perfil de embeddings desconocido"):
        get_embedding_profile("no-existe")


def test_falta_de_key_explica_que_variable_definir(monkeypatch):
    monkeypatch.delenv("CLAVE_EMB_INEXISTENTE", raising=False)
    perfil = EmbeddingProfile(
        name="ficticio",
        backend="google",
        model="x",
        dimensions=768,
        api_key_env="CLAVE_EMB_INEXISTENTE",
    )
    assert perfil.key_configured is False
    with pytest.raises(ConfigError, match="CLAVE_EMB_INEXISTENTE"):
        build_embeddings(perfil)


def test_prefijos_correctos_en_documento_y_pregunta():
    base = _Registrador()
    emb = AsymmetricEmbeddings(
        base, dimensions=8, document_prefix="title: none | text: ", query_prefix="task: q | "
    )
    emb.embed_documents(["política de envíos"])
    emb.embed_query("¿cuánto cuesta el envío?")
    assert base.documentos[0][0] == ["title: none | text: política de envíos"]
    assert base.preguntas[0][0] == "task: q | ¿cuánto cuesta el envío?"


def test_task_type_correcto_en_documento_y_pregunta():
    base = _Registrador()
    emb = AsymmetricEmbeddings(
        base,
        dimensions=8,
        document_kwargs={"task_type": "RETRIEVAL_DOCUMENT"},
        query_kwargs={"task_type": "RETRIEVAL_QUERY"},
    )
    emb.embed_documents(["a"])
    emb.embed_query("b")
    assert base.documentos[0][1] == {"task_type": "RETRIEVAL_DOCUMENT"}
    assert base.preguntas[0][1] == {"task_type": "RETRIEVAL_QUERY"}


def test_trunca_y_renormaliza_si_llega_mas_largo():
    emb = AsymmetricEmbeddings(_Registrador(largo=12), dimensions=4)
    vector = emb.embed_query("x")
    assert len(vector) == 4
    assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0)


def test_embeddings_falsos_son_deterministas_y_lexicos():
    emb = LexicalHashEmbeddings(dimensions=256)
    a = emb.embed_query("plazo de devolución de 30 días")
    assert a == emb.embed_query("plazo de devolución de 30 días")

    def coseno(x, y):
        return sum(i * j for i, j in zip(x, y, strict=True))

    cercano = emb.embed_query("¿cuál es el plazo para una devolucion?")
    lejano = emb.embed_query("envío gratis a Medellín desde cierto monto")
    assert coseno(a, cercano) > coseno(a, lejano)


def test_fabrica_fake_sin_red():
    emb = build_embeddings(get_embedding_profile("fake"))
    assert len(emb.embed_query("hola mundo")) == 256


def test_cache_guarda_documentos_en_disco(tmp_path):
    perfil = get_embedding_profile("embeddinggemma")
    emb = build_embeddings(perfil, cache_dir=tmp_path)
    emb.underlying_embeddings = AsymmetricEmbeddings(_Registrador(), dimensions=8)
    base = emb.underlying_embeddings.inner
    emb.embed_documents(["uno", "dos"])
    emb.embed_documents(["uno", "dos"])  # segunda vez: sale de la caché
    assert len(base.documentos) == 1
    assert (tmp_path / perfil.cache_namespace).is_dir()


def test_normaliza_aunque_llegue_con_la_dimension_pedida():
    """gemini-embedding-001 a 768 llega con norma ≈ 0,59: hay que normalizar a mano."""

    class _SinNormalizar(_Registrador):
        def embed_query(self, text, **kwargs):
            return [0.3] * 4

    vector = AsymmetricEmbeddings(_SinNormalizar(), dimensions=4).embed_query("x")
    assert len(vector) == 4
    assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0)
