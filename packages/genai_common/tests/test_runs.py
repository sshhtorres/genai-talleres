"""Pruebas del registro de ejecuciones."""

from genai_common import RunRecord, RunRecorder


def test_escribe_jsonl_y_markdown(tmp_path):
    recorder = RunRecorder(tmp_path, proveedor="fake", modelo="m", fecha="2026-09-23")
    recorder.add(
        RunRecord(
            caso_id="ej1-retrasado",
            ejercicio="pedido",
            variante="mejorado",
            mensaje="¿dónde está ECO-1005?",
            respuesta="Tu pedido está retrasado.",
            checks=[("enlace_presente", True, "ok"), ("sin_invenciones", False, "falló")],
            metadatos={"latencia_s": 1.2, "tokens_entrada": 10, "tokens_salida": 5},
        )
    )
    jsonl, md = recorder.write()
    assert jsonl.exists() and md.exists()

    contenido = md.read_text(encoding="utf-8")
    assert "ej1-retrasado" in contenido
    assert "✓" in contenido and "✗" in contenido
    assert "2026-09-23" in contenido
    assert jsonl.read_text(encoding="utf-8").strip().startswith("{")


def test_record_ok_solo_si_todos_los_chequeos_pasan():
    base = dict(caso_id="c", ejercicio="pedido", variante="basico", mensaje="m", respuesta="r")
    assert RunRecord(**base, checks=[("a", True, "")]).ok
    assert not RunRecord(**base, checks=[("a", True, ""), ("b", False, "")]).ok
