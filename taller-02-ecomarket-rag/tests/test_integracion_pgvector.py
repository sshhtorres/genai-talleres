"""Integración con Postgres + pgvector real, con embeddings falsos (sin red ni claves).

Excluida por defecto. Para correrla: `docker compose up -d` y `uv run pytest -m integration`.
"""

import pytest

from genai_common.embeddings import build_embeddings, get_embedding_profile
from taller02_rag import indexing, retrieval, servicios
from taller02_rag.store import crear_almacen

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def almacen_pg():
    if not servicios.estado_postgres().ok:
        pytest.skip("Postgres no responde: levántalo con `docker compose up -d`")
    perfil = get_embedding_profile("fake")
    almacen = crear_almacen(
        build_embeddings(perfil), perfil, backend="pgvector", sufijo="pytest", reset=True
    )
    yield almacen
    almacen._engine.drop_table(almacen.tabla)


def test_indexacion_idempotente_en_pgvector(almacen_pg, chunks_por_tipo):
    primero = indexing.indexar(almacen_pg, chunks_por_tipo, pausa_s=0)
    segundo = indexing.indexar(almacen_pg, chunks_por_tipo, pausa_s=0)
    assert primero.agregados == len(chunks_por_tipo)
    assert segundo.agregados == 0
    assert sum(almacen_pg.conteo_por_tipo().values()) == len(chunks_por_tipo)
    assert primero.indice.startswith("HNSW")


def test_pgvector_y_memoria_devuelven_lo_mismo(almacen_pg, almacen_memoria):
    """La distancia de pgvector convertida a similitud coincide con la similitud en memoria."""
    pregunta = "¿Cuánto cuesta el envío?"
    pg = retrieval.recuperar(almacen_pg, pregunta, k=3)
    mem = retrieval.recuperar(almacen_memoria, pregunta, k=3)
    assert [c.fuente for c in pg.chunks] == [c.fuente for c in mem.chunks]
    for a, b in zip(pg.chunks, mem.chunks, strict=True):
        assert a.similitud == pytest.approx(b.similitud, abs=1e-3)


def test_filtro_por_columna_en_pgvector(almacen_pg):
    rec = retrieval.recuperar(almacen_pg, "cuotas", k=3, filtro={"tipo": "credito"})
    assert rec.chunks and all(c.documento.metadata["tipo"] == "credito" for c in rec.chunks)
