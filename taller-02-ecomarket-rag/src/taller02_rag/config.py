"""Rutas y parámetros del taller (parametros.toml) y conexión a Postgres (.env)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from genai_common import ConfigError, load_env

TALLER_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = TALLER_DIR / "data"
KB_DIR = DATA_DIR / "kb"
EVAL_DIR = DATA_DIR / "eval"
PROMPTS_DIR = TALLER_DIR / "prompts"
OUTPUTS_DIR = TALLER_DIR / "outputs"
PARAMETROS = TALLER_DIR / "parametros.toml"
CACHE_DIR = TALLER_DIR.parent / ".cache" / "embeddings"


@lru_cache(maxsize=1)
def parametros() -> dict[str, Any]:
    """Contenido de parametros.toml."""
    with PARAMETROS.open("rb") as fh:
        return tomllib.load(fh)


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    user: str
    password: str
    db: str

    @property
    def url(self) -> str:
        """URL de SQLAlchemy con el driver psycopg 3 (lo usa langchain-postgres)."""
        return f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @property
    def dsn(self) -> str:
        """Cadena de conexión de psycopg, para comprobaciones directas."""
        return (
            f"host={self.host} port={self.port} user={self.user} "
            f"password={self.password} dbname={self.db}"
        )


def postgres_config() -> PostgresConfig:
    """Lee PG_* del entorno o del .env, con un error accionable si falta alguna."""
    load_env()
    faltan = [
        v for v in ("PG_HOST", "PG_PORT", "PG_USER", "PG_PASSWORD", "PG_DB") if not os.getenv(v)
    ]
    if faltan:
        raise ConfigError(
            f"Faltan variables de Postgres: {', '.join(faltan)}. Copia el bloque 'base vectorial' "
            "de .env.example a tu .env y levanta la base con `docker compose up -d`."
        )
    return PostgresConfig(
        host=os.environ["PG_HOST"],
        port=int(os.environ["PG_PORT"]),
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
        db=os.environ["PG_DB"],
    )
