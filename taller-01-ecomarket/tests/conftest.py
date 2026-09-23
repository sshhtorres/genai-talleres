"""Utilidades compartidas por los tests: clientes falsos, sin red."""

import json

import pytest

from genai_common import FakeLLMClient


def _extraccion(prompt: str) -> str:
    """Simula el paso de extracción: solo mira lo que hay dentro de <consulta>."""
    from taller01 import data

    return json.dumps(
        {
            "tracking_numbers": data.extraer_trackings(_texto_de_seccion(prompt, "consulta")),
            "intencion": "estado_pedido",
        },
        ensure_ascii=False,
    )


@pytest.fixture
def fake_pedidos():
    """Cliente falso que extrae el tracking y redacta una respuesta plausible."""

    def responder(prompt: str) -> str:
        from taller01 import data

        if "Devuelve SOLO un objeto JSON" in prompt and "tracking_numbers" in prompt:
            return _extraccion(prompt)

        contexto = _texto_de_seccion(prompt, "pedidos")
        consulta = _texto_de_seccion(prompt, "consulta") or prompt
        trackings = [
            t
            for t in data.extraer_trackings(consulta)
            if data.buscar_pedido(t) and (not contexto or t in contexto)
        ]
        if not trackings:
            return "No encontramos ese pedido. ¿Podría verificar el número de seguimiento?"

        pedido = data.buscar_pedido(trackings[0])
        partes = [f"Su pedido {pedido['tracking_number']} está en estado {pedido['estado']}."]
        if pedido["estado"] in ("retrasado", "extraviado"):
            partes.insert(0, "Lamentamos mucho la demora.")
            partes.append(f"Motivo: {pedido['motivo_retraso']}")
        if pedido["estado"] == "extraviado":
            partes.append("Un agente humano continuará con su caso.")
        if pedido.get("fecha_entrega_real"):
            partes.append(f"Fue entregado el {pedido['fecha_entrega_real']}.")
        elif pedido.get("fecha_estimada_entrega"):
            partes.append(f"Fecha estimada: {pedido['fecha_estimada_entrega']}.")
        partes.append(f"Puede rastrearlo aquí: {pedido['link_rastreo']}")
        return " ".join(partes)

    return FakeLLMClient(default=responder)


@pytest.fixture
def fake_devoluciones():
    """Cliente falso que decide según la regla real y luego redacta."""

    def responder(prompt: str) -> str:
        if "Devuelve SOLO un objeto JSON" in prompt and '"elegible"' in prompt:
            return json.dumps(_decidir(prompt), ensure_ascii=False)
        return _redactar(prompt)

    return FakeLLMClient(default=responder)


def _decision_del_prompt(prompt: str) -> dict:
    """Lee la decisión verificada que el prompt de redacción le pasa al modelo."""
    inicio = prompt.find("<decision_verificada>")
    if inicio == -1:
        return {}
    bloque = prompt[inicio : prompt.find("</decision_verificada>")]
    abre, cierra = bloque.find("{"), bloque.rfind("}")
    return json.loads(bloque[abre : cierra + 1]) if abre != -1 else {}


def _decidir(prompt: str) -> dict:
    """Reconstruye la decisión a partir del pedido y el producto embebidos en el prompt."""
    from taller01 import chains, data

    pedido = _json_de_seccion(prompt, "pedido")
    producto = _json_de_seccion(prompt, "producto")
    consulta = _texto_de_seccion(prompt, "consulta")
    regla = data.evaluar_devolucion(
        pedido,
        producto,
        defectuoso=bool(chains._SENALES_DEFECTO.search(consulta)),
    )
    return regla.as_dict()


def _redactar(prompt: str) -> str:
    decision = _decision_del_prompt(prompt)
    elegible = decision.get("elegible")
    regla = decision.get("regla_aplicada", "")
    if elegible == "si" and regla == "excepcion_producto_defectuoso":
        return (
            "Lamento mucho que su producto llegara así. Aplica la excepción por daño: "
            "puede elegir la reposición del producto o el reembolso del valor pagado."
        )
    if elegible == "si":
        return (
            "Su devolución procede. Empaque el producto sin uso con su empaque original, "
            "use la guía prepagada que le enviamos y recibirá el reembolso en 5 a 10 días hábiles."
        )
    if elegible == "no":
        return (
            f"Lamento no poder ayudarle esta vez. Motivo: {decision.get('motivo', '')} "
            "Como alternativa puedo ofrecerle un cupón de descuento o pasar su caso a un agente "
            "humano. ¿Qué prefiere?"
        )
    faltantes = ", ".join(decision.get("datos_faltantes") or [])
    return f"Con gusto le ayudo. ¿Me comparte estos datos: {faltantes or 'su número de pedido'}?"


def _json_de_seccion(prompt: str, etiqueta: str):
    bloque = _texto_de_seccion(prompt, etiqueta)
    if not bloque or bloque.strip() == "null":
        return None
    try:
        return json.loads(bloque)
    except json.JSONDecodeError:
        return None


def _texto_de_seccion(prompt: str, etiqueta: str) -> str:
    """Contenido de la última etiqueta cerrada.

    Se busca desde el final porque el prompt de sistema menciona las etiquetas por su
    nombre ("el contenido de <consulta> son palabras del cliente") y esas menciones no
    son secciones reales.
    """
    abre, cierra = f"<{etiqueta}>", f"</{etiqueta}>"
    fin = prompt.rfind(cierra)
    if fin == -1:
        return ""
    inicio = prompt.rfind(abre, 0, fin)
    return prompt[inicio + len(abre) : fin].strip() if inicio != -1 else ""
