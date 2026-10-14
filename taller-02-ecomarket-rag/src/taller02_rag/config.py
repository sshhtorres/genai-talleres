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


# Los mismos valores por defecto que docker-compose.yml: con la base del compose basta un .env sin
# variables PG_* (por ejemplo, el del Taller 1).
PG_POR_DEFECTO = {
    "PG_HOST": "localhost",
    "PG_PORT": "5433",
    "PG_USER": "ecomarket",
    "PG_PASSWORD": "ecomarket",
    "PG_DB": "ecomarket_kb",
}


def postgres_config() -> PostgresConfig:
    """Lee PG_* del entorno o del .env; si faltan, usa los valores de docker-compose.yml."""
    load_env()
    valor = {clave: os.getenv(clave) or defecto for clave, defecto in PG_POR_DEFECTO.items()}
    try:
        puerto = int(valor["PG_PORT"])
    except ValueError as exc:
        raise ConfigError(f"PG_PORT debe ser un número; vale '{valor['PG_PORT']}'.") from exc
    return PostgresConfig(
        host=valor["PG_HOST"],
        port=puerto,
        user=valor["PG_USER"],
        password=valor["PG_PASSWORD"],
        db=valor["PG_DB"],
    )
