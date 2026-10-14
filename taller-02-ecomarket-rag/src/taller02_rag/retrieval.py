"""Recuperación: los k chunks más parecidos a la pregunta, con *score*, filtro y umbral.

El *score* es la **similitud coseno en [0, 1]** (más alto = más parecido), ya normalizada por
`AlmacenVectorial`: pgvector devuelve distancia y aquí se convierte. La decisión
`hay_evidencia = mejor_score >= umbral` se toma ANTES de llamar al LLM: si no hay evidencia, se
responde desde código y no se gasta la llamada (mismo patrón del Taller 1 cuando falta el tracking).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from .config import parametros
from .store import AlmacenVectorial


def etiqueta_fuente(documento: Document) -> str:
    """Cómo se cita un chunk: su sección, o el documento si la estrategia no la conserva."""
    seccion = documento.metadata.get("seccion")
    if seccion:
        return seccion
    return f"{documento.metadata.get('doc_id', 'documento')} (fragmento)"


@dataclass
class ChunkRecuperado:
    documento: Document
    similitud: float

    @property
    def fuente(self) -> str:
        return etiqueta_fuente(self.documento)

    @property
    def idioma(self) -> str:
        return self.documento.metadata.get("idioma", "es")

    @property
    def texto(self) -> str:
        return self.documento.page_content

    def resumen(self) -> dict[str, Any]:
        m = self.documento.metadata
        return {
            "fuente": self.fuente,
            "similitud": self.similitud,
            "tipo": m.get("tipo"),
            "idioma": m.get("idioma"),
            "chunk_id": m.get("chunk_id"),
        }


@dataclass
class Recuperacion:
    pregunta: str
    chunks: list[ChunkRecuperado]
    k: int
    umbral: float
    filtro: dict[str, Any] | None = None
    notas: list[str] = field(default_factory=list)

    @property
    def mejor_score(self) -> float:
        return max((c.similitud for c in self.chunks), default=0.0)

    @property
    def hay_evidencia(self) -> bool:
        return bool(self.chunks) and self.mejor_score >= self.umbral

    @property
    def fuentes(self) -> list[str]:
        return list(dict.fromkeys(c.fuente for c in self.chunks))


def umbral_de(perfil: str) -> float:
    """Umbral calibrado para un perfil de embeddings (0.0 si aún no se calibró)."""
    return float(parametros()["recuperacion"]["umbral"].get(perfil, 0.0))


def recuperar(
    almacen: AlmacenVectorial,
    pregunta: str,
    k: int | None = None,
    filtro: dict[str, Any] | None = None,
    umbral: float | None = None,
) -> Recuperacion:
    """Búsqueda con *scores*. `k` y `umbral` salen de parametros.toml si no se dan; el umbral es
    el del perfil de embeddings del almacén."""
    p = parametros()["recuperacion"]
    k = k or p["k"]
    umbral = umbral_de(almacen.perfil) if umbral is None else umbral
    resultados = almacen.buscar(pregunta, k=k, filtro=filtro)
    return Recuperacion(
        pregunta=pregunta,
        chunks=[ChunkRecuperado(d, s) for d, s in resultados],
        k=k,
        umbral=umbral,
        filtro=filtro,
    )


def como_runnable(
    almacen: AlmacenVectorial,
    k: int | None = None,
    filtro: dict[str, Any] | None = None,
    umbral: float | None = None,
) -> RunnableLambda:
    """El recuperador como eslabón LCEL: pregunta (str) -> Recuperacion."""
    return RunnableLambda(lambda pregunta: recuperar(almacen, pregunta, k, filtro, umbral))
