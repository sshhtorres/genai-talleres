"""Evaluación del RAG: métricas de recuperación, calibración del umbral y chequeos de respuesta.

- **Recuperación (sin LLM, determinista):** hit@k y MRR. Un chunk "acierta" si es del documento
  esperado y contiene la `evidencia` literal del caso; así la métrica vale igual para cualquier
  estrategia de chunking, incluso las de tamaño fijo, que no conservan la sección.
- **Calibración del umbral:** distribución del mejor *score* de los casos dentro y fuera de alcance,
  con los translingües aparte, y el umbral que mejor los separa sin abstenerse en los translingües.
- **Respuesta (estilo Taller 1):** chequeos determinísticos por caso. No se usa un LLM como juez.
"""

from __future__ import annotations

import json
import re
import statistics
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import checks, kb
from .config import PARAMETROS
from .store import AlmacenVectorial

K_MAX = 8


# -- recuperación ------------------------------------------------------------------------


def acierta(texto: str, doc_id: str, fuente: dict[str, str]) -> bool:
    """¿El chunk recuperado contiene la evidencia de la fuente esperada?"""
    return doc_id == fuente["doc_id"] and kb.normalizar(fuente["evidencia"]) in kb.normalizar(texto)


@dataclass
class ResultadoRecuperacion:
    caso_id: str
    tipo: str
    doc_esperado: str
    idioma_pregunta: str
    idioma_documento: str
    rango: int | None  # posición (1..K_MAX) del primer acierto; None si no apareció
    mejor_score: float  # similitud del top-1, sea o no un acierto
    score_acierto: float | None  # similitud del primer acierto
    fuentes_top: list[str] = field(default_factory=list)

    def hit(self, k: int) -> bool:
        return self.rango is not None and self.rango <= k

    @property
    def reciproco(self) -> float:
        return 1.0 / self.rango if self.rango else 0.0


def casos_con_fuente(casos: Iterable[dict] | None = None) -> list[dict]:
    return [c for c in (casos or kb.casos_rag()) if c["fuentes_esperadas"]]


def evaluar_recuperacion(
    almacen: AlmacenVectorial, casos: Iterable[dict] | None = None, k_max: int = K_MAX
) -> list[ResultadoRecuperacion]:
    """Busca cada caso (sin filtro) y registra en qué posición aparece la evidencia esperada."""
    idiomas_doc = {f["sku"]: f["idioma"] for f in kb.catalogo()}
    resultados = []
    for caso in casos_con_fuente(casos):
        encontrados = almacen.buscar(caso["mensaje"], k=k_max)
        rango, score_acierto = None, None
        for i, (documento, score) in enumerate(encontrados, start=1):
            doc_id = documento.metadata.get("doc_id", "")
            if any(acierta(documento.page_content, doc_id, f) for f in caso["fuentes_esperadas"]):
                rango, score_acierto = i, score
                break
        esperada = caso["fuentes_esperadas"][0]
        resultados.append(
            ResultadoRecuperacion(
                caso_id=caso["id"],
                tipo=caso["tipo"],
                doc_esperado=esperada["doc_id"],
                idioma_pregunta=caso["idioma_respuesta"],
                idioma_documento=idiomas_doc.get(esperada["seccion_o_id"], "es"),
                rango=rango,
                mejor_score=encontrados[0][1] if encontrados else 0.0,
                score_acierto=score_acierto,
                fuentes_top=[
                    d.metadata.get("seccion") or d.metadata.get("doc_id", "")
                    for d, _ in encontrados[:3]
                ],
            )
        )
    return resultados


def metricas(resultados: list[ResultadoRecuperacion], ks: tuple[int, ...] = (1, 4)) -> dict:
    """hit@k y MRR de un grupo de casos."""
    n = len(resultados)
    if not n:
        return {"casos": 0}
    salida: dict[str, Any] = {"casos": n}
    for k in ks:
        salida[f"hit@{k}"] = round(sum(r.hit(k) for r in resultados) / n, 3)
    salida["mrr"] = round(sum(r.reciproco for r in resultados) / n, 3)
    return salida


def resumen_recuperacion(resultados: list[ResultadoRecuperacion], ks=(1, 4)) -> dict[str, dict]:
    """Global, por documento esperado y solo translingües."""
    grupos: dict[str, list[ResultadoRecuperacion]] = {"global": resultados}
    for doc in kb.DOCUMENTOS:
        grupos[f"doc:{doc}"] = [r for r in resultados if r.doc_esperado == doc]
    grupos["translingue"] = [r for r in resultados if r.tipo == "translingue"]
    return {nombre: metricas(grupo, ks) for nombre, grupo in grupos.items() if grupo}


def sesgo_de_idioma(resultados: list[ResultadoRecuperacion]) -> dict[str, Any]:
    """Media de la similitud del acierto: pregunta en español sobre fichas en español frente a
    pregunta en español sobre fichas en inglés (E7)."""

    def media(grupo):
        valores = [r.score_acierto for r in grupo if r.score_acierto is not None]
        return round(statistics.mean(valores), 4) if valores else None

    catalogo = [r for r in resultados if r.doc_esperado == kb.DOC_CATALOGO]
    es_es = [r for r in catalogo if r.idioma_pregunta == "es" and r.idioma_documento == "es"]
    es_en = [r for r in catalogo if r.idioma_pregunta == "es" and r.idioma_documento == "en"]
    return {
        "es_a_es": media(es_es),
        "es_a_en": media(es_en),
        "n_es_es": len(es_es),
        "n_es_en": len(es_en),
    }


# -- calibración del umbral -------------------------------------------------------------------


@dataclass
class Calibracion:
    perfil: str
    umbral: float
    exactitud: float
    dentro: list[float]
    fuera: list[float]
    translingue: list[float]
    abstenciones_translingues: int
    nota: str = ""


def mejores_scores(
    almacen: AlmacenVectorial, casos: Iterable[dict] | None = None
) -> dict[str, list]:
    """Similitud del top-1 de cada caso, separada en dentro de alcance, fuera y translingües."""
    grupos: dict[str, list[tuple[str, float]]] = {"dentro": [], "fuera": [], "translingue": []}
    for caso in casos or kb.casos_rag():
        encontrados = almacen.buscar(caso["mensaje"], k=1)
        score = encontrados[0][1] if encontrados else 0.0
        if caso["tipo"] == "translingue":
            grupos["translingue"].append((caso["id"], score))
        elif caso["debe_abstenerse"]:
            grupos["fuera"].append((caso["id"], score))
        else:
            grupos["dentro"].append((caso["id"], score))
    return grupos


def calibrar_umbral(perfil: str, grupos: dict[str, list[tuple[str, float]]]) -> Calibracion:
    """Umbral que maximiza la exactitud de la decisión abstenerse/responder sin abstenerse en
    ningún caso translingüe. Entre umbrales igual de buenos, el del medio del intervalo."""
    dentro = sorted(s for _, s in grupos["dentro"])
    fuera = sorted(s for _, s in grupos["fuera"])
    transl = sorted(s for _, s in grupos["translingue"])
    todos = sorted(set(dentro + fuera + transl))
    candidatos = [0.0] + [round((a + b) / 2, 4) for a, b in zip(todos, todos[1:], strict=False)]
    tope = min(transl) if transl else 1.0
    validos = [t for t in candidatos if t <= tope] or [0.0]

    def exactitud(t: float) -> float:
        bien = sum(s >= t for s in dentro) + sum(s < t for s in fuera)
        return bien / max(1, len(dentro) + len(fuera))

    mejor = max(exactitud(t) for t in validos)
    empatados = [t for t in validos if exactitud(t) == mejor]
    umbral = empatados[len(empatados) // 2]
    nota = ""
    if transl and tope <= max(fuera, default=0.0):
        nota = (
            "Algún caso translingüe puntúa por debajo de un caso fuera de alcance: no existe un "
            "umbral que separe todo. Se prioriza no abstenerse en los translingües."
        )
    return Calibracion(
        perfil=perfil,
        umbral=umbral,
        exactitud=round(mejor, 3),
        dentro=dentro,
        fuera=fuera,
        translingue=transl,
        abstenciones_translingues=sum(s < umbral for s in transl),
        nota=nota,
    )


def _cuenta(valores: list[float], inicio: float, fin: float) -> int:
    return sum(inicio <= v < fin or (fin >= 1.0 and v == 1.0) for v in valores)


def histograma(calibracion: Calibracion, ancho: float = 0.05) -> list[str]:
    """Histograma en texto de los mejores scores por grupo (D=dentro, F=fuera, T=translingüe)."""
    lineas = []
    inicio = 0.0
    while inicio < 1.0:
        fin = round(inicio + ancho, 4)
        d = _cuenta(calibracion.dentro, inicio, fin)
        f = _cuenta(calibracion.fuera, inicio, fin)
        t = _cuenta(calibracion.translingue, inicio, fin)
        en_umbral = inicio <= calibracion.umbral < fin
        if d or f or t or en_umbral:
            marca = " ← umbral" if en_umbral else ""
            lineas.append(f"{inicio:.2f}-{fin:.2f} | {'D' * d}{'F' * f}{'T' * t}{marca}")
        inicio = fin
    return lineas


def guardar_umbral(perfil: str, umbral: float, ruta: Path = PARAMETROS) -> None:
    """Escribe el umbral del perfil en la tabla [recuperacion.umbral] de parametros.toml."""
    texto = ruta.read_text(encoding="utf-8")
    seccion = texto.index("[recuperacion.umbral]")
    patron = re.compile(rf"^{re.escape(perfil)} = [0-9.]+$", re.MULTILINE)
    cuerpo, n = patron.subn(f"{perfil} = {umbral}", texto[seccion:], count=1)
    if not n:
        raise ValueError(f"El perfil '{perfil}' no está en [recuperacion.umbral] de {ruta.name}.")
    ruta.write_text(texto[:seccion] + cuerpo, encoding="utf-8")


# -- chequeos de respuesta por caso ---------------------------------------------------------------


def checks_del_caso(caso: dict, respuesta: str, contexto: str = "") -> list[checks.Check]:
    """Lo que el set de evaluación espera de la respuesta, además de los chequeos de la cadena."""
    salida = [
        checks.abstencion_correcta(respuesta, caso["debe_abstenerse"]),
        checks.idioma_correcto(respuesta, caso["idioma_respuesta"]),
        *checks.contiene(respuesta, caso["debe_contener"], caso["no_debe_contener"]),
    ]
    if caso.get("cifras_con_respaldo"):
        salida.append(checks.cifras_soportadas(respuesta, contexto, caso["mensaje"]))
    return salida


# -- reportes de recuperación ----------------------------------------------------------------------


def escribir_reporte(
    nombre: str,
    titulo: str,
    secciones: list[tuple[str, list[str]]],
    datos: dict,
    outputs_dir: Path,
    sufijo: str = "",
) -> tuple[Path, Path]:
    """outputs/<nombre>_<fecha>[_<sufijo>].{json,md}, el mismo esquema de nombres de RunRecorder."""
    outputs_dir.mkdir(parents=True, exist_ok=True)
    base = outputs_dir / "_".join(x for x in (nombre, date.today().isoformat(), sufijo) if x)
    base.with_suffix(".json").write_text(
        json.dumps(datos, ensure_ascii=False, indent=2, default=_serializable), encoding="utf-8"
    )
    lineas = [
        f"# {titulo}",
        "",
        f"**Fecha:** {date.today().isoformat()}",
        "",
        "> Generado por `taller02 evaluar`/`calibrar`. No editar a mano: es la evidencia de una "
        "ejecución real.",
        "",
    ]
    for subtitulo, contenido in secciones:
        lineas += [f"## {subtitulo}", "", *contenido, ""]
    base.with_suffix(".md").write_text("\n".join(lineas), encoding="utf-8")
    return base.with_suffix(".json"), base.with_suffix(".md")


def tabla_metricas(filas: dict[str, dict[str, dict]], ks=(1, 4)) -> list[str]:
    """Una tabla Markdown: filas = variantes, columnas = grupo × métrica."""
    columnas = [f"hit@{k}" for k in ks] + ["mrr"]
    salida = []
    grupos = list(next(iter(filas.values())).keys()) if filas else []
    for grupo in grupos:
        salida += [f"**{grupo}**", "", "| Variante | Casos | " + " | ".join(columnas) + " |"]
        salida.append("|---|---:|" + "---:|" * len(columnas))
        for variante, resumen in filas.items():
            m = resumen.get(grupo, {"casos": 0})
            valores = " | ".join(str(m.get(c, "—")) for c in columnas)
            salida.append(f"| {variante} | {m.get('casos', 0)} | {valores} |")
        salida.append("")
    return salida


def tabla_casos(resultados: list[ResultadoRecuperacion]) -> list[str]:
    salida = [
        "| Caso | Tipo | Esperado | Rango | Top-1 | Score top-1 |",
        "|---|---|---|---:|---|---:|",
    ]
    for r in resultados:
        rango = r.rango if r.rango else "—"
        top = r.fuentes_top[0] if r.fuentes_top else "—"
        salida.append(
            f"| {r.caso_id} | {r.tipo} | {r.doc_esperado} | {rango} | {top} | {r.mejor_score:.4f} |"
        )
    return salida


def _serializable(valor: Any) -> Any:
    if hasattr(valor, "__dataclass_fields__"):
        return asdict(valor)
    raise TypeError(type(valor))
