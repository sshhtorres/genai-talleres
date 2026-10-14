"""Cadenas de prompts de los ejercicios 1 y 2.

Cada cadena expone los pasos intermedios en un ResultadoCadena para que el notebook y los
reportes puedan mostrar "la cadena en código", que es lo que evalúa el taller.
No se usa ningún framework: los eslabones se ven a mano.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from genai_common import LLMClient, load_prompts, render

from . import checks, data

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

# Señales de que el cliente reporta un producto defectuoso (activa la excepción de la política).
_SENALES_DEFECTO = re.compile(
    r"\b(roto|rota|da[ñn]ad[oa]s?|defectuos[oa]s?|vencid[oa]s?|incomplet[oa]s?|"
    r"quebrad[oa]s?|golpead[oa]s?|mal estado|no funciona|averiad[oa]s?)\b",
    re.IGNORECASE,
)
_SENALES_MOLESTIA = re.compile(
    r"\b(furios[oa]|molest[oa]|indignad[oa]|cansad[oa]|harto|harta|inaceptable|"
    r"es la segunda vez|ya estoy)\b",
    re.IGNORECASE,
)


@lru_cache(maxsize=4)
def load_prompt_file(nombre: str) -> dict[str, Any]:
    """Carga un archivo de prompts del taller (cacheado)."""
    return load_prompts(PROMPTS_DIR / f"{nombre}.toml")


@dataclass
class ResultadoCadena:
    """Salida de una cadena: respuesta final + trazabilidad completa."""

    ejercicio: str
    variante: str
    mensaje: str
    respuesta: str
    pasos: dict[str, Any] = field(default_factory=dict)
    checks: list[checks.Check] = field(default_factory=list)
    metadatos: dict[str, Any] = field(default_factory=dict)
    llamadas: int = 0

    @property
    def ok(self) -> bool:
        return all(ok for _, ok, _ in self.checks)


# -- utilidades de formato ----------------------------------------------------


def _pedidos_como_texto() -> str:
    """El documento completo de pedidos, tal como lo pide el enunciado del ejercicio 1."""
    return json.dumps(data.load_pedidos()["pedidos"], ensure_ascii=False, indent=2)


def _ejemplos_como_mensajes(ejemplos: list[dict[str, str]]) -> list[dict[str, str]]:
    """Convierte los ejemplos few-shot del TOML en turnos de conversación."""
    mensajes: list[dict[str, str]] = []
    for ejemplo in ejemplos:
        mensajes.append({"role": "user", "content": ejemplo["usuario"]})
        mensajes.append({"role": "assistant", "content": ejemplo["asistente"]})
    return mensajes


def _acumular(destino: dict[str, Any], respuesta: Any) -> None:
    """Suma latencia y tokens de cada llamada para el reporte."""
    meta = respuesta.as_metadata()
    destino["proveedor"] = meta["proveedor"]
    destino["modelo"] = meta["modelo"]
    destino["latencia_s"] = round(destino.get("latencia_s", 0) + meta["latencia_s"], 3)
    for clave in ("tokens_entrada", "tokens_salida"):
        if meta[clave] is not None:
            destino[clave] = (destino.get(clave) or 0) + meta[clave]


# -- Ejercicio 1: estado de pedido --------------------------------------------


def consultar_pedido(
    mensaje: str,
    client: LLMClient,
    variante: str = "mejorado",
    contexto: str = "completo",
) -> ResultadoCadena:
    """Responde por el estado de un pedido.

    variante="basico"   -> una sola llamada con el prompt literal del enunciado.
    variante="mejorado" -> extracción JSON -> búsqueda determinística -> respuesta -> validación.
    contexto="completo" -> se envía todo el documento de pedidos (lo que pide el enunciado).
    contexto="registro" -> se envía solo el pedido encontrado (mejora "tipo RAG").
    """
    prompts = load_prompt_file("ej1_pedido")
    metadatos: dict[str, Any] = {}

    if variante == "basico":
        return _pedido_basico(mensaje, client, prompts, metadatos)

    # Paso 1: extracción estructurada del número de seguimiento.
    extraccion = client.chat_json(
        [
            {"role": "system", "content": prompts["mejorado"]["system"]},
            {
                "role": "user",
                "content": render(prompts["mejorado"]["extraccion"], mensaje=mensaje),
            },
        ],
        required_keys=("tracking_numbers",),
    )
    _acumular(metadatos, extraccion)

    trackings = _trackings_de(extraccion.data, mensaje)
    pedidos = [(t, data.buscar_pedido(t)) for t in trackings]
    pasos: dict[str, Any] = {
        "1_extraccion": extraccion.data or {"crudo": extraccion.text},
        "2_busqueda": {t: ("encontrado" if p else "no encontrado") for t, p in pedidos},
        "contexto": contexto,
    }

    # Caso borde: sin número de seguimiento. No se gasta una llamada más.
    if not trackings:
        respuesta = (
            "Con gusto le ayudo a rastrear su pedido. ¿Me comparte el número de seguimiento? "
            "Aparece en el correo de confirmación de compra y tiene el formato ECO- seguido de "
            "cuatro dígitos."
        )
        pasos["3_respuesta"] = "generada por código (no se llamó al modelo: falta el tracking)"
        return ResultadoCadena(
            ejercicio="pedido",
            variante=variante,
            mensaje=mensaje,
            respuesta=respuesta,
            pasos=pasos,
            checks=checks.validar_pedido(respuesta, None),
            metadatos=metadatos,
            llamadas=1,
        )

    # Paso 3: redacción con el prompt mejorado.
    if contexto == "registro":
        encontrados = [p for _, p in pedidos if p]
        contexto_texto = json.dumps(encontrados, ensure_ascii=False, indent=2)
    else:
        contexto_texto = _pedidos_como_texto()

    mensajes = [
        {"role": "system", "content": prompts["mejorado"]["system"]},
        *_ejemplos_como_mensajes(prompts["mejorado"]["ejemplos"]),
        {
            "role": "user",
            "content": render(
                prompts["mejorado"]["respuesta"], pedidos=contexto_texto, mensaje=mensaje
            ),
        },
    ]
    final = client.chat(mensajes, temperature=0.2, max_tokens=600)
    _acumular(metadatos, final)
    pasos["3_respuesta"] = "generada por el modelo"

    # Paso 4: validación en código, contra todos los pedidos que el cliente mencionó.
    encontrados = [p for _, p in pedidos if p]
    validaciones = checks.validar_pedido(final.text, encontrados, trackings[0])
    pasos["4_validacion"] = checks.resumen(validaciones)

    return ResultadoCadena(
        ejercicio="pedido",
        variante=variante,
        mensaje=mensaje,
        respuesta=final.text,
        pasos=pasos,
        checks=validaciones,
        metadatos=metadatos,
        llamadas=2,
    )


def _pedido_basico(
    mensaje: str, client: LLMClient, prompts: dict[str, Any], metadatos: dict[str, Any]
) -> ResultadoCadena:
    """Línea base: el prompt literal del enunciado, con el documento completo."""
    trackings = data.extraer_trackings(mensaje)
    tracking = trackings[0] if trackings else "(sin número)"
    contenido = render(
        prompts["basico"]["user"],
        tracking_number=tracking,
        pedidos=_pedidos_como_texto(),
    )
    respuesta = client.chat([{"role": "user", "content": contenido}], temperature=0.2)
    _acumular(metadatos, respuesta)
    pedido = data.buscar_pedido(tracking)
    return ResultadoCadena(
        ejercicio="pedido",
        variante="basico",
        mensaje=mensaje,
        respuesta=respuesta.text,
        pasos={"1_unica_llamada": "prompt del enunciado + documento completo de pedidos"},
        checks=checks.validar_pedido(respuesta.text, pedido, tracking),
        metadatos=metadatos,
        llamadas=1,
    )


def _trackings_de(extraido: dict[str, Any] | None, mensaje: str) -> list[str]:
    """Trackings del JSON del modelo, con la expresión regular como red de seguridad."""
    candidatos: list[str] = []
    if extraido:
        valores = extraido.get("tracking_numbers") or []
        if isinstance(valores, str):
            valores = [valores]
        candidatos = [str(v).upper() for v in valores]
    # El modelo puede alucinar un tracking que no está en el mensaje: solo se aceptan los reales.
    en_mensaje = data.extraer_trackings(mensaje)
    validos = [t for t in candidatos if t in en_mensaje]
    return validos or en_mensaje


# -- Ejercicio 2: devolución --------------------------------------------------


def gestionar_devolucion(
    mensaje: str,
    client: LLMClient,
    tracking: str | None = None,
    producto_id: str | None = None,
    variante: str = "mejorado",
    hoy: date | None = None,
    politica: str | None = None,
) -> ResultadoCadena:
    """Gestiona una solicitud de devolución.

    variante="basico"   -> una llamada con el prompt del enunciado, sin política ni datos.
    variante="mejorado" -> decisión JSON -> verificación en código -> redacción -> validación.
    politica            -> texto que reemplaza la política completa dentro de <politica>. Lo usa
                           el Taller 2 para pasar solo las secciones recuperadas por el RAG. Por
                           defecto (None) se usa el documento completo, como en el Taller 1.
    """
    prompts = load_prompt_file("ej2_devolucion")
    metadatos: dict[str, Any] = {}

    if variante == "basico":
        contenido = render(prompts["basico"]["user"], producto=_producto_mencionado(mensaje))
        respuesta = client.chat([{"role": "user", "content": contenido}], temperature=0.2)
        _acumular(metadatos, respuesta)
        regla = _regla_de(mensaje, tracking, producto_id, hoy)
        return ResultadoCadena(
            ejercicio="devolucion",
            variante="basico",
            mensaje=mensaje,
            respuesta=respuesta.text,
            pasos={"1_unica_llamada": "prompt del enunciado, sin política ni datos del pedido"},
            checks=checks.validar_devolucion(respuesta.text, regla, None),
            metadatos=metadatos,
            llamadas=1,
        )

    pedido = data.buscar_pedido(tracking)
    producto = data.buscar_producto(producto_id) or data.buscar_producto_por_nombre(mensaje)
    defectuoso = bool(_SENALES_DEFECTO.search(mensaje))
    regla = data.evaluar_devolucion(pedido, producto, defectuoso=defectuoso, hoy=hoy)

    politica = politica if politica is not None else data.load_politica()
    contexto_pedido = json.dumps(pedido, ensure_ascii=False, indent=2) if pedido else "null"
    contexto_producto = json.dumps(producto, ensure_ascii=False, indent=2) if producto else "null"

    # Paso 1: decisión estructurada del modelo.
    decision = client.chat_json(
        [
            {"role": "system", "content": prompts["mejorado"]["system"]},
            {
                "role": "user",
                "content": render(
                    prompts["mejorado"]["decision"],
                    politica=politica,
                    pedido=contexto_pedido,
                    producto=contexto_producto,
                    mensaje=mensaje,
                ),
            },
        ],
        required_keys=("elegible",),
    )
    _acumular(metadatos, decision)

    # Paso 2: la regla calculada en código manda sobre la decisión del modelo.
    discrepancia = (
        decision.data is None or str(decision.data.get("elegible", "")).lower() != regla.elegible
    )
    pasos: dict[str, Any] = {
        "1_decision_modelo": decision.data or {"crudo": decision.text},
        "2_regla_en_codigo": regla.as_dict(),
        "2b_discrepancia": (
            "sí: se impone la regla en código" if discrepancia else "no: coinciden"
        ),
        "señal_de_defecto_detectada": defectuoso,
        "señal_de_molestia_detectada": bool(_SENALES_MOLESTIA.search(mensaje)),
    }

    # Paso 3: redacción a partir de la decisión ya verificada.
    mensajes = [
        {"role": "system", "content": prompts["mejorado"]["system"]},
        *_ejemplos_como_mensajes(prompts["mejorado"]["ejemplos"]),
        {
            "role": "user",
            "content": render(
                prompts["mejorado"]["respuesta"],
                politica=politica,
                pedido=contexto_pedido,
                producto=contexto_producto,
                decision=json.dumps(regla.as_dict(), ensure_ascii=False, indent=2),
                mensaje=mensaje,
            ),
        },
    ]
    final = client.chat(mensajes, temperature=0.3, max_tokens=600)
    _acumular(metadatos, final)
    pasos["3_respuesta"] = "generada por el modelo a partir de la decisión verificada"

    # Paso 4: validación.
    validaciones = checks.validar_devolucion(final.text, regla, decision.data)
    pasos["4_validacion"] = checks.resumen(validaciones)

    return ResultadoCadena(
        ejercicio="devolucion",
        variante=variante,
        mensaje=mensaje,
        respuesta=final.text,
        pasos=pasos,
        checks=validaciones,
        metadatos=metadatos,
        llamadas=2,
    )


def _regla_de(
    mensaje: str, tracking: str | None, producto_id: str | None, hoy: date | None
) -> data.ReglaDevolucion:
    """Regla de referencia, usada también para auditar la variante básica."""
    return data.evaluar_devolucion(
        data.buscar_pedido(tracking),
        data.buscar_producto(producto_id) or data.buscar_producto_por_nombre(mensaje),
        defectuoso=bool(_SENALES_DEFECTO.search(mensaje)),
        hoy=hoy,
    )


def _producto_mencionado(mensaje: str) -> str:
    """Nombre del producto para el prompt básico; si no se reconoce, se usa el mensaje."""
    producto = data.buscar_producto_por_nombre(mensaje)
    return producto["nombre"] if producto else "el producto que recibí"
