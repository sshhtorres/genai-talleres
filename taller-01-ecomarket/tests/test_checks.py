"""Casos positivos y negativos de cada chequeo automático."""

from datetime import date

from taller01 import checks, data

HOY = date(2026, 9, 23)


def _dict(resultado):
    return {nombre: (ok, detalle) for nombre, ok, detalle in resultado}


# -- Ejercicio 1 --------------------------------------------------------------


def test_detecta_la_falta_del_enlace_de_rastreo():
    pedido = data.buscar_pedido("ECO-1001")
    sin_enlace = _dict(checks.validar_pedido("Su pedido va en camino.", pedido))
    assert sin_enlace["incluye_enlace_de_rastreo"][0] is False

    con_enlace = _dict(checks.validar_pedido(f"Va en camino: {pedido['link_rastreo']}", pedido))
    assert con_enlace["incluye_enlace_de_rastreo"][0] is True


def test_detecta_trackings_ajenos():
    pedido = data.buscar_pedido("ECO-1001")
    resultado = _dict(
        checks.validar_pedido(
            f"Su pedido ECO-1001 y también el ECO-1005. {pedido['link_rastreo']}", pedido
        )
    )
    assert resultado["sin_trackings_ajenos"][0] is False


def test_detecta_fechas_inventadas():
    pedido = data.buscar_pedido("ECO-1001")
    inventada = _dict(
        checks.validar_pedido(f"Llega el 2030-01-01. {pedido['link_rastreo']}", pedido)
    )
    assert inventada["sin_fechas_inventadas"][0] is False

    real = _dict(
        checks.validar_pedido(
            f"Llega el {pedido['fecha_estimada_entrega']}. {pedido['link_rastreo']}", pedido
        )
    )
    assert real["sin_fechas_inventadas"][0] is True


def test_exige_disculpa_solo_en_retrasados_y_extraviados():
    retrasado = data.buscar_pedido("ECO-1005")
    assert "incluye_disculpa" in _dict(checks.validar_pedido("texto", retrasado))
    entregado = data.buscar_pedido("ECO-1007")
    assert "incluye_disculpa" not in _dict(checks.validar_pedido("texto", entregado))


def test_exige_escalamiento_en_extraviados():
    extraviado = data.buscar_pedido("ECO-1011")
    sin_escalar = _dict(checks.validar_pedido("Lamentamos la demora.", extraviado))
    assert sin_escalar["ofrece_agente_humano"][0] is False
    con_escalar = _dict(
        checks.validar_pedido("Lamentamos la demora, un agente le contactará.", extraviado)
    )
    assert con_escalar["ofrece_agente_humano"][0] is True


def test_exige_la_fecha_real_en_los_entregados():
    entregado = data.buscar_pedido("ECO-1007")
    resultado = _dict(checks.validar_pedido(f"Enlace: {entregado['link_rastreo']}", entregado))
    assert resultado["menciona_fecha_de_entrega"][0] is False


def test_pedido_inexistente_detecta_invenciones():
    malo = _dict(checks.validar_pedido("Su pedido está en tránsito y llega el 2026-10-01.", None))
    assert malo["no_inventa_estado"][0] is False
    assert malo["no_inventa_fechas"][0] is False
    assert malo["pide_verificar_o_completar"][0] is False

    bueno = _dict(
        checks.validar_pedido(
            "No encontramos ese pedido. ¿Puede verificar el número de seguimiento?", None
        )
    )
    assert all(ok for ok, _ in bueno.values())


def test_pedido_inexistente_detecta_filtracion_de_otros_pedidos():
    resultado = _dict(checks.validar_pedido("Tenemos ECO-1001 y ECO-1002. Verifique.", None))
    assert resultado["no_filtra_otros_pedidos"][0] is False


def test_detecta_respuesta_sobre_otro_pedido():
    pedido = data.buscar_pedido("ECO-1001")
    resultado = _dict(
        checks.validar_pedido(pedido["link_rastreo"], pedido, tracking_consultado="ECO-1005")
    )
    assert resultado["tracking_coincide"][0] is False


def test_resumen_es_legible():
    assert checks.resumen([("a", True, ""), ("b", False, "")]) == "1/2 chequeos en verde"
    assert checks.resumen([]) == "sin chequeos"
