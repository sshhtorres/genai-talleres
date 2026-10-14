"""Recuperación, prompts y cadena RAG (H4), con embeddings y LLM falsos."""

import pytest

from genai_common import variables_of
from genai_common.lc import FakeChatModel
from taller02_rag import chains, checks, retrieval
from taller02_rag.componentes import respuesta_extractiva


def test_scores_normalizados_y_ordenados(almacen_memoria):
    rec = retrieval.recuperar(almacen_memoria, "monto mínimo para financiar una compra", k=4)
    scores = [c.similitud for c in rec.chunks]
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert scores == sorted(scores, reverse=True)


def test_recupera_la_regla_correcta(almacen_memoria):
    rec = retrieval.recuperar(almacen_memoria, "¿Cuál es el monto mínimo financiable?", k=4)
    assert any(c.documento.metadata.get("id_regla") == "CR-05" for c in rec.chunks)


def test_filtro_por_metadatos(almacen_memoria):
    rec = retrieval.recuperar(almacen_memoria, "plazo", k=4, filtro={"area": "devoluciones"})
    assert rec.chunks and all(c.documento.metadata["area"] == "devoluciones" for c in rec.chunks)


def test_umbral_decide_si_hay_evidencia(almacen_memoria):
    rec = retrieval.recuperar(almacen_memoria, "envío gratis", k=2, umbral=0.0)
    assert rec.hay_evidencia
    rec = retrieval.recuperar(almacen_memoria, "envío gratis", k=2, umbral=0.999)
    assert not rec.hay_evidencia


def test_el_contexto_llega_al_prompt_con_sus_fuentes(almacen_memoria):
    llm = FakeChatModel(default=respuesta_extractiva)
    resultado = chains.responder("¿Cuánto cuesta el envío?", almacen_memoria, llm, umbral=0.0)
    prompt = "\n".join(str(m.content) for m in llm.calls[-1])
    for chunk in resultado.recuperacion.chunks:
        assert f'fuente="{chunk.fuente}"' in prompt
        assert chunk.texto[:60] in prompt
    assert "<pregunta>\n¿Cuánto cuesta el envío?\n</pregunta>" in prompt
    assert resultado.llamadas == 1
    assert ("cita_una_fuente", True) == resultado.checks[0][:2]


def test_sin_evidencia_no_se_llama_al_llm(almacen_memoria):
    llm = FakeChatModel()
    resultado = chains.responder("¿Venden bicicletas?", almacen_memoria, llm, umbral=0.999)
    assert llm.calls == []
    assert resultado.abstuvo_por_umbral and resultado.llamadas == 0
    assert checks.es_abstencion(resultado.respuesta)


def test_abstencion_en_el_idioma_de_la_pregunta(almacen_memoria):
    resultado = chains.responder(
        "Do you sell electric bikes?", almacen_memoria, FakeChatModel(), umbral=0.999
    )
    assert resultado.respuesta.startswith("I don't have information")


def test_variante_basica_sin_system_ni_etiquetas(almacen_memoria):
    rec = retrieval.recuperar(almacen_memoria, "cupones", k=2)
    mensajes = chains.construir_mensajes("¿Puedo usar dos cupones?", rec.chunks, "basico")
    assert len(mensajes) == 1 and mensajes[0].type == "human"
    assert "<fragmento" not in mensajes[0].content


def test_variante_mejorada_con_few_shot_y_reglas_de_credito(almacen_memoria):
    rec = retrieval.recuperar(almacen_memoria, "cuotas", k=2)
    extra = chains.cargar_prompts()["credito"]["reglas"]
    mensajes = chains.construir_mensajes("¿Me aprueban?", rec.chunks, "mejorado", extra)
    assert mensajes[0].type == "system" and "No calcules cuotas" in mensajes[0].content
    assert [m.type for m in mensajes[1:7]] == ["human", "ai"] * 3
    assert mensajes[-1].type == "human"  # Haiku 5.5 rechaza terminar en un turno del asistente


def test_plantillas_sin_variables_huerfanas():
    prompts = chains.cargar_prompts()
    assert variables_of(prompts["basico"]["user"]) == {"contexto", "pregunta"}
    assert variables_of(prompts["mejorado"]["user"]) == {"contexto", "pregunta"}
    assert variables_of(prompts["mejorado"]["system"]) == set()
    assert variables_of(prompts["credito"]["reglas"]) == set()


def test_variante_desconocida_falla():
    with pytest.raises(ValueError, match="Variante"):
        chains.construir_mensajes("x", [], "creativa")


def test_cadena_lcel_completa(almacen_memoria):
    llm = FakeChatModel(default=respuesta_extractiva)
    texto = chains.cadena_rag_lcel(almacen_memoria, llm, k=2).invoke("¿Cuánto cuesta el envío?")
    assert "[" in texto and texto.endswith("]")


# -- chequeos ----------------------------------------------------------------------------


def test_citas_validas_e_invalidas():
    fuentes = ["Envíos › Costos de envío"]
    assert checks.cita_fuentes_validas("Es gratis [Envíos › Costos de envío].", fuentes)[1]
    assert not checks.cita_fuentes_validas("Es gratis [Pagos › Inventado].", fuentes)[1]
    assert not checks.cita_fuentes_validas("Es gratis.", fuentes)[1]


def test_cifras_sin_respaldo_se_detectan():
    contexto = "Una compra de 650.000 pesos se puede pagar en 2 a 6 cuotas."
    ok = checks.cifras_soportadas("Puede pagar 650.000 pesos en hasta 6 cuotas.", contexto)
    malo = checks.cifras_soportadas("Cada cuota sería de 108.333 pesos.", contexto)
    porcentaje = checks.cifras_soportadas("La tasa es del 2,1% mensual.", contexto)
    assert ok[1] and not malo[1] and not porcentaje[1]


def test_detecta_idioma_y_abstencion():
    assert checks.detectar_idioma("How many days do I have to return a product?") == "en"
    assert checks.detectar_idioma("¿Cuántos días tengo para devolver un producto?") == "es"
    assert checks.es_abstencion("No tengo información sobre eso en los documentos.")
    assert not checks.es_abstencion("El envío es gratis desde 150.000 pesos.")


def test_no_menciona_pedidos_ajenos():
    assert not checks.sin_datos_de_pedidos("Su pedido ECO-1003 llegó.", "¿y mi envío?")[1]
    assert checks.sin_datos_de_pedidos("Su pedido ECO-1003 llegó.", "¿y ECO-1003?")[1]


def test_debe_contener_admite_alternativas():
    assert checks.contiene("La mantiene caliente 12 h.", ["12 horas|12 h"], [])[0][1]
    assert not checks.contiene("La mantiene caliente.", ["12 horas|12 h"], [])[0][1]
