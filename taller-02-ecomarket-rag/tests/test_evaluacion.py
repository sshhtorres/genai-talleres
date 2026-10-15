"""Métricas, calibración y experimentos (H7), con embeddings y LLM falsos."""

import json

import pytest

from taller02_rag import evaluation, experimentos, kb


def _resultado(rango, score=0.5, tipo="dentro_alcance"):
    return evaluation.ResultadoRecuperacion(
        caso_id="x",
        tipo=tipo,
        doc_esperado="politicas-y-faq",
        idioma_pregunta="es",
        idioma_documento="es",
        rango=rango,
        mejor_score=score,
        score_acierto=score if rango else None,
    )


def test_hit_y_mrr():
    resultados = [_resultado(1), _resultado(3), _resultado(None)]
    m = evaluation.metricas(resultados)
    assert m == {
        "casos": 3,
        "hit@1": round(1 / 3, 3),
        "hit@4": round(2 / 3, 3),
        "mrr": round((1 + 1 / 3) / 3, 3),
    }


def test_acierto_por_evidencia_y_documento():
    fuente = {
        "doc_id": "reglas-credito",
        "seccion_o_id": "CR-05",
        "evidencia": "200.000 pesos o más",
    }
    assert evaluation.acierta("Solo compras de 200.000 pesos   o más.", "reglas-credito", fuente)
    assert not evaluation.acierta("Solo compras de 200.000 pesos o más.", "catalogo", fuente)
    assert not evaluation.acierta("Compras de 200.000", "reglas-credito", fuente)


def test_recuperacion_sobre_la_base_en_memoria(almacen_memoria):
    resultados = evaluation.evaluar_recuperacion(almacen_memoria)
    assert len(resultados) == len(evaluation.casos_con_fuente())
    resumen = evaluation.resumen_recuperacion(resultados)
    assert {"global", "translingue", "doc:catalogo"} <= set(resumen)
    assert 0 <= resumen["global"]["hit@1"] <= resumen["global"]["hit@4"] <= 1


def test_calibracion_separa_y_respeta_translingues():
    grupos = {
        "dentro": [("a", 0.8), ("b", 0.7), ("c", 0.65)],
        "fuera": [("d", 0.3), ("e", 0.4)],
        "translingue": [("f", 0.5)],
    }
    cal = evaluation.calibrar_umbral("x", grupos)
    assert 0.4 < cal.umbral <= 0.5  # separa dentro de fuera sin dejar fuera al translingüe
    assert cal.exactitud == 1.0 and cal.abstenciones_translingues == 0


def test_calibracion_avisa_si_un_translingue_puntua_bajo():
    grupos = {"dentro": [("a", 0.8)], "fuera": [("b", 0.5)], "translingue": [("c", 0.4)]}
    cal = evaluation.calibrar_umbral("x", grupos)
    assert cal.umbral <= 0.4 and cal.abstenciones_translingues == 0
    assert "translingüe" in cal.nota


def test_histograma_marca_el_umbral():
    cal = evaluation.calibrar_umbral(
        "x", {"dentro": [("a", 0.72)], "fuera": [("b", 0.31)], "translingue": []}
    )
    lineas = evaluation.histograma(cal)
    assert any("D" in linea for linea in lineas) and any("F" in linea for linea in lineas)
    assert sum("← umbral" in linea for linea in lineas) == 1


def test_guardar_umbral_solo_toca_su_perfil(tmp_path):
    import tomllib

    from taller02_rag.config import PARAMETROS

    copia = tmp_path / "parametros.toml"
    copia.write_text(PARAMETROS.read_text(encoding="utf-8"), encoding="utf-8")
    antes = tomllib.loads(copia.read_text(encoding="utf-8"))["recuperacion"]["umbral"]
    evaluation.guardar_umbral("embeddinggemma", 0.4321, copia)
    despues = tomllib.loads(copia.read_text(encoding="utf-8"))["recuperacion"]["umbral"]
    # Solo cambia el perfil indicado; los demás conservan su valor (calibrado o no).
    assert despues["embeddinggemma"] == 0.4321
    assert {k: v for k, v in despues.items() if k != "embeddinggemma"} == {
        k: v for k, v in antes.items() if k != "embeddinggemma"
    }
    with pytest.raises(ValueError):
        evaluation.guardar_umbral("inexistente", 0.1, copia)


def test_checks_del_caso_exige_lo_que_dice_el_set():
    caso = next(c for c in kb.casos_rag() if c["id"] == "trampa-02")
    respuesta = "Cada cuota sería de 108.333 pesos [Reglas de crédito › CR-06 · x]."
    fallidos = {
        n for n, ok, _ in evaluation.checks_del_caso(caso, respuesta, "650.000 pesos") if not ok
    }
    assert {"cifras_con_respaldo", "no_contiene:108.333", "contiene:simulador"} <= fallidos


# -- experimentos de punta a punta con los modelos falsos --------------------------------------


@pytest.fixture
def opciones(tmp_path, sin_env):
    sin_env.setenv("RAG_CONFIG", "pruebas")
    return experimentos.Opciones(
        backend="memoria", pausa_s=0, limite=3, outputs_dir=tmp_path, progreso=lambda _: None
    )


def test_e1_compara_basico_y_mejorado(opciones):
    (md,) = experimentos.correr("E1", opciones)
    registros = [json.loads(x) for x in md.with_suffix(".jsonl").read_text().splitlines()]
    assert {r["variante"] for r in registros} == {"basico", "mejorado"}
    assert len(registros) == 6
    assert md.name.startswith("E1_") and md.name.endswith("_fake.md")


def test_e2_mide_las_tres_estrategias(opciones):
    (md,) = experimentos.correr("E2", opciones)
    texto = md.read_text()
    assert all(e in texto for e in ("por_tipo", "fija300", "fija1000"))
    assert md.name.endswith("_fake.md")


def test_e3_resume_tokens_por_k(opciones):
    (md,) = experimentos.correr("E3", opciones)
    assert "Tokens de entrada por k" in md.read_text() and "k=8" in md.read_text()


def test_e4_con_un_perfil(opciones):
    opciones.perfiles = ("fake",)
    (md,) = experimentos.correr("E4", opciones)
    assert "Latencia y memoria" in md.read_text()


def test_e5_compara_sin_y_con_rag(opciones):
    (md,) = experimentos.correr("E5", opciones)
    registros = [json.loads(x) for x in md.with_suffix(".jsonl").read_text().splitlines()]
    assert {r["variante"] for r in registros} == {"sin_rag", "con_rag"}


def test_e7_sin_resumenes_es_accionable(opciones, monkeypatch, tmp_path):
    from genai_common import ConfigError
    from taller02_rag import enriquecimiento

    monkeypatch.setattr(enriquecimiento, "DIR_ENRIQUECIDO", tmp_path / "vacio")
    with pytest.raises(ConfigError, match="taller02 enriquecer"):
        experimentos.correr("E7", opciones)


def test_e7_con_resumenes(opciones, monkeypatch, tmp_path):
    from genai_common.lc import FakeChatModel
    from taller02_rag import enriquecimiento

    monkeypatch.setattr(enriquecimiento, "DIR_ENRIQUECIDO", tmp_path / "enriq")
    estado = enriquecimiento.generar(FakeChatModel(default="Cepillo de bambú con cerdas sin BPA."))
    assert [e for _, e in estado] == ["generado"] * 4
    assert enriquecimiento.leer_resumen("P-101") == "Cepillo de bambú con cerdas sin BPA."
    (md,) = experimentos.correr("E7", opciones)
    assert "Sesgo de idioma" in md.read_text()


def test_e8_mide_ttft_y_resume(opciones):
    opciones.configuraciones = ("pruebas",)
    reportes = experimentos.correr("E8", opciones)
    resumen = reportes[-1].read_text()
    assert "TTFT" in resumen and "| pruebas |" in resumen
    registro = json.loads(reportes[0].with_suffix(".jsonl").read_text().splitlines()[0])
    assert registro["metadatos"]["ttft_s"] is not None


def test_experimento_desconocido():
    with pytest.raises(ValueError, match="Experimento desconocido"):
        experimentos.correr("E9", experimentos.Opciones())


def test_costo_con_precio_verificado():
    meta = {"tokens_entrada": 1_000_000, "tokens_salida": 1_000_000}
    assert experimentos._costo(meta, {"entrada": 0.10, "salida": 0.50}) == 0.6
    assert experimentos._costo(meta, None) is None


def test_e1_reporta_con_y_sin_el_chequeo_de_citas(opciones):
    (md,) = experimentos.correr("E1", opciones)
    texto = md.read_text()
    assert "Sin contar `cita_una_fuente`" in texto
    assert "| basico |" in texto and "| mejorado |" in texto


def test_tabla_e1_excluye_solo_las_citas():
    def registro(variante, *checks):
        return {"variante": variante, "checks": [{"nombre": n, "ok": ok} for n, ok in checks]}

    registros = [
        registro("basico", ("cita_una_fuente", False), ("idioma", True)),
        registro("basico", ("cita_una_fuente", False), ("idioma", False)),
        registro("mejorado", ("cita_una_fuente", True), ("idioma", True)),
    ]
    filas = experimentos.tabla_e1(registros)
    assert "| basico | 2 | 0 | 0.0 | 1 | 50.0 |" in filas
    assert "| mejorado | 1 | 1 | 100.0 | 1 | 100.0 |" in filas


def test_e5_no_falla_si_el_router_manda_a_devolucion(opciones, monkeypatch):
    # Antes: AttributeError al leer r.detalle.recuperacion de un resultado del Taller 1.
    caso = {
        "id": "x-01",
        "mensaje": "¿Puedo devolver un producto que ya abrí?",
        "tipo": "reformulacion",
        "intencion_esperada": "consulta_general",
        "fuentes_esperadas": [],
        "debe_contener": [],
        "no_debe_contener": [],
        "debe_abstenerse": False,
        "idioma_respuesta": "es",
        "cifras_con_respaldo": True,
    }
    monkeypatch.setattr(kb, "casos_rag", lambda: [caso])
    (md,) = experimentos.correr("E5", opciones)
    registros = [json.loads(x) for x in md.with_suffix(".jsonl").read_text().splitlines()]
    con_rag = next(r for r in registros if r["variante"] == "con_rag")
    assert con_rag["metadatos"]["ruta"] == "devolucion"


def test_muestra_estratificada_alterna_tipos():
    casos = [{"id": f"d{i}", "tipo": "dentro_alcance"} for i in range(5)] + [
        {"id": "f1", "tipo": "fuera_alcance"},
        {"id": "t1", "tipo": "translingue"},
    ]
    muestra = experimentos.muestra_estratificada(casos, 4)
    assert [c["id"] for c in muestra] == ["d0", "f1", "t1", "d1"]
    assert len(experimentos.muestra_estratificada(casos, 50)) == len(casos)
