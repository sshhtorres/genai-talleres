"""Carga y búsqueda determinística en los datos sintéticos de EcoMarket.

Este módulo hace el papel de "los sistemas de la empresa" de la arquitectura de la Fase 1:
el LLM nunca adivina un estado de pedido, lo consulta aquí.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

TRACKING_RE = re.compile(r"\bECO-\d{4}\b", re.IGNORECASE)

ESTADOS_SIN_ENTREGA = {"en_preparacion", "en_transito", "en_reparto", "retrasado", "extraviado"}
PLAZO_DEVOLUCION_DIAS = 30
PLAZO_RETRACTO_DIAS_HABILES = 5
CATEGORIAS_NO_RETORNABLES = {
    "alimentos_perecederos",
    "granel",
    "tarjeta_regalo",
    "personalizado",
}


def data_dir() -> Path:
    """Carpeta data/ del taller."""
    return Path(__file__).resolve().parents[2] / "data"


@lru_cache(maxsize=1)
def load_pedidos() -> dict[str, Any]:
    """Documento completo de pedidos."""
    return json.loads((data_dir() / "pedidos.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_catalogo() -> dict[str, Any]:
    """Catálogo completo de productos."""
    return json.loads((data_dir() / "catalogo.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_politica() -> str:
    """Texto de la política de devoluciones."""
    return (data_dir() / "politica_devoluciones.md").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_casos() -> list[dict[str, Any]]:
    """Casos de prueba declarados en YAML."""
    return yaml.safe_load((data_dir() / "casos_prueba.yaml").read_text(encoding="utf-8"))


def fecha_referencia() -> date:
    """Fecha 'de hoy' del escenario, para que los cálculos de plazo sean reproducibles."""
    return date.fromisoformat(load_pedidos()["fecha_referencia"])


# -- búsquedas ----------------------------------------------------------------


def extraer_trackings(texto: str) -> list[str]:
    """Números de seguimiento presentes en un texto libre, sin repetir y en orden."""
    vistos: list[str] = []
    for encontrado in TRACKING_RE.findall(texto or ""):
        normalizado = encontrado.upper()
        if normalizado not in vistos:
            vistos.append(normalizado)
    return vistos


def buscar_pedido(tracking: str | None) -> dict[str, Any] | None:
    """Pedido por número de seguimiento, o None si no existe."""
    if not tracking:
        return None
    objetivo = tracking.strip().upper()
    for pedido in load_pedidos()["pedidos"]:
        if pedido["tracking_number"].upper() == objetivo:
            return pedido
    return None


def buscar_producto(producto_id: str | None) -> dict[str, Any] | None:
    """Producto del catálogo por id."""
    if not producto_id:
        return None
    objetivo = producto_id.strip().upper()
    for producto in load_catalogo()["productos"]:
        if producto["id"].upper() == objetivo:
            return producto
    return None


def buscar_producto_por_nombre(texto: str) -> dict[str, Any] | None:
    """Coincidencia laxa de un producto por palabras clave del mensaje del cliente."""
    if not texto:
        return None
    normalizado = _normalizar(texto)
    mejor: tuple[int, dict[str, Any]] | None = None
    for producto in load_catalogo()["productos"]:
        palabras = [p for p in _normalizar(producto["nombre"]).split() if len(p) > 3]
        aciertos = sum(1 for palabra in palabras if palabra in normalizado)
        if aciertos and (mejor is None or aciertos > mejor[0]):
            mejor = (aciertos, producto)
    return mejor[1] if mejor else None


def productos_del_pedido(pedido: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Productos de un pedido, enriquecidos con los datos del catálogo."""
    if not pedido:
        return []
    enriquecidos = []
    for item in pedido["productos"]:
        catalogo = buscar_producto(item["id"]) or {}
        enriquecidos.append({**item, **{k: v for k, v in catalogo.items() if k not in item}})
    return enriquecidos


def _normalizar(texto: str) -> str:
    tabla = str.maketrans("áéíóúüñ", "aeiouun")
    return texto.lower().translate(tabla)


# -- reglas de negocio (la verdad contra la que se valida al LLM) --------------


@dataclass(frozen=True)
class ReglaDevolucion:
    """Resultado de aplicar la política en código, sin intervención del LLM."""

    elegible: str  # "si" | "no" | "requiere_revision"
    motivo: str
    regla_aplicada: str
    datos_faltantes: tuple[str, ...] = ()
    dias_desde_entrega: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "elegible": self.elegible,
            "motivo": self.motivo,
            "regla_aplicada": self.regla_aplicada,
            "datos_faltantes": list(self.datos_faltantes),
            "dias_desde_entrega": self.dias_desde_entrega,
        }


def dias_desde_entrega(pedido: dict[str, Any] | None, hoy: date | None = None) -> int | None:
    """Días transcurridos desde la entrega real; None si el pedido no se ha entregado."""
    if not pedido or not pedido.get("fecha_entrega_real"):
        return None
    entrega = datetime.fromisoformat(pedido["fecha_entrega_real"]).date()
    return ((hoy or fecha_referencia()) - entrega).days


def es_no_retornable(producto: dict[str, Any] | None) -> bool:
    """True si la categoría o la bandera del catálogo lo marcan como no retornable."""
    if not producto:
        return False
    return producto.get("categoria") in CATEGORIAS_NO_RETORNABLES or not producto.get(
        "retornable", True
    )


def evaluar_devolucion(
    pedido: dict[str, Any] | None,
    producto: dict[str, Any] | None,
    defectuoso: bool = False,
    hoy: date | None = None,
) -> ReglaDevolucion:
    """Aplica la política de devoluciones en código puro.

    El orden de las reglas importa: primero los datos faltantes, luego el estado del pedido,
    luego la excepción por defecto (que vence a la categoría) y por último plazo y categoría.
    """
    faltantes: list[str] = []
    if pedido is None:
        faltantes.append("numero_de_pedido")
    if producto is None:
        faltantes.append("producto")
    if faltantes:
        return ReglaDevolucion(
            elegible="requiere_revision",
            motivo="Faltan datos para aplicar la política.",
            regla_aplicada="datos_incompletos",
            datos_faltantes=tuple(faltantes),
        )

    assert pedido is not None and producto is not None  # para el verificador de tipos
    estado = pedido["estado"]

    if estado in ESTADOS_SIN_ENTREGA:
        return ReglaDevolucion(
            elegible="requiere_revision",
            motivo=(
                f"El pedido está en estado '{estado}': todavía no ha sido entregado, "
                "así que no procede una devolución sino una cancelación o un seguimiento."
            ),
            regla_aplicada="pedido_no_entregado",
        )

    if estado == "cancelado":
        return ReglaDevolucion(
            elegible="no",
            motivo="El pedido fue cancelado y su reembolso ya se gestionó.",
            regla_aplicada="pedido_cancelado",
        )

    if estado == "devuelto":
        return ReglaDevolucion(
            elegible="no",
            motivo="El pedido ya fue devuelto y reembolsado previamente.",
            regla_aplicada="pedido_ya_devuelto",
        )

    dias = dias_desde_entrega(pedido, hoy)

    if defectuoso:
        return ReglaDevolucion(
            elegible="si",
            motivo=(
                "El producto llegó defectuoso o dañado: aplica la excepción de la política "
                "y la garantía legal (Ley 1480 de 2011), aunque el producto no sea retornable."
            ),
            regla_aplicada="excepcion_producto_defectuoso",
            dias_desde_entrega=dias,
        )

    if es_no_retornable(producto):
        return ReglaDevolucion(
            elegible="no",
            motivo=(
                f"El producto pertenece a la categoría '{producto['categoria']}', "
                "que no admite devolución salvo defecto o daño."
            ),
            regla_aplicada="categoria_no_retornable",
            dias_desde_entrega=dias,
        )

    if dias is not None and dias > PLAZO_DEVOLUCION_DIAS:
        return ReglaDevolucion(
            elegible="no",
            motivo=(
                f"Han pasado {dias} días desde la entrega y el plazo de devolución "
                f"es de {PLAZO_DEVOLUCION_DIAS} días."
            ),
            regla_aplicada="fuera_de_plazo",
            dias_desde_entrega=dias,
        )

    return ReglaDevolucion(
        elegible="si",
        motivo=(
            f"Producto retornable y dentro del plazo ({dias} de {PLAZO_DEVOLUCION_DIAS} días "
            "desde la entrega)."
        ),
        regla_aplicada="retornable_en_plazo",
        dias_desde_entrega=dias,
    )
