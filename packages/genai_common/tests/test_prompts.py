"""Pruebas del renderizado de plantillas."""

import pytest

from genai_common import PromptError, render, variables_of


def test_render_reemplaza_variables():
    assert render("Hola {{nombre}}", nombre="EcoMarket") == "Hola EcoMarket"


def test_render_tolera_espacios_dentro_de_las_llaves():
    assert render("{{ a }}-{{b}}", a=1, b=2) == "1-2"


def test_render_falla_si_falta_una_variable():
    with pytest.raises(PromptError, match="tracking"):
        render("Pedido {{tracking}}")


def test_variables_of_detecta_los_nombres():
    assert variables_of("{{a}} y {{b}} y {{a}}") == {"a", "b"}
