"""Comprobaciones de los servicios externos: Postgres + pgvector y Ollama."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from genai_common import ConfigError

from .config import postgres_config


@dataclass
class Estado:
    ok: bool
    detalle: str
    extra: list[str] = field(default_factory=list)


def estado_postgres(timeout_s: int = 2) -> Estado:
    """¿Responde Postgres y tiene la extensión vector?"""
    try:
        config = postgres_config()
    except ConfigError as exc:
        return Estado(False, str(exc))

    import psycopg

    try:
        with psycopg.connect(config.dsn, connect_timeout=timeout_s) as conexion:
            fila = conexion.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()
            tablas = [
                r[0]
                for r in conexion.execute(
                    "SELECT tablename FROM pg_tables WHERE tablename LIKE 'kb\\_%' ORDER BY 1"
                ).fetchall()
            ]
    except psycopg.OperationalError:
        return Estado(
            False,
            f"no responde en {config.host}:{config.port}. Levántala con `docker compose up -d`.",
        )
    if not fila:
        return Estado(False, "responde, pero sin la extensión vector (CREATE EXTENSION vector;)")
    return Estado(True, f"{config.host}:{config.port}/{config.db} · pgvector {fila[0]}", tablas)


def estado_ollama(base_url: str = "http://localhost:11434", timeout_s: float = 2.0) -> Estado:
    """¿Responde Ollama? Devuelve los modelos descargados en `extra`."""
    try:
        respuesta = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout_s)
        respuesta.raise_for_status()
    except httpx.HTTPError:
        return Estado(False, f"no responde en {base_url}. Instálalo desde https://ollama.com.")
    modelos = sorted(m.get("name", "") for m in respuesta.json().get("models", []))
    return Estado(True, f"{base_url} · {len(modelos)} modelo(s) descargado(s)", modelos)


def modelo_descargado(modelo: str, descargados: list[str]) -> bool:
    """Ollama lista 'bge-m3:latest' aunque se haya pedido 'bge-m3'."""
    return modelo in descargados or f"{modelo}:latest" in descargados
