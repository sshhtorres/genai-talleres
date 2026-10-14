"""Fábrica de la base vectorial: Postgres + pgvector (`PGVectorStore`) o memoria (tests).

`AlmacenVectorial` es un envoltorio delgado con lo que necesitan la indexación y la recuperación:
qué ids hay, agregar, borrar, buscar con *score* y contar por tipo. Su razón de ser es normalizar
el *score*: `PGVectorStore` devuelve **distancia** coseno (0 = idéntico, más bajo es mejor) y
`InMemoryVectorStore` devuelve **similitud** coseno (1 = idéntico, más alto es mejor). Aquí ambos
salen como similitud en [0, 1], que es lo que compara el umbral de abstención.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

from genai_common.embeddings import EmbeddingProfile

from .chunking import ESTRATEGIA_POR_DEFECTO
from .config import postgres_config

# Metadatos que van en columnas propias (y no solo en el JSON) porque se filtra por ellos:
# langchain-postgres solo filtra sobre columnas.
COLUMNAS_FILTRABLES: dict[str, str] = {
    "doc_id": "TEXT",
    "tipo": "TEXT",
    "area": "TEXT",
    "idioma": "TEXT",
    "es_faq": "BOOLEAN",
}

BACKENDS = ("pgvector", "memoria")


def nombre_tabla(
    perfil: EmbeddingProfile, estrategia: str = ESTRATEGIA_POR_DEFECTO, sufijo: str = ""
) -> str:
    """kb_<perfil>_<dim>[_<estrategia>][_<sufijo>]: un espacio vectorial por modelo y variante.

    La estrategia por defecto no aparece en el nombre; las de los experimentos sí (E2: `_fija300`),
    para poder compararlas sin reindexar cada vez.
    """
    partes = [perfil.table_name]
    if estrategia != ESTRATEGIA_POR_DEFECTO:
        partes.append(estrategia)
    if sufijo:
        partes.append(sufijo)
    return "_".join(partes)


@dataclass
class AlmacenVectorial:
    """Base vectorial con *scores* normalizados a similitud en [0, 1]."""

    backend: str
    tabla: str
    vectorstore: Any
    dimensiones: int
    perfil: str = ""  # perfil de embeddings: define la escala de similitudes y su umbral
    _engine: Any = field(default=None, repr=False)

    # -- consulta -------------------------------------------------------------------

    def buscar(
        self, pregunta: str, k: int, filtro: dict[str, Any] | None = None
    ) -> list[tuple[Document, float]]:
        """Los k chunks más parecidos a la pregunta, con similitud coseno en [0, 1]."""
        if self.backend == "memoria":
            kwargs: dict[str, Any] = {}
            if filtro:
                kwargs["filter"] = lambda d: all(d.metadata.get(c) == v for c, v in filtro.items())
            crudos = self.vectorstore.similarity_search_with_score(pregunta, k=k, **kwargs)
            return [(d, _acotar(s)) for d, s in crudos]
        crudos = self.vectorstore.similarity_search_with_score(pregunta, k=k, filter=filtro or None)
        return [(d, _acotar(1.0 - distancia)) for d, distancia in crudos]

    # -- mantenimiento ----------------------------------------------------------------

    def ids(self) -> set[str]:
        if self.backend == "memoria":
            return set(self.vectorstore.store)
        filas = self._sql(f'SELECT langchain_id::text FROM "{self.tabla}"')
        return {fila[0] for fila in filas}

    def agregar(self, documentos: list[Document], ids: list[str]) -> None:
        self.vectorstore.add_documents(documentos, ids=ids)

    def eliminar(self, ids: list[str]) -> None:
        if ids:
            self.vectorstore.delete(ids=ids)

    def conteo_por_tipo(self) -> dict[str, int]:
        if self.backend == "memoria":
            return dict(
                Counter(v["metadata"].get("tipo", "") for v in self.vectorstore.store.values())
            )
        filas = self._sql(f'SELECT tipo, count(*) FROM "{self.tabla}" GROUP BY tipo ORDER BY tipo')
        return {tipo: n for tipo, n in filas}

    def crear_indice(self) -> str:
        """Índice HNSW con distancia coseno. En memoria no aplica: la búsqueda es exacta."""
        if self.backend == "memoria":
            return "búsqueda exacta (memoria)"
        from langchain_postgres.v2.indexes import DistanceStrategy, HNSWIndex

        nombre = f"{self.tabla}_hnsw"
        if not self.vectorstore.is_valid_index(nombre):
            self.vectorstore.apply_vector_index(
                HNSWIndex(name=nombre, distance_strategy=DistanceStrategy.COSINE_DISTANCE)
            )
        return f"HNSW coseno ({nombre})"

    def _sql(self, consulta: str) -> list[tuple]:
        import psycopg

        with psycopg.connect(postgres_config().dsn) as conexion:
            return conexion.execute(consulta).fetchall()


def _acotar(valor: float) -> float:
    return round(max(0.0, min(1.0, float(valor))), 4)


def crear_almacen(
    embeddings: Embeddings,
    perfil: EmbeddingProfile,
    backend: str = "pgvector",
    estrategia: str = ESTRATEGIA_POR_DEFECTO,
    sufijo: str = "",
    reset: bool = False,
) -> AlmacenVectorial:
    """Base vectorial para un perfil de embeddings. `reset=True` borra y recrea la tabla."""
    tabla = nombre_tabla(perfil, estrategia, sufijo)
    if backend == "memoria":
        return AlmacenVectorial(
            "memoria", tabla, InMemoryVectorStore(embeddings), perfil.dimensions
        )
    if backend != "pgvector":
        raise ValueError(f"Backend desconocido: '{backend}'. Disponibles: {', '.join(BACKENDS)}.")

    from langchain_postgres import Column, PGEngine, PGVectorStore

    engine = PGEngine.from_connection_string(postgres_config().url)
    if reset:
        engine.drop_table(tabla)
    if not _existe_tabla(tabla):
        engine.init_vectorstore_table(
            tabla,
            perfil.dimensions,
            metadata_columns=[Column(n, t) for n, t in COLUMNAS_FILTRABLES.items()],
        )
    vectorstore = PGVectorStore.create_sync(
        engine, embeddings, tabla, metadata_columns=list(COLUMNAS_FILTRABLES)
    )
    return AlmacenVectorial("pgvector", tabla, vectorstore, perfil.dimensions, perfil.name, engine)


def _existe_tabla(tabla: str) -> bool:
    import psycopg

    with psycopg.connect(postgres_config().dsn) as conexion:
        fila = conexion.execute("SELECT to_regclass(%s)", (f'public."{tabla}"',)).fetchone()
    return bool(fila and fila[0])
