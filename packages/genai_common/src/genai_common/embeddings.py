"""Perfiles de embeddings (providers.toml -> [embeddings.*]) y su fábrica de LangChain.

Dos ideas guían este módulo:

1. **Asimetría pregunta/documento.** Los modelos de recuperación esperan una señal distinta para
   la pregunta y para el documento: Gemini usa `task_type` y EmbeddingGemma usa prefijos de texto.
   Si se omite no hay error, pero la recuperación empeora en silencio. Por eso la fábrica devuelve
   un objeto que aplica la señal correcta en `embed_documents` (indexar) y en `embed_query`
   (consultar), sin que el resto del código tenga que recordarlo.
2. **Vectores de modelos distintos no son comparables**, aunque tengan la misma dimensión. Cada
   perfil tiene su propia tabla (`table_name`) y su propio espacio en la caché.

Las dependencias de LangChain son opcionales (extra `langchain`): se importan dentro de las
funciones para no imponérselas al Taller 1.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .config import ConfigError, _donde_conseguir, _load_raw, find_repo_root, load_env

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings

BACKENDS = ("google", "ollama", "fake")


@dataclass(frozen=True)
class EmbeddingProfile:
    """Perfil de un modelo de embeddings tal como está declarado en providers.toml."""

    name: str
    backend: str
    model: str
    dimensions: int
    api_key_env: str = ""
    base_url: str = ""
    task_type_document: str = ""
    task_type_query: str = ""
    document_prefix: str = ""
    query_prefix: str = ""
    status: str = "implementado"
    notas: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def table_name(self) -> str:
        """Tabla de la base vectorial: un espacio vectorial por modelo y dimensión."""
        return f"kb_{self.name}_{self.dimensions}"

    @property
    def cache_namespace(self) -> str:
        """Espacio de la caché: cambiar de modelo o de dimensión nunca reutiliza vectores."""
        return re.sub(r"[^\w.-]", "_", f"{self.name}_{self.model}_{self.dimensions}")

    @property
    def key_configured(self) -> bool:
        return not self.api_key_env or bool(os.getenv(self.api_key_env))

    def api_key(self) -> str:
        """Devuelve la API key o explica exactamente qué falta."""
        if not self.api_key_env:
            return ""
        valor = os.getenv(self.api_key_env)
        if not valor:
            raise ConfigError(
                f"Falta la variable de entorno {self.api_key_env} para los embeddings "
                f"'{self.name}'. Copia .env.example a .env y define "
                f"{self.api_key_env}=<tu clave>. {_donde_conseguir('gemini')}"
            )
        return valor


def list_embedding_profiles(root: Path | None = None) -> list[EmbeddingProfile]:
    """Todos los perfiles de embeddings declarados, en el orden del archivo."""
    raiz = root or find_repo_root()
    load_env(raiz)
    crudo = _load_raw(str(raiz)).get("embeddings", {})
    return [_build(nombre, datos) for nombre, datos in crudo.items()]


def get_embedding_profile(name: str, root: Path | None = None) -> EmbeddingProfile:
    """Perfil de embeddings por nombre, con un error accionable si no existe."""
    raiz = root or find_repo_root()
    load_env(raiz)
    crudo = _load_raw(str(raiz)).get("embeddings", {})
    if name not in crudo:
        raise ConfigError(
            f"Perfil de embeddings desconocido: '{name}'. "
            f"Disponibles en providers.toml: {', '.join(sorted(crudo))}."
        )
    return _build(name, crudo[name])


def _build(nombre: str, datos: dict[str, Any]) -> EmbeddingProfile:
    conocidas = set(EmbeddingProfile.__dataclass_fields__) - {"name", "extra"}
    backend = datos.get("backend", "")
    if backend not in BACKENDS:
        raise ConfigError(
            f"El perfil de embeddings '{nombre}' tiene backend '{backend}'. "
            f"Valores válidos: {', '.join(BACKENDS)}."
        )
    return EmbeddingProfile(
        name=nombre,
        **{k: v for k, v in datos.items() if k in conocidas},
        extra={k: v for k, v in datos.items() if k not in conocidas},
    )


# -- fábrica -----------------------------------------------------------------


def build_embeddings(
    profile: EmbeddingProfile,
    cache_dir: str | Path | None = None,
) -> Embeddings:
    """Objeto `Embeddings` de LangChain para un perfil.

    `embed_documents` aplica la señal de documento y `embed_query` la de pregunta. Si se pasa
    `cache_dir`, los vectores de documentos se guardan en disco (CacheBackedEmbeddings): reindexar
    sin cambios no vuelve a gastar cuota. Las preguntas no se cachean a propósito: comparten texto
    con los documentos pero llevan otra señal de tarea, y una caché común las mezclaría.
    """
    if profile.status == "por_implementar":
        raise ConfigError(
            f"El perfil de embeddings '{profile.name}' está marcado como 'por_implementar' en "
            "providers.toml: pruébalo manualmente y cambia su estado a 'implementado'."
        )
    base = _base_embeddings(profile)
    if cache_dir is None or profile.backend == "fake":
        return base

    from langchain_classic.embeddings import CacheBackedEmbeddings
    from langchain_classic.storage import LocalFileStore

    store = LocalFileStore(str(Path(cache_dir) / profile.cache_namespace))
    return CacheBackedEmbeddings.from_bytes_store(
        base, store, namespace=profile.cache_namespace, key_encoder="sha256"
    )


def _base_embeddings(profile: EmbeddingProfile) -> Embeddings:
    if profile.backend == "fake":
        return LexicalHashEmbeddings(dimensions=profile.dimensions)

    if profile.backend == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        cliente = GoogleGenerativeAIEmbeddings(
            model=profile.model,
            google_api_key=profile.api_key(),
            output_dimensionality=profile.dimensions,
        )
        return AsymmetricEmbeddings(
            cliente,
            dimensions=profile.dimensions,
            document_kwargs={"task_type": profile.task_type_document or None},
            query_kwargs={"task_type": profile.task_type_query or None},
        )

    from langchain_ollama import OllamaEmbeddings

    cliente = OllamaEmbeddings(
        model=profile.model,
        base_url=profile.base_url or None,
        dimensions=profile.dimensions,
    )
    return AsymmetricEmbeddings(
        cliente,
        dimensions=profile.dimensions,
        document_prefix=profile.document_prefix,
        query_prefix=profile.query_prefix,
    )


def _normalizar_vector(vector: list[float]) -> list[float]:
    norma = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norma for x in vector]


def _ajustar_dimension(vector: list[float], dimensions: int) -> list[float]:
    """Trunca (MRL) si llegó más largo de lo pedido y SIEMPRE normaliza a norma 1.

    gemini-embedding-001 devuelve vectores sin normalizar en cualquier dimensión distinta de 3072
    (verificado: norma ≈ 0,59 a 768). La distancia coseno no cambia el ranking, pero cualquier
    producto interno, distancia L2 o umbral sobre el producto punto quedaría mal calibrado.
    """
    return _normalizar_vector(list(vector[:dimensions]))


try:  # pragma: no cover - la rama except solo aplica si falta el extra
    from langchain_core.embeddings import Embeddings as _Embeddings
except ImportError:  # pragma: no cover
    _Embeddings = object  # type: ignore[assignment,misc]


class AsymmetricEmbeddings(_Embeddings):  # type: ignore[misc,valid-type]
    """Envoltorio que aplica la señal de documento o de pregunta al modelo de base.

    - Gemini: `task_type` distinto en cada llamada (`document_kwargs` / `query_kwargs`).
    - EmbeddingGemma vía Ollama: prefijos de texto (`task: search result | query: …`), porque
      Ollama no los añade por su cuenta.
    En ambos casos el vector sale con la dimensión del perfil (se trunca si llega más largo, como
    permite Matryoshka) y normalizado a norma 1, para que nunca entre a la tabla un vector de otra
    forma ni con otra escala.
    """

    def __init__(
        self,
        inner: Any,
        dimensions: int,
        document_prefix: str = "",
        query_prefix: str = "",
        document_kwargs: dict[str, Any] | None = None,
        query_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self.inner = inner
        self.dimensions = dimensions
        self.document_prefix = document_prefix
        self.query_prefix = query_prefix
        self.document_kwargs = {k: v for k, v in (document_kwargs or {}).items() if v}
        self.query_kwargs = {k: v for k, v in (query_kwargs or {}).items() if v}

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        entrada = [f"{self.document_prefix}{t}" for t in texts]
        vectores = self.inner.embed_documents(entrada, **self.document_kwargs)
        return [_ajustar_dimension(v, self.dimensions) for v in vectores]

    def embed_query(self, text: str) -> list[float]:
        vector = self.inner.embed_query(f"{self.query_prefix}{text}", **self.query_kwargs)
        return _ajustar_dimension(vector, self.dimensions)


_PALABRA = re.compile(r"\w+")
# Palabras vacías frecuentes (sin tildes): sin quitarlas dominan la bolsa de palabras.
_VACIAS = frozenset(
    "que los las del con por para una uno unos unas como mas pero sus este esta estos estas ese "
    "esa eso hay ser son fue han muy sin sobre entre cuando donde cual cuales quien hasta desde "
    "tambien puedo puede pueden tengo tiene hago the and for with you your are can how what does "
    "from this that have will not".split()
)


class LexicalHashEmbeddings(_Embeddings):  # type: ignore[misc,valid-type]
    """Embeddings falsos, deterministas y sin red, pero con sentido léxico.

    Cada palabra (en minúsculas y sin tildes) suma en una posición elegida por su hash, y el vector
    se normaliza. Dos textos que comparten palabras quedan cerca, así que en los tests la
    recuperación, el hit@k y la calibración del umbral se comportan como en un sistema real,
    aunque sin semántica ni capacidad translingüe. `DeterministicFakeEmbedding` de LangChain no
    sirve para eso: da vectores aleatorios por texto y la búsqueda sale al azar.
    """

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def _vector(self, texto: str) -> list[float]:
        vector = [0.0] * self.dimensions
        plano = unicodedata.normalize("NFKD", texto.lower())
        plano = "".join(c for c in plano if not unicodedata.combining(c))
        for palabra in _PALABRA.findall(plano):
            if len(palabra) < 3 or palabra in _VACIAS:
                continue
            digest = hashlib.blake2b(palabra.encode("utf-8"), digest_size=8).digest()
            indice = int.from_bytes(digest[:4], "big") % self.dimensions
            signo = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[indice] += signo
        return _normalizar_vector(vector)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
