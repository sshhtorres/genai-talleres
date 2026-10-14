"""Experimentos del Taller 2 (E1-E5, E7, E8): las "modificaciones observables" del enunciado.

| Exp. | Qué se modifica                                         | Llama al LLM |
|------|---------------------------------------------------------|--------------|
| E1   | prompt `basico` vs `mejorado`                           | Sí           |
| E2   | chunking `por_tipo` / `fija300` / `fija1000`            | No           |
| E3   | k = 1, 4, 8                                             | Sí           |
| E4   | embeddings `gemini` / `embeddinggemma` / `bge_m3`       | No           |
| E5   | asistente sin RAG vs `atender` con RAG                  | Sí           |
| E7   | catálogo tal cual vs fichas en inglés enriquecidas      | No           |
| E8   | configuraciones nube / hibrida / local (con streaming)  | Sí           |

Cada experimento escribe su evidencia en outputs/. Los de respuesta usan `RunRecorder` (el mismo
formato del Taller 1); los de recuperación, tablas de hit@k y MRR. Ninguna cifra de los documentos
de las fases debe salir de otro lado.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from genai_common import ConfigError, RunRecord, RunRecorder, render
from genai_common.configuraciones import resolver_configuracion
from genai_common.embeddings import get_embedding_profile
from genai_common.lc import chat_model_from_profile

from . import atencion, checks, evaluation, indexing, kb
from .chains import cargar_prompts, formatear_contexto, metadatos_de, responder
from .chunking import ESTRATEGIA_POR_DEFECTO, estrategias_disponibles
from .componentes import armar_embeddings
from .config import OUTPUTS_DIR
from .store import AlmacenVectorial, crear_almacen

EXPERIMENTOS = ("E1", "E2", "E3", "E4", "E5", "E7", "E8")
PERFILES_E4 = ("gemini", "embeddinggemma", "bge_m3")
CONFIGURACIONES_E8 = ("nube", "hibrida:gemini", "hibrida:anthropic", "local")

Progreso = Callable[[str], None]


@dataclass
class Opciones:
    embeddings: str | None = None
    proveedor: str | None = None
    backend: str = "pgvector"
    pausa_s: float = 4.0
    limite: int | None = None
    outputs_dir: Path = OUTPUTS_DIR
    progreso: Progreso = print
    perfiles: tuple[str, ...] = PERFILES_E4  # E4
    configuraciones: tuple[str, ...] = CONFIGURACIONES_E8  # E8


# -- piezas comunes -------------------------------------------------------------------------


def almacen_listo(
    perfil_nombre: str, backend: str, estrategia: str = ESTRATEGIA_POR_DEFECTO, sufijo: str = ""
) -> AlmacenVectorial:
    """Base vectorial de un perfil y una estrategia. En pgvector debe estar indexada; en memoria
    se indexa en el momento."""
    perfil = get_embedding_profile(perfil_nombre)
    almacen = crear_almacen(
        armar_embeddings(perfil), perfil, backend=backend, estrategia=estrategia, sufijo=sufijo
    )
    if backend == "memoria":
        chunks = indexing.preparar_chunks(estrategia, enriquecer_ingles=sufijo == "enriq")
        indexing.indexar(almacen, chunks, pausa_s=0)
    elif not almacen.ids():
        opciones = f" --estrategia {estrategia}" if estrategia != ESTRATEGIA_POR_DEFECTO else ""
        opciones += " --enriquecer-ingles" if sufijo == "enriq" else ""
        raise ConfigError(
            f"La tabla {almacen.tabla} está vacía: indexa primero con "
            f"`taller02 indexar --embeddings {perfil_nombre}{opciones}`."
        )
    return almacen


def _llm(opciones: Opciones, model_role: str | None = None) -> BaseChatModel:
    from .componentes import armar_llm

    return armar_llm(opciones.proveedor, model_role=model_role)


def _casos(opciones: Opciones, predicado: Callable[[dict], bool]) -> list[dict]:
    casos = [c for c in kb.casos_rag() if predicado(c)]
    return casos[: opciones.limite] if opciones.limite else casos


def _parametros_ruta(caso: dict, variante: str) -> dict[str, Any]:
    """Filtro y reglas que el router aplicaría según la intención esperada del caso."""
    if caso["intencion_esperada"] == "credito":
        return {
            "filtro": atencion.FILTRO_CREDITO,
            "reglas_extra": cargar_prompts()["credito"]["reglas"] if variante == "mejorado" else "",
            "es_credito": True,
        }
    return {}


def _registro(exp: str, caso: dict, variante: str, respuesta: str, chks, meta, pasos) -> RunRecord:
    return RunRecord(
        caso_id=caso["id"],
        ejercicio=f"{exp}:{caso['tipo']}",
        variante=variante,
        mensaje=caso["mensaje"],
        respuesta=respuesta,
        checks=chks,
        metadatos=meta,
        pasos=pasos,
    )


def _anexar(md: Path, titulo: str, lineas: list[str]) -> None:
    """Agrega una sección de resumen al final del reporte de RunRecorder."""
    with md.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(["", f"## {titulo}", "", *lineas, ""]))


def _media(valores) -> float | None:
    valores = [v for v in valores if v is not None]
    return round(statistics.mean(valores), 3) if valores else None


def _con_pausa(opciones: Opciones, i: int, total: int) -> None:
    if opciones.pausa_s and i < total:
        time.sleep(opciones.pausa_s)


# -- E1 y E3: variantes del prompt y de k ----------------------------------------------------


def _respuestas_rag(exp: str, opciones: Opciones, variantes: list[tuple[str, dict]]) -> Path:
    """Corre la cadena RAG (sin router) sobre los casos que no requieren el Taller 1."""
    perfil = opciones.embeddings or resolver_configuracion().embeddings.name
    almacen = almacen_listo(perfil, opciones.backend)
    llm = _llm(opciones)
    casos = _casos(opciones, lambda c: c["tipo"] != "mixto")
    recorder = RunRecorder(
        opciones.outputs_dir, proveedor=_nombre_llm(llm), modelo=_modelo(llm), etiqueta=exp
    )
    total = len(casos) * len(variantes)
    hecho = 0
    for etiqueta, kwargs in variantes:
        for caso in casos:
            hecho += 1
            opciones.progreso(f"[{hecho}/{total}] {caso['id']} · {etiqueta}")
            variante = kwargs.get("variante", "mejorado")
            r = responder(
                caso["mensaje"], almacen, llm, **kwargs, **_parametros_ruta(caso, variante)
            )
            contexto = formatear_contexto(r.recuperacion.chunks)
            chks = r.checks + evaluation.checks_del_caso(caso, r.respuesta, contexto)
            meta = {**r.metadatos, "embeddings": perfil, "k": r.recuperacion.k}
            recorder.add(_registro(exp, caso, etiqueta, r.respuesta, chks, meta, r.pasos()))
            if r.llamadas:
                _con_pausa(opciones, hecho, total)
    _, md = recorder.write()
    return md


def e1(opciones: Opciones) -> list[Path]:
    md = _respuestas_rag("E1", opciones, [("basico", {"variante": "basico"}), ("mejorado", {})])
    return [md]


def e3(opciones: Opciones) -> list[Path]:
    md = _respuestas_rag("E3", opciones, [(f"k={k}", {"k": k}) for k in (1, 4, 8)])
    registros = RunRecorderLectura(md)
    lineas = [
        "| Variante | Casos | Chequeos OK | Tokens de entrada (media) |",
        "|---|---:|---:|---:|",
    ]
    for variante, grupo in registros.por_variante().items():
        ok = sum(1 for r in grupo if all(c["ok"] for c in r["checks"]))
        tokens = _media(r["metadatos"].get("tokens_entrada") for r in grupo)
        lineas.append(f"| {variante} | {len(grupo)} | {ok} | {tokens} |")
    _anexar(md, "Tokens de entrada por k", lineas)
    return [md]


# -- E2, E4, E7: solo recuperación -------------------------------------------------------------


def e2(opciones: Opciones) -> list[Path]:
    perfil = opciones.embeddings or resolver_configuracion().embeddings.name
    filas, datos, detalle = {}, {}, []
    for estrategia in estrategias_disponibles():
        opciones.progreso(f"E2 · {perfil} · {estrategia}")
        almacen = almacen_listo(perfil, opciones.backend, estrategia)
        resultados = evaluation.evaluar_recuperacion(almacen)
        filas[estrategia] = evaluation.resumen_recuperacion(resultados)
        datos[estrategia] = {"resumen": filas[estrategia], "casos": resultados}
        if estrategia == ESTRATEGIA_POR_DEFECTO:
            detalle = evaluation.tabla_casos(resultados)
    _, md = evaluation.escribir_reporte(
        "E2",
        f"E2 — Chunking: hit@k y MRR por estrategia ({perfil})",
        [
            ("Métricas por estrategia y por documento", evaluation.tabla_metricas(filas)),
            ("Detalle por caso (por_tipo)", detalle),
        ],
        {"perfil": perfil, "k_max": evaluation.K_MAX, "estrategias": datos},
        opciones.outputs_dir,
        sufijo=perfil,
    )
    return [md]


def e4(opciones: Opciones) -> list[Path]:
    filas, datos, latencias = {}, {}, []
    for perfil in opciones.perfiles:
        opciones.progreso(f"E4 · {perfil}")
        almacen = almacen_listo(perfil, opciones.backend)
        inicio = time.perf_counter()
        resultados = evaluation.evaluar_recuperacion(almacen)
        por_consulta = (time.perf_counter() - inicio) / max(1, len(resultados))
        filas[perfil] = evaluation.resumen_recuperacion(resultados)
        ram = _ram_ollama_gb() if get_embedding_profile(perfil).backend == "ollama" else None
        datos[perfil] = {
            "resumen": filas[perfil],
            "casos": resultados,
            "segundos_por_consulta": round(por_consulta, 3),
            "ram_ollama_gb": ram,
        }
        latencias.append(
            f"| {perfil} | {round(por_consulta, 3)} | {ram if ram is not None else 'no aplica'} |"
        )
    _, md = evaluation.escribir_reporte(
        "E4",
        "E4 — Modelos de embeddings: hit@k y MRR (global, por documento y translingüe)",
        [
            ("Métricas", evaluation.tabla_metricas(filas)),
            (
                "Latencia y memoria",
                [
                    "Latencia = embedding de la pregunta + búsqueda en la base, por consulta. "
                    "RAM = RSS de los procesos de Ollama al terminar (solo modelos locales).",
                    "",
                    "| Perfil | Segundos por consulta | RAM de Ollama (GB) |",
                    "|---|---:|---:|",
                    *latencias,
                ],
            ),
        ],
        {"k_max": evaluation.K_MAX, "perfiles": datos},
        opciones.outputs_dir,
    )
    return [md]


def e7(opciones: Opciones) -> list[Path]:
    perfil = opciones.embeddings or resolver_configuracion().embeddings.name
    filas, datos, sesgo = {}, {}, []
    for nombre, sufijo in (("tal cual", ""), ("enriquecido", "enriq")):
        opciones.progreso(f"E7 · {perfil} · {nombre}")
        almacen = almacen_listo(perfil, opciones.backend, sufijo=sufijo)
        resultados = evaluation.evaluar_recuperacion(almacen)
        filas[nombre] = evaluation.resumen_recuperacion(resultados)
        s = evaluation.sesgo_de_idioma(resultados)
        datos[nombre] = {"resumen": filas[nombre], "sesgo": s, "casos": resultados}
        sesgo.append(
            f"| {nombre} | {s['es_a_es']} ({s['n_es_es']}) | {s['es_a_en']} ({s['n_es_en']}) |"
        )
    _, md = evaluation.escribir_reporte(
        "E7",
        f"E7 — Fichas en inglés: tal cual vs enriquecidas con un resumen en español ({perfil})",
        [
            ("Métricas (mirar translingue y doc:catalogo)", evaluation.tabla_metricas(filas)),
            (
                "Sesgo de idioma: similitud media del acierto en el catálogo",
                [
                    "| Variante | Pregunta ES → ficha ES (n) | Pregunta ES → ficha EN (n) |",
                    "|---|---:|---:|",
                    *sesgo,
                ],
            ),
        ],
        {"perfil": perfil, "variantes": datos},
        opciones.outputs_dir,
        sufijo=perfil,
    )
    return [md]


# -- E5: sin RAG vs con RAG ------------------------------------------------------------------------


def e5(opciones: Opciones) -> list[Path]:
    """Preguntas que el Taller 1 no podía responder: el mismo asistente sin documentos frente a
    `atender` con RAG."""
    perfil = opciones.embeddings or resolver_configuracion().embeddings.name
    almacen = almacen_listo(perfil, opciones.backend)
    llm = _llm(opciones)
    llm_router = _llm(opciones, model_role="router")
    from .componentes import armar_cliente_t1

    cliente_t1 = armar_cliente_t1(opciones.proveedor)
    casos = _casos(
        opciones,
        lambda c: (
            c["tipo"] in {"dentro_alcance", "reformulacion", "credito_trampa"}
            and c["intencion_esperada"] in {"consulta_general", "credito"}
        ),
    )
    prompts = cargar_prompts()["sin_rag"]
    recorder = RunRecorder(
        opciones.outputs_dir, proveedor=_nombre_llm(llm), modelo=_modelo(llm), etiqueta="E5"
    )
    total = len(casos) * 2
    for i, caso in enumerate(casos, start=1):
        opciones.progreso(f"[{2 * i - 1}/{total}] {caso['id']} · sin_rag")
        mensajes = [
            SystemMessage(prompts["system"]),
            HumanMessage(render(prompts["user"], pregunta=caso["mensaje"])),
        ]
        inicio = time.perf_counter()
        ia = llm.invoke(mensajes)
        texto = StrOutputParser().invoke(ia).strip()
        meta = metadatos_de(ia, llm, time.perf_counter() - inicio)
        chks = [checks.sin_datos_de_pedidos(texto, caso["mensaje"])]
        chks += evaluation.checks_del_caso(caso, texto)
        recorder.add(_registro("E5", caso, "sin_rag", texto, chks, meta, {}))
        _con_pausa(opciones, 2 * i - 1, total)

        opciones.progreso(f"[{2 * i}/{total}] {caso['id']} · con_rag")
        r = atencion.atender(caso["mensaje"], almacen, llm, cliente_t1, llm_router)
        contexto = formatear_contexto(r.detalle.recuperacion.chunks) if r.fuentes else ""
        chks = r.checks + evaluation.checks_del_caso(caso, r.respuesta, contexto)
        meta = {**r.metadatos, "ruta": r.ruta, "llamadas": r.llamadas}
        recorder.add(_registro("E5", caso, "con_rag", r.respuesta, chks, meta, r.pasos))
        _con_pausa(opciones, 2 * i, total)
    _, md = recorder.write()
    return [md]


# -- E8: configuraciones --------------------------------------------------------------------------


def e8(opciones: Opciones) -> list[Path]:
    """Mismas preguntas con cada configuración; streaming para medir el tiempo hasta el primer
    token aparte de la latencia total. `hibrida:anthropic` = embeddings locales + Haiku 5.5."""
    casos = _casos(opciones, lambda c: c["tipo"] != "mixto")
    reportes, resumen = [], []
    for etiqueta in opciones.configuraciones:
        nombre, _, rag_llm = etiqueta.partition(":")
        config = resolver_configuracion(nombre, llm=rag_llm or None)
        opciones.progreso(f"E8 · {etiqueta}")
        almacen = almacen_listo(config.embeddings.name, opciones.backend)
        llm = chat_model_from_profile(profile=config.llm, model=config.llm_model, max_tokens=600)
        recorder = RunRecorder(
            opciones.outputs_dir,
            proveedor=etiqueta.replace(":", "-"),
            modelo=f"{config.embeddings.model} + {config.llm_model or config.llm.model}",
            etiqueta="E8",
        )
        precios = config.llm.extra.get("precios_usd_mtok", {}).get(
            config.llm_model or config.llm.model
        )
        for i, caso in enumerate(casos, start=1):
            opciones.progreso(f"  [{i}/{len(casos)}] {caso['id']}")
            r = responder(
                caso["mensaje"],
                almacen,
                llm,
                medir_ttft=True,
                **_parametros_ruta(caso, "mejorado"),
            )
            contexto = formatear_contexto(r.recuperacion.chunks)
            chks = r.checks + evaluation.checks_del_caso(caso, r.respuesta, contexto)
            meta = {**r.metadatos, "costo_usd": _costo(r.metadatos, precios)}
            recorder.add(_registro("E8", caso, etiqueta, r.respuesta, chks, meta, r.pasos()))
            if r.llamadas:
                _con_pausa(opciones, i, len(casos))
        _, md = recorder.write()
        reportes.append(md)
        registros = [x.to_dict() for x in recorder.records]
        ok = sum(1 for x in recorder.records if x.ok)
        costo = _media(x["metadatos"].get("costo_usd") for x in registros)
        resumen.append(
            f"| {etiqueta} | {len(registros)} | {ok} | "
            f"{_media(x['metadatos'].get('ttft_s') for x in registros)} | "
            f"{_media(x['metadatos'].get('latencia_s') for x in registros)} | "
            f"{_media(x['metadatos'].get('tokens_entrada') for x in registros)} | "
            f"{_media(x['metadatos'].get('tokens_salida') for x in registros)} | "
            f"{costo if costo is not None else 'sin precio verificado'} |"
        )
    _, md = evaluation.escribir_reporte(
        "E8_resumen",
        "E8 — Configuraciones: chequeos, tiempo hasta el primer token, latencia, tokens y costo",
        [
            (
                "Resumen (medias por respuesta)",
                [
                    "| Configuración | Casos | Chequeos OK | TTFT (s) | Latencia total (s) | "
                    "Tokens entrada | Tokens salida | Costo (USD) |",
                    "|---|---:|---:|---:|---:|---:|---:|---:|",
                    *resumen,
                    "",
                    "Detalle por caso: " + ", ".join(f"`{p.name}`" for p in reportes),
                ],
            )
        ],
        {"configuraciones": list(opciones.configuraciones), "reportes": [p.name for p in reportes]},
        opciones.outputs_dir,
    )
    return [*reportes, md]


def _costo(meta: dict, precios: dict | None) -> float | None:
    if not precios or meta.get("tokens_entrada") is None:
        return None
    entrada = meta["tokens_entrada"] * precios["entrada"] / 1e6
    salida = (meta.get("tokens_salida") or 0) * precios["salida"] / 1e6
    return round(entrada + salida, 6)


# -- utilidades ---------------------------------------------------------------------------------


def correr(experimento: str, opciones: Opciones) -> list[Path]:
    funciones = {"E1": e1, "E2": e2, "E3": e3, "E4": e4, "E5": e5, "E7": e7, "E8": e8}
    if experimento not in funciones:
        raise ValueError(f"Experimento desconocido: {experimento}. Disponibles: {EXPERIMENTOS}.")
    return funciones[experimento](opciones)


def _nombre_llm(llm: BaseChatModel) -> str:
    return {
        "ChatGoogleGenerativeAI": "gemini",
        "ChatAnthropic": "anthropic",
        "ChatOllama": "ollama",
    }.get(type(llm).__name__, "fake")


def _modelo(llm: BaseChatModel) -> str:
    return str(getattr(llm, "model", None) or getattr(llm, "model_name", "?"))


def _ram_ollama_gb() -> float | None:
    """RSS total de los procesos de Ollama (ollama, llama-server), en GB; None si no hay."""
    import psutil

    total = 0
    for proceso in psutil.process_iter(["name", "memory_info"]):
        nombre = (proceso.info.get("name") or "").lower()
        if "ollama" in nombre or "llama-server" in nombre:
            total += proceso.info["memory_info"].rss if proceso.info.get("memory_info") else 0
    return round(total / 1024**3, 2) if total else None


class RunRecorderLectura:
    """Lee el JSONL que acaba de escribir RunRecorder (para resúmenes adicionales)."""

    def __init__(self, md: Path) -> None:
        import json

        self.registros = [
            json.loads(linea)
            for linea in md.with_suffix(".jsonl").read_text(encoding="utf-8").splitlines()
            if linea.strip()
        ]

    def por_variante(self) -> dict[str, list[dict]]:
        grupos: dict[str, list[dict]] = {}
        for registro in self.registros:
            grupos.setdefault(registro["variante"], []).append(registro)
        return grupos
