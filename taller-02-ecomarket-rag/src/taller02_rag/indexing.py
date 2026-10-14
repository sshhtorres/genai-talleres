"""Pipeline de indexación: cargar → limpiar → dividir → enriquecer → embeber → guardar → indexar.

Las funciones puras (`preparar_chunks`, `enriquecer`, `plan_de_cambios`) están separadas de la E/S
(`indexar`) para poder probarlas sin red. La indexación es **idempotente**: el id de cada chunk es
un hash de su documento y su contenido, así que volver a indexar sin cambios no agrega nada, no
vuelve a calcular embeddings y no duplica; y si un documento cambió, sus chunks viejos se borran.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from langchain_core.documents import Document

from . import chunking, loaders
from .config import parametros
from .store import AlmacenVectorial

# Paso 7, verificación: una consulta de humo por tipo de documento (sin filtro), con el tipo que
# debería salir primero.
CONSULTAS_DE_HUMO = {
    "politicas": "¿Cuántos días tengo para devolver un producto?",
    "credito": "¿Cuál es el monto mínimo para financiar una compra en cuotas?",
    "producto": "¿El vaso de vidrio se puede lavar en el lavavajillas?",
    "terminos": "¿En cuánto tiempo llega la factura electrónica?",
}

# Espacio de nombres fijo para los UUID determinísticos de los chunks.
_NAMESPACE = uuid.UUID("6f1f2b0e-2b7a-4c55-9a3e-0e5c0f3a7d21")


def preparar_chunks(
    estrategia: str = chunking.ESTRATEGIA_POR_DEFECTO, enriquecer_ingles: bool = False
) -> list[Document]:
    """Pasos 1 a 3: carga, limpieza y división de los cuatro tipos de documento."""
    return enriquecer(chunking.dividir(loaders.cargar_todo(enriquecer_ingles), estrategia))


def enriquecer(chunks: list[Document]) -> list[Document]:
    """Paso 3b: `hash` del texto y `chunk_id` determinístico; descarta duplicados exactos.

    Un duplicado ocuparía varios de los k puestos del retriever con el mismo contenido.
    """
    vistos: set[str] = set()
    salida: list[Document] = []
    for chunk in chunks:
        texto = chunk.page_content
        huella = hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]
        if huella in vistos:
            continue
        vistos.add(huella)
        metadatos = {
            **chunk.metadata,
            "hash": huella,
            "chunk_id": str(uuid.uuid5(_NAMESPACE, f"{chunk.metadata['doc_id']}|{texto}")),
        }
        salida.append(Document(page_content=texto, metadata=metadatos))
    return salida


@dataclass
class PlanDeCambios:
    agregar: list[Document]
    eliminar: list[str]
    sin_cambios: int


def plan_de_cambios(chunks: list[Document], existentes: set[str]) -> PlanDeCambios:
    """Qué agregar y qué borrar para que la base quede igual a `chunks`, sin tocar lo demás."""
    nuevos = {c.metadata["chunk_id"] for c in chunks}
    return PlanDeCambios(
        agregar=[c for c in chunks if c.metadata["chunk_id"] not in existentes],
        eliminar=sorted(existentes - nuevos),
        sin_cambios=len(nuevos & existentes),
    )


@dataclass
class ReporteIndexacion:
    tabla: str
    estrategia: str
    total_chunks: int
    agregados: int
    eliminados: int
    sin_cambios: int
    por_tipo: dict[str, int] = field(default_factory=dict)
    tokens_aproximados: int = 0
    segundos: float = 0.0
    indice: str = ""


def indexar(
    almacen: AlmacenVectorial,
    chunks: list[Document],
    lote: int | None = None,
    pausa_s: float | None = None,
    progreso=None,
) -> ReporteIndexacion:
    """Pasos 4 a 6: embeber en lotes (con pausa por los límites del nivel gratuito), guardar con
    ids determinísticos y crear el índice HNSW."""
    p = parametros()["indexacion"]
    lote = lote or p["lote"]
    pausa_s = p["pausa_s"] if pausa_s is None else pausa_s
    inicio = time.perf_counter()

    plan = plan_de_cambios(chunks, almacen.ids())
    almacen.eliminar(plan.eliminar)
    for i in range(0, len(plan.agregar), lote):
        grupo = plan.agregar[i : i + lote]
        almacen.agregar(grupo, ids=[c.metadata["chunk_id"] for c in grupo])
        if progreso:
            progreso(min(i + lote, len(plan.agregar)), len(plan.agregar))
        if pausa_s and i + lote < len(plan.agregar):
            time.sleep(pausa_s)
    indice = almacen.crear_indice()

    return ReporteIndexacion(
        tabla=almacen.tabla,
        estrategia=chunks[0].metadata.get("estrategia", "") if chunks else "",
        total_chunks=len(chunks),
        agregados=len(plan.agregar),
        eliminados=len(plan.eliminar),
        sin_cambios=plan.sin_cambios,
        por_tipo=dict(Counter(c.metadata["tipo"] for c in chunks)),
        tokens_aproximados=sum(chunking.tokens_aproximados(c.page_content) for c in chunks),
        segundos=round(time.perf_counter() - inicio, 2),
        indice=indice,
    )


def consultas_de_humo(almacen: AlmacenVectorial) -> list[dict]:
    """Paso 7: para cada tipo, ¿la consulta de humo trae primero un chunk de ese tipo?"""
    filas = []
    for tipo, pregunta in CONSULTAS_DE_HUMO.items():
        resultados = almacen.buscar(pregunta, k=1)
        documento, score = resultados[0] if resultados else (None, 0.0)
        obtenido = documento.metadata.get("tipo") if documento else None
        filas.append(
            {
                "tipo_esperado": tipo,
                "pregunta": pregunta,
                "tipo_obtenido": obtenido,
                "fuente": (documento.metadata.get("seccion") or documento.metadata.get("doc_id"))
                if documento
                else None,
                "similitud": score,
                "ok": obtenido == tipo,
            }
        )
    return filas


def escribir_reporte(
    reporte: ReporteIndexacion,
    perfil_nombre: str,
    modelo: str,
    dimensiones: int,
    humo: list[dict],
    outputs_dir: Path,
) -> tuple[Path, Path]:
    """Evidencia de una indexación real: outputs/indexacion_<fecha>_<perfil>[_<estrategia>]."""
    outputs_dir.mkdir(parents=True, exist_ok=True)
    fecha = date.today().isoformat()
    sufijo = "" if reporte.estrategia in ("", "por_tipo") else f"_{reporte.estrategia}"
    base = outputs_dir / f"indexacion_{fecha}_{perfil_nombre}{sufijo}"
    datos = {
        "fecha": fecha,
        "perfil": perfil_nombre,
        "modelo": modelo,
        "dimensiones": dimensiones,
        **asdict(reporte),
        "consultas_de_humo": humo,
    }
    base.with_suffix(".json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), "utf-8")

    lineas = [
        f"# Indexación — {perfil_nombre} ({modelo}, {dimensiones} dim)",
        "",
        f"**Fecha:** {fecha} · **Tabla:** `{reporte.tabla}` · "
        f"**Estrategia:** `{reporte.estrategia}`",
        "",
        "> Generado por `taller02 indexar`. No editar a mano: "
        "es la evidencia de una ejecución real.",
        "",
        "| Métrica | Valor |",
        "|---|---:|",
        f"| Chunks | {reporte.total_chunks} |",
        *(f"| · {tipo} | {n} |" for tipo, n in sorted(reporte.por_tipo.items())),
        f"| Agregados (embebidos en esta corrida) | {reporte.agregados} |",
        f"| Eliminados (ya no existen) | {reporte.eliminados} |",
        f"| Sin cambios | {reporte.sin_cambios} |",
        f"| Tokens aproximados | {reporte.tokens_aproximados} |",
        f"| Tiempo total (s) | {reporte.segundos} |",
        f"| Índice | {reporte.indice} |",
        "",
        "## Consultas de humo (una por tipo de documento, sin filtro, top-1)",
        "",
        "| Tipo esperado | Pregunta | Tipo obtenido | Fuente | Similitud | OK |",
        "|---|---|---|---|---:|:--:|",
        *(
            f"| {h['tipo_esperado']} | {h['pregunta']} | {h['tipo_obtenido']} | {h['fuente']} | "
            f"{h['similitud']:.4f} | {'✓' if h['ok'] else '✗'} |"
            for h in humo
        ),
        "",
    ]
    base.with_suffix(".md").write_text("\n".join(lineas), encoding="utf-8")
    return base.with_suffix(".json"), base.with_suffix(".md")
