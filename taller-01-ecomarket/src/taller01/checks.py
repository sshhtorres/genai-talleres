"""Validaciones automáticas de las respuestas, sin usar ningún LLM.

Son el "validador / guardrails" de la arquitectura de la Fase 1 en miniatura: comprueban que
la respuesta no contradiga los datos consultados. Cada chequeo devuelve (nombre, ok, detalle).
"""

from __future__ import annotations

import json
import re
from typing import Any

from . import data

Check = tuple[str, bool, str]

DISCULPAS = ("lament", "disculp", "sentimos", "perdón", "perdon")
APROBACIONES = ("aprobada", "aprobado", "procederemos con el reembolso", "reembolso aprobado")
REPOSICION = ("reposición", "reposicion", "reembolso", "cambio", "reemplaz")
ESCALAMIENTO = ("agente", "asesor", "persona", "humano", "equipo de soporte")
PETICIONES = (
    "indíqueme",
    "indiqueme",
    "indicarme",
    "comparta",
    "compartirme",
    "necesitamos",
    "necesito",
    "por favor",
    "facilíteme",
    "proporcione",
)

_FECHA_ISO = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")


def validar_pedido(
    respuesta: str,
    pedido: dict[str, Any] | list[dict[str, Any]] | None,
    tracking_consultado: str | None = None,
) -> list[Check]:
    """Chequeos del ejercicio 1.

    `pedido` acepta un registro o una lista, porque el cliente puede preguntar por varios
    pedidos en el mismo mensaje y la respuesta debe cubrirlos todos.
    """
    texto = (respuesta or "").lower()
    checks: list[Check] = []
    registros = [pedido] if isinstance(pedido, dict) else [p for p in (pedido or []) if p]

    if not registros:
        # El pedido no existe: lo único válido es decirlo y no inventar nada.
        inventados = [t for t in data.extraer_trackings(respuesta) if data.buscar_pedido(t)]
        checks.append(
            (
                "no_filtra_otros_pedidos",
                not inventados,
                f"menciona pedidos ajenos: {inventados}" if inventados else "ok",
            )
        )
        estados_inventados = [
            e
            for e in ("en tránsito", "en transito", "entregado el", "salió a reparto")
            if e in texto
        ]
        checks.append(
            (
                "no_inventa_estado",
                not estados_inventados,
                f"afirma un estado sin datos: {estados_inventados}" if estados_inventados else "ok",
            )
        )
        checks.append(
            (
                "no_inventa_fechas",
                not _FECHA_ISO.search(respuesta or ""),
                "incluye una fecha concreta sin tener datos"
                if _FECHA_ISO.search(respuesta or "")
                else "ok",
            )
        )
        pide_dato = any(p in texto for p in ("verific", "número de seguimiento", "numero de"))
        checks.append(
            ("pide_verificar_o_completar", pide_dato, "ok" if pide_dato else "no pide el número")
        )
        return checks

    trackings = {p["tracking_number"].upper() for p in registros}
    estados = {p["estado"] for p in registros}

    faltan_enlaces = [
        p["link_rastreo"] for p in registros if p["link_rastreo"].lower() not in texto
    ]
    checks.append(
        (
            "incluye_enlace_de_rastreo",
            not faltan_enlaces,
            "ok" if not faltan_enlaces else f"falta {', '.join(faltan_enlaces)}",
        )
    )

    # Un tracking es ajeno si no corresponde a ninguno de los pedidos consultados.
    ajenos = [t for t in data.extraer_trackings(respuesta) if t not in trackings]
    checks.append(("sin_trackings_ajenos", not ajenos, f"menciona {ajenos}" if ajenos else "ok"))

    # Cualquier fecha que aparezca en los registros es legítima, incluidas las que están
    # dentro de motivo_retraso u observacion.
    fechas_validas = set(_FECHA_ISO.findall(json.dumps(registros, ensure_ascii=False)))
    fechas_inventadas = [f for f in _FECHA_ISO.findall(respuesta or "") if f not in fechas_validas]
    checks.append(
        (
            "sin_fechas_inventadas",
            not fechas_inventadas,
            f"fechas que no están en el registro: {fechas_inventadas}"
            if fechas_inventadas
            else "ok",
        )
    )

    if estados & {"retrasado", "extraviado"}:
        disculpa = any(p in texto for p in DISCULPAS)
        checks.append(("incluye_disculpa", disculpa, "ok" if disculpa else "no se disculpa"))

    if "extraviado" in estados:
        escala = any(p in texto for p in ESCALAMIENTO)
        checks.append(
            ("ofrece_agente_humano", escala, "ok" if escala else "no ofrece escalamiento")
        )

    entregas = [
        p["fecha_entrega_real"]
        for p in registros
        if p["estado"] == "entregado" and p.get("fecha_entrega_real")
    ]
    if entregas:
        faltan = [f for f in entregas if f not in (respuesta or "")]
        checks.append(
            (
                "menciona_fecha_de_entrega",
                not faltan,
                "ok" if not faltan else f"falta {', '.join(faltan)}",
            )
        )

    if tracking_consultado and tracking_consultado.upper() not in trackings:
        checks.append(("tracking_coincide", False, "respondió por un pedido distinto"))

    return checks


def validar_devolucion(
    respuesta: str,
    regla: data.ReglaDevolucion,
    decision_modelo: dict[str, Any] | None,
) -> list[Check]:
    """Chequeos del ejercicio 2."""
    texto = (respuesta or "").lower()
    checks: list[Check] = []

    checks.append(
        (
            "json_de_decision_parseable",
            decision_modelo is not None,
            "ok" if decision_modelo is not None else "el modelo no devolvió un JSON válido",
        )
    )

    if decision_modelo is not None:
        coincide = str(decision_modelo.get("elegible", "")).lower() == regla.elegible
        checks.append(
            (
                "decision_coincide_con_la_regla",
                coincide,
                "ok"
                if coincide
                else (
                    f"el modelo dijo '{decision_modelo.get('elegible')}' y la regla en código "
                    f"dice '{regla.elegible}' ({regla.regla_aplicada})"
                ),
            )
        )

    if regla.elegible == "no":
        aprobaciones = [p for p in APROBACIONES if p in texto]
        checks.append(
            (
                "no_aprueba_lo_no_elegible",
                not aprobaciones,
                f"usa lenguaje de aprobación: {aprobaciones}" if aprobaciones else "ok",
            )
        )
        alternativa = any(
            p in texto for p in ("cupón", "cupon", "cambio", "descuento", *ESCALAMIENTO)
        )
        checks.append(
            (
                "ofrece_alternativa",
                alternativa,
                "ok" if alternativa else "no ofrece cambio, cupón ni agente humano",
            )
        )

    if regla.regla_aplicada == "excepcion_producto_defectuoso":
        menciona = any(p in texto for p in REPOSICION)
        checks.append(
            (
                "aplica_excepcion_por_dano",
                menciona,
                "ok" if menciona else "no ofrece reposición ni reembolso",
            )
        )

    if regla.datos_faltantes:
        # Pedir un dato puede ser una pregunta ("¿me comparte…?") o una petición cortés
        # ("por favor indíqueme…"); ambas formas son correctas.
        pide = "?" in (respuesta or "") or any(p in texto for p in PETICIONES)
        checks.append(
            ("pide_los_datos_faltantes", pide, "ok" if pide else "no pide los datos que faltan")
        )

    return checks


def resumen(checks: list[Check]) -> str:
    """Línea compacta para la salida de la CLI."""
    if not checks:
        return "sin chequeos"
    ok = sum(1 for _, valor, _ in checks if valor)
    return f"{ok}/{len(checks)} chequeos en verde"
