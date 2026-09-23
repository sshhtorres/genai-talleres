"""Pruebas de extracción de JSON y del proveedor fake (sin red)."""

from genai_common import FakeLLMClient, json_response
from genai_common.llm import _extraer_json


def test_extrae_json_plano():
    assert _extraer_json('{"a": 1}') == {"a": 1}


def test_extrae_json_dentro_de_un_bloque_de_codigo():
    texto = 'Claro:\n```json\n{"tracking_number": "ECO-1001"}\n```\nEso es todo.'
    assert _extraer_json(texto, ("tracking_number",)) == {"tracking_number": "ECO-1001"}


def test_extrae_json_rodeado_de_texto():
    assert _extraer_json('Resultado: {"ok": true} listo', ("ok",)) == {"ok": True}


def test_devuelve_none_si_faltan_claves_requeridas():
    assert _extraer_json('{"a": 1}', ("b",)) is None


def test_devuelve_none_si_no_hay_json():
    assert _extraer_json("no hay json aquí") is None


def test_fake_aplica_reglas_en_orden():
    cliente = FakeLLMClient()
    cliente.add_rule(r"ECO-1005", "El pedido ECO-1005 está retrasado.")
    cliente.add_rule(r".*", "genérica")
    respuesta = cliente.chat([{"role": "user", "content": "¿Y el ECO-1005?"}])
    assert "retrasado" in respuesta.text
    assert respuesta.provider == "fake"
    assert cliente.calls  # registra las llamadas para poder inspeccionarlas


def test_fake_chat_json_parsea():
    cliente = FakeLLMClient(rules=[(r".*", json_response({"elegible": "si"}))])
    respuesta = cliente.chat_json([{"role": "user", "content": "x"}], ("elegible",))
    assert respuesta.data == {"elegible": "si"}
