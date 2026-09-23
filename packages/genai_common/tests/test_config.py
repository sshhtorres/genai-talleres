"""Pruebas de carga de configuración (sin red)."""

import pytest

from genai_common import ConfigError, ProviderProfile, get_profile, list_profiles
from genai_common.config import find_repo_root


def test_encuentra_la_raiz_del_repo():
    assert (find_repo_root() / "providers.toml").is_file()


def test_lista_los_perfiles_esperados():
    nombres = {p.name for p in list_profiles()}
    assert {"gemini", "anthropic", "ollama", "fake"} <= nombres


def test_perfil_gemini_resuelve_roles():
    perfil = get_profile("gemini")
    assert perfil.base_url.startswith("https://")
    assert perfil.api_key_env == "GEMINI_API_KEY"
    assert perfil.model_for("liviano") == perfil.models["liviano"]
    assert perfil.model_for(None) == perfil.model


def test_rol_inexistente_falla_con_mensaje_claro():
    with pytest.raises(ConfigError, match="no define el rol"):
        get_profile("gemini").model_for("inexistente")


def test_proveedor_desconocido_falla():
    with pytest.raises(ConfigError, match="Proveedor desconocido"):
        get_profile("no-existe")


def test_falta_de_key_explica_que_variable_definir(monkeypatch):
    """El perfil es ficticio a propósito: el test no debe depender del .env local."""
    monkeypatch.delenv("CLAVE_INEXISTENTE", raising=False)
    perfil = ProviderProfile(
        name="ficticio",
        base_url="https://ejemplo.invalid/v1",
        api_key_env="CLAVE_INEXISTENTE",
        model="modelo-x",
    )
    assert perfil.key_configured is False
    with pytest.raises(ConfigError, match="CLAVE_INEXISTENTE"):
        perfil.api_key()


def test_ollama_no_requiere_key():
    perfil = get_profile("ollama")
    assert perfil.requires_key is False
    assert perfil.key_configured is True
