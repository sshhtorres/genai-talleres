"""Todas las plantillas de prompts deben renderizar sin dejar variables sueltas."""

import json

import pytest

from genai_common import PromptError, render, variables_of
from taller01 import chains, data

VALORES = {
    "tracking_number": "ECO-1001",
    "pedidos": "[]",
    "mensaje": "hola",
    "producto": "{}",
    "politica": "texto",
    "pedido": "{}",
    "decision": "{}",
}


def _plantillas():
    for archivo in ("ej1_pedido", "ej2_devolucion"):
        prompts = chains.load_prompt_file(archivo)
        for seccion in ("basico", "mejorado"):
            for clave, valor in prompts[seccion].items():
                if isinstance(valor, str):
                    yield f"{archivo}.{seccion}.{clave}", valor


def test_hay_plantillas_en_ambos_archivos():
    assert len(list(_plantillas())) >= 6


@pytest.mark.parametrize(("nombre", "plantilla"), list(_plantillas()))
def test_cada_plantilla_renderiza(nombre, plantilla):
    faltantes = variables_of(plantilla) - set(VALORES)
    assert not faltantes, f"{nombre} usa variables no previstas: {faltantes}"
    resultado = render(plantilla, **VALORES)
    assert "{{" not in resultado


def test_render_falla_si_falta_una_variable():
    prompts = chains.load_prompt_file("ej1_pedido")
    with pytest.raises(PromptError):
        render(prompts["basico"]["user"], tracking_number="ECO-1001")


def test_el_prompt_mejorado_aplica_las_tecnicas_declaradas():
    mejorado = chains.load_prompt_file("ej1_pedido")["mejorado"]
    system = mejorado["system"].lower()
    assert "asistente virtual" in system  # rol
    assert "nunca inventes" in system  # anti-alucinación
    assert "máximo 120 palabras" in system  # formato de salida
    assert "<pedidos>" in mejorado["respuesta"]  # contexto delimitado
    assert "<consulta>" in mejorado["respuesta"]
    assert len(mejorado["ejemplos"]) >= 2  # few-shot


def test_el_prompt_de_devolucion_pide_json_con_las_claves_necesarias():
    decision = chains.load_prompt_file("ej2_devolucion")["mejorado"]["decision"]
    for clave in ("elegible", "motivo", "regla_aplicada", "datos_faltantes"):
        assert clave in decision
    assert "<politica>" in decision and "<producto>" in decision


def test_los_ejemplos_few_shot_no_usan_trackings_reales():
    """Los ejemplos no deben poder confundirse con datos del catálogo real."""
    for archivo in ("ej1_pedido", "ej2_devolucion"):
        for ejemplo in chains.load_prompt_file(archivo)["mejorado"]["ejemplos"]:
            texto = json.dumps(ejemplo, ensure_ascii=False)
            for tracking in data.extraer_trackings(texto):
                assert data.buscar_pedido(tracking) is None, (
                    f"{archivo}: el ejemplo usa {tracking}, que sí existe en los datos"
                )
