"""Configuración del taller y comandos que no necesitan servicios."""

import pytest
from typer.testing import CliRunner

from genai_common import ConfigError
from taller02_rag import config, servicios
from taller02_rag.cli import app


def test_parametros_del_plan():
    p = config.parametros()
    assert p["chunking"]["chunk_size"] == 800
    assert p["chunking"]["chunk_overlap"] == 120
    assert p["recuperacion"]["k"] == 4
    umbrales = p["recuperacion"]["umbral"]
    assert {"gemini", "embeddinggemma", "bge_m3", "fake"} <= set(umbrales)
    assert all(0.0 <= u <= 1.0 for u in umbrales.values())


def test_postgres_sin_variables_usa_los_valores_del_compose(sin_env):
    """Un .env heredado del Taller 1 no trae PG_*: deben valer los de docker-compose.yml."""
    assert config.postgres_config().url == (
        "postgresql+psycopg://ecomarket:ecomarket@localhost:5433/ecomarket_kb"
    )


def test_postgres_puerto_invalido_es_accionable(sin_env):
    sin_env.setenv("PG_PORT", "cinco")
    with pytest.raises(ConfigError, match="PG_PORT"):
        config.postgres_config()


def test_postgres_arma_url_con_psycopg(sin_env):
    for clave, valor in {
        "PG_HOST": "localhost",
        "PG_PORT": "5433",
        "PG_USER": "u",
        "PG_PASSWORD": "p",
        "PG_DB": "kb",
    }.items():
        sin_env.setenv(clave, valor)
    assert config.postgres_config().url == "postgresql+psycopg://u:p@localhost:5433/kb"


def test_postgres_caido_no_rompe_y_dice_como_levantarlo(sin_env):
    sin_env.setenv("PG_PORT", "9")
    estado = servicios.estado_postgres()
    assert estado.ok is False
    assert "docker compose up -d" in estado.detalle


def test_ollama_caido_explica_como_instalarlo():
    estado = servicios.estado_ollama("http://127.0.0.1:9", timeout_s=0.2)
    assert estado.ok is False
    assert "ollama.com" in estado.detalle


def test_modelo_descargado_tolera_latest():
    assert servicios.modelo_descargado("bge-m3", ["bge-m3:latest"])
    assert not servicios.modelo_descargado("gemma4:e4b", ["gemma4:e2b"])


def test_cli_proveedores_funciona_sin_servicios(sin_env):
    sin_env.setenv("RAG_CONFIG", "pruebas")
    sin_env.setattr(servicios, "estado_ollama", lambda *a, **k: servicios.Estado(False, "caído"))
    resultado = CliRunner().invoke(app, ["proveedores", "--recomendar"])
    assert resultado.exit_code == 0, resultado.output
    assert "kb_fake_256" in resultado.output
    assert "LOCAL_TIER" in resultado.output
