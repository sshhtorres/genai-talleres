"""Pruebas de chat_model_from_profile y de las configuraciones de ejecución (sin red)."""

import pytest

from genai_common import ConfigError, ProviderProfile, get_profile
from genai_common.configuraciones import recomendar_nivel, resolver_configuracion
from genai_common.lc import FakeChatModel, chat_model_from_profile


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    """Los tests no deben depender del .env local de quien los ejecuta."""
    import genai_common.configuraciones as configuraciones

    monkeypatch.setattr(configuraciones, "load_env", lambda *args, **kwargs: None)
    for variable in ("RAG_CONFIG", "RAG_LLM", "LOCAL_TIER"):
        monkeypatch.delenv(variable, raising=False)


# -- chat_model_from_profile ----------------------------------------------------


def test_fake_devuelve_modelo_falso_que_responde_por_reglas():
    modelo = chat_model_from_profile("fake")
    assert isinstance(modelo, FakeChatModel)
    modelo.add_rule("envío", "El envío cuesta poco.")
    assert modelo.invoke("¿Cuánto cuesta el envío?").content == "El envío cuesta poco."
    assert len(modelo.calls) == 1


def test_por_implementar_esta_bloqueado():
    perfil = ProviderProfile(
        name="x", base_url="http://x/v1", api_key_env="", model="m", status="por_implementar"
    )
    with pytest.raises(ConfigError, match="por_implementar"):
        chat_model_from_profile(profile=perfil)


def test_falta_de_key_es_accionable(monkeypatch):
    monkeypatch.delenv("CLAVE_CHAT_INEXISTENTE", raising=False)
    perfil = ProviderProfile(
        name="x", base_url="http://x/v1", api_key_env="CLAVE_CHAT_INEXISTENTE", model="m"
    )
    with pytest.raises(ConfigError, match="CLAVE_CHAT_INEXISTENTE"):
        chat_model_from_profile(profile=perfil)


def test_omite_parametros_y_usa_modelo_por_rol(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-de-prueba")
    modelo = chat_model_from_profile("anthropic", model_role="router")
    assert modelo.model_name == "claude-haiku-5-5"
    assert modelo.temperature is None  # omit_params la quita
    assert "top_p" not in modelo.model_kwargs


def test_respeta_max_tokens_minimo_del_perfil(monkeypatch):
    """Haiku 5.5 piensa dentro de max_tokens: un valor pequeño podría dejar la respuesta vacía."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-de-prueba")
    modelo = chat_model_from_profile("anthropic", model_role="router", max_tokens=200)
    assert modelo.max_tokens >= 4000


def test_gemini_conserva_temperature(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    modelo = chat_model_from_profile("gemini", temperature=0.1)
    assert modelo.temperature == 0.1
    assert modelo.model_name == get_profile("gemini").model


# -- configuraciones -------------------------------------------------------------


def test_nube_por_defecto():
    config = resolver_configuracion()
    assert config.nombre == "nube"
    assert config.embeddings.name == "gemini"
    assert config.llm.name == "gemini"
    assert config.tabla == "kb_gemini_768"


def test_hibrida_exige_rag_llm():
    with pytest.raises(ConfigError, match="RAG_LLM"):
        resolver_configuracion("hibrida")


def test_hibrida_con_anthropic(monkeypatch):
    monkeypatch.setenv("RAG_LLM", "anthropic")
    config = resolver_configuracion("hibrida")
    assert config.embeddings.name == "embeddinggemma"
    assert config.llm.name == "anthropic"


def test_hibrida_rechaza_llm_no_permitido():
    with pytest.raises(ConfigError, match="RAG_LLM"):
        resolver_configuracion("hibrida", llm="ollama")


def test_local_usa_nivel_por_defecto_y_su_modelo():
    config = resolver_configuracion("local")
    assert config.llm.name == "ollama"
    assert config.nivel == "cpu-16gb"
    assert config.llm_model == "gemma4:e4b"
    assert config.tabla == "kb_embeddinggemma_768"


def test_local_con_nivel_inexistente_falla(monkeypatch):
    monkeypatch.setenv("LOCAL_TIER", "cpu-2gb")
    with pytest.raises(ConfigError, match="LOCAL_TIER"):
        resolver_configuracion("local")


def test_configuracion_desconocida_falla(monkeypatch):
    monkeypatch.setenv("RAG_CONFIG", "marte")
    with pytest.raises(ConfigError, match="RAG_CONFIG"):
        resolver_configuracion()


def test_pruebas_no_necesita_red():
    config = resolver_configuracion("pruebas")
    assert config.embeddings.backend == "fake"
    assert config.llm.name == "fake"


@pytest.mark.parametrize(
    ("ram", "esperado"),
    [(4, None), (7.6, "cpu-8gb"), (12, "cpu-8gb"), (15.5, "cpu-16gb"), (32, "cpu-16gb")],
)
def test_recomendar_nivel_por_ram(ram, esperado):
    assert recomendar_nivel(ram) == esperado
