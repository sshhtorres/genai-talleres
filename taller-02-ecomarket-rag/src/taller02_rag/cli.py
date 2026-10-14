"""Interfaz de línea de comandos del Taller 2."""

from __future__ import annotations

from typing import Annotated

import typer

from genai_common import ConfigError, list_profiles
from genai_common.configuraciones import (
    listar_niveles,
    recomendar_nivel,
    resolver_configuracion,
)
from genai_common.embeddings import list_embedding_profiles

from . import chunking, componentes, indexing, servicios
from .chains import VARIANTES, responder
from .config import OUTPUTS_DIR
from .store import BACKENDS, crear_almacen

app = typer.Typer(
    add_completion=False,
    help="Taller 2 · EcoMarket: RAG para la atención al cliente.",
    no_args_is_help=True,
)


def _ollama_url() -> str:
    """URL nativa de Ollama, tomada del primer perfil de embeddings que lo usa."""
    for perfil in list_embedding_profiles():
        if perfil.backend == "ollama" and perfil.base_url:
            return perfil.base_url
    return "http://localhost:11434"


@app.callback()
def main() -> None:
    """Taller 2 · EcoMarket: RAG para la atención al cliente."""


def _titulo(texto: str) -> None:
    typer.secho(f"\n{texto}", fg=typer.colors.BLUE, bold=True)


def _marca(ok: bool) -> str:
    return "✓" if ok else "✗"


@app.command()
def proveedores(
    recomendar: Annotated[
        bool, typer.Option("--recomendar", help="Sugiere un LOCAL_TIER según la RAM del equipo")
    ] = False,
) -> None:
    """Configuración activa, perfiles de LLM y de embeddings, y estado de Postgres y Ollama."""
    _titulo("Configuración RAG activa (RAG_CONFIG)")
    config = None
    try:
        config = resolver_configuracion()
    except ConfigError as exc:
        typer.secho(f"  ✗ {exc}", fg=typer.colors.RED)
    if config:
        typer.echo(f"  {config.nombre}: {config.descripcion}")
        typer.echo(
            f"  · embeddings: {config.embeddings.name} ({config.embeddings.model}, "
            f"{config.embeddings.dimensions} dim)"
        )
        modelo = config.llm_model or config.llm.model
        nivel = ""
        if config.nivel:
            origen = " por defecto: LOCAL_TIER no definido" if config.nivel_por_defecto else ""
            nivel = f", nivel {config.nivel}{origen}"
        typer.echo(f"  · LLM: {config.llm.name} ({modelo}{nivel})")
        typer.echo(f"  · tabla de la base vectorial: {config.tabla}")

    _titulo("Perfiles de LLM (providers.toml)")
    for perfil in list_profiles():
        clave = (
            "no requiere"
            if not perfil.requires_key
            else f"{perfil.api_key_env} {_marca(perfil.key_configured)}"
        )
        typer.echo(f"  {perfil.name:<12} {perfil.status:<16} {clave:<22} {perfil.model}")

    _titulo("Perfiles de embeddings (providers.toml)")
    for perfil in list_embedding_profiles():
        clave = (
            "no requiere"
            if not perfil.api_key_env
            else f"{perfil.api_key_env} {_marca(perfil.key_configured)}"
        )
        typer.echo(
            f"  {perfil.name:<15} {perfil.backend:<7} {clave:<22} "
            f"{perfil.model} → {perfil.table_name}"
        )

    _titulo("Servicios")
    pg = servicios.estado_postgres()
    color = typer.colors.GREEN if pg.ok else typer.colors.YELLOW
    typer.secho(f"  {_marca(pg.ok)} Postgres: {pg.detalle}", fg=color)
    if pg.extra:
        typer.echo(f"      tablas: {', '.join(pg.extra)}")

    ollama = servicios.estado_ollama(_ollama_url())
    color = typer.colors.GREEN if ollama.ok else typer.colors.YELLOW
    typer.secho(f"  {_marca(ollama.ok)} Ollama: {ollama.detalle}", fg=color)
    if ollama.ok and config:
        necesarios = []
        if config.embeddings.backend == "ollama":
            necesarios.append(config.embeddings.model)
        if config.llm.name == "ollama":
            necesarios.append(config.llm_model or config.llm.model)
        for modelo in necesarios:
            ok = servicios.modelo_descargado(modelo, ollama.extra)
            pista = "" if ok else f" → ollama pull {modelo}"
            typer.echo(f"      {_marca(ok)} {modelo}{pista}")

    if recomendar:
        _recomendar()


def _recomendar() -> None:
    import psutil

    ram_gb = psutil.virtual_memory().total / 1024**3
    _titulo("Nivel de hardware sugerido para la configuración local")
    nivel = recomendar_nivel(ram_gb)
    typer.echo(f"  RAM detectada: {ram_gb:.1f} GB")
    if nivel:
        modelo = listar_niveles()[nivel]["llm_model"]
        typer.echo(f"  Sugerencia: LOCAL_TIER={nivel} (LLM {modelo})")
    else:
        typer.echo("  Ningún nivel de CPU cabe en esta RAM: usa la configuración nube o hibrida.")
    typer.secho(
        "  La GPU no se detecta: si tienes una, elige gpu-12gb o gpu-24gb a mano.\n"
        "  Este comando no modifica tu .env.",
        fg=typer.colors.BRIGHT_BLACK,
    )


def _salir_si_error(funcion, *args, **kwargs):
    try:
        return funcion(*args, **kwargs)
    except ConfigError as exc:
        typer.secho(f"\n✗ {exc}\n", fg=typer.colors.RED)
        raise typer.Exit(code=2) from exc


EmbeddingsOpt = Annotated[
    str | None,
    typer.Option(
        "--embeddings", help="gemini | embeddinggemma | bge_m3 | fake (por defecto: RAG_CONFIG)"
    ),
]
BackendOpt = Annotated[str, typer.Option("--backend", help=" | ".join(BACKENDS))]


@app.command()
def indexar(
    embeddings: EmbeddingsOpt = None,
    estrategia: Annotated[
        str, typer.Option("--estrategia", help="por_tipo | fija300 | fija1000")
    ] = chunking.ESTRATEGIA_POR_DEFECTO,
    reset: Annotated[bool, typer.Option("--reset", help="Borra y recrea la tabla")] = False,
    backend: BackendOpt = "pgvector",
    pausa: Annotated[
        float | None, typer.Option("--pausa", help="Segundos entre lotes (nivel gratuito)")
    ] = None,
    reporte_md: Annotated[
        bool | None,
        typer.Option(
            "--reporte/--sin-reporte",
            help="Guarda la evidencia en outputs/ (por defecto: sí, salvo con embeddings fake)",
        ),
    ] = None,
) -> None:
    """Carga, divide, embebe e indexa la base de conocimiento (idempotente)."""
    perfil = _salir_si_error(componentes.perfil_embeddings, embeddings)
    emb = _salir_si_error(componentes.armar_embeddings, perfil)
    chunks = indexing.preparar_chunks(estrategia)
    almacen = _salir_si_error(
        crear_almacen, emb, perfil, backend=backend, estrategia=estrategia, reset=reset
    )
    typer.secho(
        f"Indexando {len(chunks)} chunks ({estrategia}) con {perfil.name} "
        f"({perfil.model}, {perfil.dimensions} dim) en {almacen.tabla}…",
        fg=typer.colors.BLUE,
    )
    reporte = indexing.indexar(
        almacen,
        chunks,
        pausa_s=pausa,
        progreso=lambda hecho, total: typer.echo(f"  embebidos {hecho}/{total}"),
    )
    _titulo("Resultado")
    typer.echo(f"  chunks: {reporte.total_chunks} · por tipo: {reporte.por_tipo}")
    typer.echo(
        f"  agregados: {reporte.agregados} · eliminados: {reporte.eliminados} · "
        f"sin cambios: {reporte.sin_cambios}"
    )
    typer.echo(f"  tokens aproximados: {reporte.tokens_aproximados} · tiempo: {reporte.segundos} s")
    typer.echo(f"  índice: {reporte.indice}")
    typer.echo(f"  en la base: {almacen.conteo_por_tipo()}")

    humo = indexing.consultas_de_humo(almacen)
    _titulo("Consultas de humo (top-1 sin filtro)")
    for h in humo:
        typer.echo(
            f"  {_marca(h['ok'])} {h['tipo_esperado']:<10} → {h['tipo_obtenido']} "
            f"({h['similitud']:.4f}) {h['fuente']}"
        )
    if reporte_md if reporte_md is not None else perfil.backend != "fake":
        _, md = indexing.escribir_reporte(
            reporte, perfil.name, perfil.model, perfil.dimensions, humo, OUTPUTS_DIR
        )
        typer.echo(f"\n  Evidencia: {md}")


@app.command()
def preguntar(
    mensaje: Annotated[str, typer.Argument(help="Pregunta del cliente")],
    variante: Annotated[str, typer.Option("--variante", help=" | ".join(VARIANTES))] = "mejorado",
    k: Annotated[int | None, typer.Option("--k", help="Chunks a recuperar")] = None,
    umbral: Annotated[float | None, typer.Option("--umbral", help="Similitud mínima")] = None,
    proveedor: Annotated[
        str | None, typer.Option("--proveedor", help="gemini | anthropic | ollama | fake")
    ] = None,
    embeddings: EmbeddingsOpt = None,
    backend: BackendOpt = "pgvector",
    mostrar_contexto: Annotated[
        bool, typer.Option("--mostrar-contexto", help="Imprime los chunks y el prompt final")
    ] = False,
) -> None:
    """Cadena RAG sola (sin router): recupera, responde citando fuentes y valida."""
    partes = _salir_si_error(componentes.armar_almacen, embeddings, backend=backend)
    llm = _salir_si_error(componentes.armar_llm, proveedor)
    resultado = responder(mensaje, partes.almacen, llm, variante=variante, k=k, umbral=umbral)
    _mostrar_rag(resultado, mostrar_contexto)


def _mostrar_rag(resultado, mostrar_contexto: bool) -> None:
    rec = resultado.recuperacion
    _titulo(f"Recuperación (k={rec.k}, umbral={rec.umbral}, mejor={rec.mejor_score})")
    for i, chunk in enumerate(rec.chunks, start=1):
        typer.echo(f"  {i}. {chunk.similitud:.4f} · {chunk.fuente} [{chunk.idioma}]")
        if mostrar_contexto:
            for linea in chunk.texto.splitlines():
                typer.secho(f"       {linea}", fg=typer.colors.BRIGHT_BLACK)
    typer.echo(f"  → {resultado.pasos()['2_decision']}")

    if mostrar_contexto and resultado.prompt:
        _titulo("Prompt final (último mensaje)")
        typer.secho(resultado.prompt[-1]["contenido"], fg=typer.colors.BRIGHT_BLACK)

    typer.secho("\nRespuesta", fg=typer.colors.GREEN, bold=True)
    typer.echo(resultado.respuesta)

    if resultado.checks:
        _titulo("Chequeos automáticos")
        for nombre, ok, detalle in resultado.checks:
            color = typer.colors.GREEN if ok else typer.colors.RED
            typer.secho(f"  {_marca(ok)} {nombre}: {detalle}", fg=color)

    meta = resultado.metadatos
    tokens = f"{meta.get('tokens_entrada')}/{meta.get('tokens_salida')}"
    typer.secho(
        f"\n[{meta.get('modelo', 'sin LLM')} · {resultado.llamadas} llamada(s) · "
        f"{meta.get('latencia_s', 0)} s · tokens {tokens}]",
        fg=typer.colors.BRIGHT_BLACK,
    )


if __name__ == "__main__":
    app()
