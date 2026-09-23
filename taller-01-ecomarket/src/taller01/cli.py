"""Interfaz de línea de comandos del Taller 1."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated

import typer

from genai_common import ConfigError, LLMClient, RunRecord, RunRecorder, list_profiles

from . import chains, data

app = typer.Typer(
    add_completion=False,
    help="Taller 1 · EcoMarket: cadenas de prompts para atención al cliente.",
    no_args_is_help=True,
)

OUTPUTS_DIR = Path(__file__).resolve().parents[2] / "outputs"

VarianteOpt = Annotated[str, typer.Option("--variante", help="basico | mejorado")]
ProveedorOpt = Annotated[str | None, typer.Option("--proveedor", help="gemini | anthropic | fake")]


def _cliente(proveedor: str | None, rol: str | None = None) -> LLMClient:
    try:
        return LLMClient.from_profile(proveedor, model_role=rol)
    except ConfigError as exc:
        typer.secho(f"\n✗ {exc}\n", fg=typer.colors.RED)
        raise typer.Exit(code=2) from exc


def _mostrar(resultado: chains.ResultadoCadena, mostrar_pasos: bool = True) -> None:
    if mostrar_pasos and resultado.pasos:
        typer.secho("\nPasos de la cadena", fg=typer.colors.BLUE, bold=True)
        for nombre, valor in resultado.pasos.items():
            typer.echo(f"  · {nombre}: {valor}")

    typer.secho("\nRespuesta", fg=typer.colors.GREEN, bold=True)
    typer.echo(resultado.respuesta)

    if resultado.checks:
        typer.secho("\nChequeos automáticos", fg=typer.colors.BLUE, bold=True)
        for nombre, ok, detalle in resultado.checks:
            color = typer.colors.GREEN if ok else typer.colors.RED
            typer.secho(f"  {'✓' if ok else '✗'} {nombre}: {detalle}", fg=color)

    meta = resultado.metadatos
    typer.secho(
        f"\n[{meta.get('proveedor', '?')} · {meta.get('modelo', '?')} · "
        f"{resultado.llamadas} llamada(s) · {meta.get('latencia_s', 0)} s]",
        fg=typer.colors.BRIGHT_BLACK,
    )


@app.command()
def proveedores() -> None:
    """Lista los perfiles de providers.toml, su estado y si la clave está configurada."""
    typer.secho(
        f"{'Proveedor':<12} {'Estado':<16} {'Clave':<22} Modelo por defecto",
        fg=typer.colors.BLUE,
        bold=True,
    )
    for perfil in list_profiles():
        if not perfil.requires_key:
            clave = "no requiere"
            color = typer.colors.BRIGHT_BLACK
        elif perfil.key_configured:
            clave = f"{perfil.api_key_env} ✓"
            color = typer.colors.GREEN
        else:
            clave = f"{perfil.api_key_env} ✗"
            color = typer.colors.YELLOW
        typer.secho(f"{perfil.name:<12} {perfil.status:<16} {clave:<22} {perfil.model}", fg=color)
    typer.secho(
        "\nLas claves se definen en el archivo .env de la raíz (ver .env.example).",
        fg=typer.colors.BRIGHT_BLACK,
    )


@app.command()
def pedido(
    mensaje: Annotated[str, typer.Argument(help="Mensaje del cliente")],
    variante: VarianteOpt = "mejorado",
    contexto: Annotated[str, typer.Option("--contexto", help="completo | registro")] = "completo",
    proveedor: ProveedorOpt = None,
) -> None:
    """Ejercicio 1: consulta el estado de un pedido."""
    resultado = chains.consultar_pedido(
        mensaje, _cliente(proveedor), variante=variante, contexto=contexto
    )
    _mostrar(resultado)


@app.command()
def devolucion(
    mensaje: Annotated[str, typer.Argument(help="Mensaje del cliente")],
    tracking: Annotated[str | None, typer.Option("--tracking", help="Ej. ECO-1004")] = None,
    producto: Annotated[str | None, typer.Option("--producto", help="Id, ej. P-106")] = None,
    variante: VarianteOpt = "mejorado",
    proveedor: ProveedorOpt = None,
) -> None:
    """Ejercicio 2: gestiona una solicitud de devolución."""
    resultado = chains.gestionar_devolucion(
        mensaje,
        _cliente(proveedor),
        tracking=tracking,
        producto_id=producto,
        variante=variante,
    )
    _mostrar(resultado)


@app.command()
def evaluar(
    proveedor: ProveedorOpt = None,
    variante: Annotated[
        str, typer.Option("--variante", help="basico | mejorado | ambas")
    ] = "ambas",
    ejercicio: Annotated[
        str, typer.Option("--ejercicio", help="pedido | devolucion | ambos")
    ] = "ambos",
    contexto: Annotated[str, typer.Option("--contexto")] = "completo",
    pausa: Annotated[
        float, typer.Option("--pausa", help="Segundos entre llamadas (límites del tier gratuito)")
    ] = 4.0,
    limite: Annotated[int | None, typer.Option("--limite", help="Máximo de casos")] = None,
    etiqueta: Annotated[
        str,
        typer.Option("--etiqueta", help="Prefijo del reporte; evita sobrescribir otra corrida"),
    ] = "resultados",
) -> None:
    """Ejecuta la matriz de casos y guarda la evidencia en outputs/."""
    cliente = _cliente(proveedor)
    variantes = ["basico", "mejorado"] if variante == "ambas" else [variante]
    casos = [c for c in data.load_casos() if ejercicio == "ambos" or c["ejercicio"] == ejercicio]
    if limite:
        casos = casos[:limite]

    recorder = RunRecorder(
        OUTPUTS_DIR, proveedor=cliente.profile.name, modelo=cliente.model, etiqueta=etiqueta
    )
    total = len(casos) * len(variantes)
    typer.secho(
        f"Ejecutando {total} combinaciones con {cliente.profile.name} ({cliente.model})…",
        fg=typer.colors.BLUE,
    )

    hecho = 0
    for caso in casos:
        for var in variantes:
            hecho += 1
            typer.echo(f"  [{hecho}/{total}] {caso['id']} · {var}")
            try:
                resultado = _ejecutar_caso(caso, cliente, var, contexto)
            except Exception as exc:  # la evaluación no se detiene por un caso que falla
                typer.secho(f"      ✗ error: {exc}", fg=typer.colors.RED)
                continue
            recorder.add(
                RunRecord(
                    caso_id=caso["id"],
                    ejercicio=caso["ejercicio"],
                    variante=var,
                    mensaje=caso["mensaje"],
                    respuesta=resultado.respuesta,
                    checks=resultado.checks + _checks_del_caso(caso, resultado),
                    metadatos=resultado.metadatos,
                    pasos=resultado.pasos,
                )
            )
            if pausa and hecho < total:
                time.sleep(pausa)

    jsonl, md = recorder.write()
    verdes = sum(1 for r in recorder.records if r.ok)
    typer.secho(
        f"\n✓ {verdes}/{len(recorder.records)} casos con todos los chequeos en verde",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"  Reporte:  {md}")
    typer.echo(f"  Registro: {jsonl}")


def _ejecutar_caso(
    caso: dict, cliente: LLMClient, variante: str, contexto: str
) -> chains.ResultadoCadena:
    if caso["ejercicio"] == "pedido":
        return chains.consultar_pedido(
            caso["mensaje"], cliente, variante=variante, contexto=contexto
        )
    return chains.gestionar_devolucion(
        caso["mensaje"],
        cliente,
        tracking=caso.get("tracking"),
        producto_id=caso.get("producto_id"),
        variante=variante,
    )


def _checks_del_caso(caso: dict, resultado: chains.ResultadoCadena) -> list[tuple[str, bool, str]]:
    """Chequeos declarados en casos_prueba.yaml (debe_contener / no_debe_contener)."""
    esperado = caso.get("esperado") or {}
    texto = resultado.respuesta.lower()
    extra: list[tuple[str, bool, str]] = []
    for fragmento in esperado.get("debe_contener") or []:
        ok = fragmento.lower() in texto
        extra.append((f"contiene:{fragmento}", ok, "ok" if ok else "ausente"))
    for fragmento in esperado.get("no_debe_contener") or []:
        ok = fragmento.lower() not in texto
        extra.append((f"no_contiene:{fragmento}", ok, "ok" if ok else "aparece y no debería"))
    return extra


if __name__ == "__main__":
    app()
