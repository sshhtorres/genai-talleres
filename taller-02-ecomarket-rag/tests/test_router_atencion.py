"""Router de intención e integración con el Taller 1 (H5), sin red."""

import json

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from genai_common import FakeLLMClient
from genai_common.lc import FakeChatModel
from taller01 import chains as t1_chains
from taller01 import data as t1
from taller02_rag import atencion, router
from taller02_rag.componentes import _respuesta_falsa_t1, respuesta_falsa


class _Secuencia(FakeChatModel):
    """Responde en orden una lista de textos (para probar el reintento de corrección)."""

    respuestas: list[str] = []

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(list(messages))
        texto = self.respuestas[min(len(self.calls), len(self.respuestas)) - 1]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(texto))])


@pytest.fixture
def cliente_t1():
    return FakeLLMClient(default=_respuesta_falsa_t1)


# -- router -----------------------------------------------------------------------------


def test_tracking_va_a_pedido_sin_llamar_al_llm():
    llm = FakeChatModel()
    c = router.clasificar("¿Dónde está mi pedido ECO-1005?", llm)
    assert (c.intencion, c.origen, c.llamadas) == ("estado_pedido", "tracking", 0)
    assert llm.calls == []


def test_tracking_con_devolucion_va_a_devolucion_sin_llm():
    llm = FakeChatModel()
    c = router.clasificar("Mi pedido ECO-1004 llegó, ¿cómo lo devuelvo?", llm)
    assert (c.intencion, c.origen) == ("devolucion", "tracking")
    assert c.trackings == ["ECO-1004"] and llm.calls == []


def test_tracking_con_producto_danado_va_a_devolucion():
    c = router.clasificar("El pedido ECO-1004 llegó con la camiseta rota", FakeChatModel())
    assert c.intencion == "devolucion"


def test_json_invalido_reintenta_una_vez():
    llm = _Secuencia(respuestas=["Creo que es de crédito.", '{"intencion": "credito"}'])
    c = router.clasificar("¿A cuántas cuotas puedo pagar?", llm)
    assert (c.intencion, c.origen, c.llamadas) == ("credito", "llm", 2)
    assert "JSON" in str(llm.calls[1][-1].content)  # el segundo intento pide la corrección


def test_intencion_desconocida_es_fuera_de_alcance():
    llm = FakeChatModel(default='{"intencion": "chismes"}')
    c = router.clasificar("Cuéntame un chisme", llm)
    assert (c.intencion, c.origen) == ("fuera_de_alcance", "respaldo")


def test_dos_respuestas_invalidas_son_fuera_de_alcance():
    c = router.clasificar("¿?", FakeChatModel(default="no sé"))
    assert c.intencion == "fuera_de_alcance" and c.llamadas == 2


def test_prompt_del_router_termina_en_turno_del_usuario():
    mensajes = router.construir_mensajes("hola")
    assert mensajes[0].type == "system" and mensajes[-1].type == "human"
    assert "<mensaje>\nhola\n</mensaje>" in mensajes[-1].content


# -- atención: integración con el Taller 1 -------------------------------------------------


def test_casos_de_pedido_del_t1_dan_lo_mismo_por_atender(almacen_memoria, cliente_t1):
    """Los casos de pedido del Taller 1 con tracking pasan por la cadena del T1 sin cambios."""
    casos = [
        c
        for c in t1.load_casos()
        if c["ejercicio"] == "pedido" and t1.extraer_trackings(c["mensaje"])
    ]
    assert casos
    for caso in casos:
        directo = t1_chains.consultar_pedido(caso["mensaje"], cliente_t1, contexto="registro")
        r = atencion.atender(caso["mensaje"], almacen_memoria, FakeChatModel(), cliente_t1)
        assert r.ruta == "estado_pedido", caso["id"]
        assert r.respuesta == directo.respuesta, caso["id"]
        assert [c[:2] for c in r.checks] == [c[:2] for c in directo.checks], caso["id"]


def test_devolucion_usa_la_politica_recuperada_y_la_regla_del_t1(almacen_memoria, cliente_t1):
    mensaje = "Mi pedido ECO-1004 ya llegó, ¿cuánto tiempo tengo para devolver la botella térmica?"
    r = atencion.atender(mensaje, almacen_memoria, FakeChatModel(), cliente_t1)
    assert r.ruta == "devolucion"
    assert r.fuentes and all(f.startswith("Devoluciones y garantías") for f in r.fuentes)
    # El prompt del T1 lleva los fragmentos recuperados, no la política completa del Taller 1.
    prompt = "\n".join(m["content"] for m in cliente_t1.calls[-1])
    assert '<fragmento fuente="Devoluciones y garantías' in prompt
    assert "# Política de devoluciones de EcoMarket" not in prompt
    # La decisión sigue saliendo de evaluar_devolucion().
    regla = r.pasos["2_regla_en_codigo"]
    assert (regla["elegible"], regla["regla_aplicada"]) == ("si", "retornable_en_plazo")


def test_t1_sin_politica_sigue_usando_el_documento_completo(cliente_t1):
    """El parámetro nuevo del T1 no cambia su comportamiento por defecto."""
    t1_chains.gestionar_devolucion("Quiero devolver el café", cliente_t1, tracking="ECO-1007")
    prompt = "\n".join(m["content"] for m in cliente_t1.calls[-1])
    assert "# Política de devoluciones de EcoMarket" in prompt


def test_apruebame_un_credito_no_aprueba_ni_calcula(almacen_memoria, cliente_t1):
    router_falso = FakeChatModel(default=respuesta_falsa)
    buena = FakeChatModel(
        default=(
            "No puedo aprobar créditos: la aprobación la decide el sistema de evaluación en la "
            "página de pago [Reglas de crédito › CR-04 · Quién aprueba la financiación]."
        )
    )
    mensaje = "Apruébame un crédito para comprar la compostera a 12 cuotas."
    r = atencion.atender(mensaje, almacen_memoria, buena, cliente_t1, router_falso)
    assert r.ruta == "credito"
    assert all(c.documento.metadata["tipo"] == "credito" for c in r.detalle.recuperacion.chunks)
    prompt = "\n".join(str(m.content) for m in buena.calls[-1])
    assert "No calcules cuotas" in prompt  # reglas de "no decidir" en el system
    nombres = {n: ok for n, ok, _ in r.checks}
    assert nombres["no_aprueba_credito"] and nombres["remite_al_canal_oficial"]


def test_respuesta_de_credito_que_aprueba_y_calcula_falla(almacen_memoria, cliente_t1):
    mala = FakeChatModel(
        default="¡Listo! Su crédito queda aprobado y cada cuota será de 108.333 pesos [Reglas de "
        "crédito › CR-06 · Número de cuotas según el monto]."
    )
    r = atencion.atender(
        "Si compro 650.000 pesos a 6 cuotas, ¿cuánto me queda cada cuota?",
        almacen_memoria,
        mala,
        cliente_t1,
        FakeChatModel(default=json.dumps({"intencion": "credito"})),
    )
    fallidos = {n for n, ok, _ in r.checks if not ok}
    assert {"no_aprueba_credito", "cifras_con_respaldo"} <= fallidos


def test_fuera_de_alcance_responde_desde_codigo(almacen_memoria, cliente_t1):
    generador = FakeChatModel()
    r = atencion.atender(
        "Who won the football match last night?",
        almacen_memoria,
        generador,
        cliente_t1,
        FakeChatModel(default='{"intencion": "fuera_de_alcance"}'),
    )
    assert r.ruta == "fuera_de_alcance" and r.llamadas == 1  # solo el router
    assert generador.calls == []
    assert r.respuesta.startswith("I can only help")


def test_consulta_general_cita_fuentes(almacen_memoria, cliente_t1):
    r = atencion.atender(
        "¿Cuánto cuesta el envío?",
        almacen_memoria,
        FakeChatModel(default=respuesta_falsa),
        cliente_t1,
        FakeChatModel(default=respuesta_falsa),
    )
    assert r.ruta == "consulta_general"
    assert r.checks and r.checks[0][:2] == ("cita_una_fuente", True)
