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
    assert 0.0 <= p["recuperacion"]["umbral"] <= 1.0


def test_postgres_sin_variables_es_accionable(sin_env):
    with pytest.raises(ConfigError, match="PG_HOST"):
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


def test_postgres_sin_configurar_no_rompe(sin_env):
    estado = servicios.estado_postgres()
    assert estado.ok is False
    assert "PG_HOST" in estado.detalle


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
