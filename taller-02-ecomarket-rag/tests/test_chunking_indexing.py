"""Carga, limpieza, chunking e indexación (H3), sin red."""

from collections import Counter

from langchain_core.documents import Document

from genai_common.embeddings import build_embeddings, get_embedding_profile
from taller02_rag import chunking, indexing, loaders
from taller02_rag.config import parametros
from taller02_rag.store import crear_almacen, nombre_tabla

TAMANO = parametros()["chunking"]["chunk_size"]


def test_ningun_chunk_vacio_y_todos_con_idioma(chunks_por_tipo):
    assert all(c.page_content.strip() for c in chunks_por_tipo)
    assert all(c.metadata["idioma"] in {"es", "en"} for c in chunks_por_tipo)


def test_politicas_y_terminos_respetan_chunk_size(chunks_por_tipo):
    for chunk in chunks_por_tipo:
        if chunk.metadata["tipo"] in {"politicas", "terminos"}:
            assert len(chunk.page_content) <= TAMANO, chunk.metadata.get("seccion")


def test_cada_pregunta_frecuente_es_exactamente_un_chunk(chunks_por_tipo):
    faqs = [c for c in chunks_por_tipo if c.metadata["es_faq"]]
    secciones = Counter(c.metadata["seccion"] for c in faqs)
    assert len(secciones) == 24
    assert set(secciones.values()) == {1}


def test_un_chunk_por_regla_y_por_producto(chunks_por_tipo):
    tipos = Counter(c.metadata["tipo"] for c in chunks_por_tipo)
    assert tipos["credito"] == 18
    assert tipos["producto"] == 15
    reglas = [c.metadata["id_regla"] for c in chunks_por_tipo if c.metadata["tipo"] == "credito"]
    assert len(set(reglas)) == 18


def test_chunks_de_politicas_llevan_area_y_seccion(chunks_por_tipo):
    politicas = [c for c in chunks_por_tipo if c.metadata["tipo"] == "politicas"]
    areas = {c.metadata["area"] for c in politicas}
    assert areas == {"devoluciones", "envios", "pagos", "sostenibilidad"}
    for chunk in politicas:
        # La ruta de encabezados viaja dentro del texto que se embebe.
        assert chunk.page_content.startswith(chunk.metadata["seccion"])


def test_fichas_en_ingles_conservan_su_idioma(chunks_por_tipo):
    productos = [c for c in chunks_por_tipo if c.metadata["tipo"] == "producto"]
    en = {c.metadata["sku"] for c in productos if c.metadata["idioma"] == "en"}
    assert en == {"P-101", "P-106", "P-110", "P-111"}
    ficha = next(c for c in productos if c.metadata["sku"] == "P-106")
    assert ficha.page_content.startswith("Product: Stainless steel thermal bottle")


def test_ficha_serializada_es_autocontenida():
    ficha = next(d for d in loaders.cargar_catalogo() if d.metadata["sku"] == "P-103")
    assert "Producto: Café orgánico en grano 500 g." in ficha.page_content
    assert "Retornable: no." in ficha.page_content


def test_ficha_conserva_la_condicion_de_devolucion_del_taller_1():
    """P-115 es de 'hogar', pero su ficha exige empaque sellado: la condición no se pierde."""
    ficha = next(d for d in loaders.cargar_catalogo() if d.metadata["sku"] == "P-115")
    assert "Condiciones de devolución: Solo si el empaque está sellado." in ficha.page_content


def test_pdf_sin_encabezado_ni_pie():
    limpias = loaders.cargar_terminos()
    sucias = loaders.cargar_terminos(limpiar=False)
    assert all("Página" not in d.page_content for d in limpias)
    assert all("Versión 1.0" not in d.page_content for d in limpias)
    assert any("Página" in d.page_content for d in sucias)


def test_lineas_repetidas_normaliza_numeros_de_pagina():
    paginas = [
        "Encabezado\nuno\nPágina 1",
        "Encabezado\ndos\nPágina 2",
        "Encabezado\ntres\nPágina 3",
    ]
    assert loaders.lineas_repetidas(paginas) == {"Encabezado", "Página #"}
    assert loaders.lineas_repetidas(["solo una página"]) == set()


def test_estrategias_fijas_cortan_al_tamano():
    documentos = loaders.cargar_todo()
    for nombre, tamano in parametros()["chunking"]["fijas"].items():
        chunks = chunking.dividir(documentos, nombre)
        assert all(len(c.page_content) <= tamano for c in chunks)
        assert all(c.metadata["estrategia"] == nombre for c in chunks)
        assert "seccion" not in chunks[0].metadata  # la estrategia ingenua pierde la estructura


def test_nombre_de_tabla_por_modelo_y_estrategia():
    perfil = get_embedding_profile("gemini")
    assert nombre_tabla(perfil) == "kb_gemini_768"
    assert nombre_tabla(perfil, "fija300") == "kb_gemini_768_fija300"
    assert nombre_tabla(perfil, sufijo="enriq") == "kb_gemini_768_enriq"


def test_chunk_id_deterministico_y_sin_duplicados():
    a = indexing.enriquecer([Document("igual", metadata={"doc_id": "x"})] * 3)
    b = indexing.enriquecer([Document("igual", metadata={"doc_id": "x"})])
    assert len(a) == 1
    assert a[0].metadata["chunk_id"] == b[0].metadata["chunk_id"]


def test_indexar_dos_veces_no_cambia_el_conteo(chunks_por_tipo):
    perfil = get_embedding_profile("fake")
    almacen = crear_almacen(build_embeddings(perfil), perfil, backend="memoria")
    primero = indexing.indexar(almacen, chunks_por_tipo, pausa_s=0)
    segundo = indexing.indexar(almacen, chunks_por_tipo, pausa_s=0)
    assert primero.agregados == len(chunks_por_tipo)
    assert segundo.agregados == 0 and segundo.sin_cambios == len(chunks_por_tipo)
    assert sum(almacen.conteo_por_tipo().values()) == len(chunks_por_tipo)


def test_reindexar_borra_los_chunks_que_ya_no_existen(chunks_por_tipo):
    perfil = get_embedding_profile("fake")
    almacen = crear_almacen(build_embeddings(perfil), perfil, backend="memoria")
    indexing.indexar(almacen, chunks_por_tipo, pausa_s=0)
    reporte = indexing.indexar(almacen, chunks_por_tipo[1:], pausa_s=0)
    assert reporte.eliminados == 1
    assert len(almacen.ids()) == len(chunks_por_tipo) - 1


def test_reporte_de_indexacion_enriquecida_no_pisa_el_principal(tmp_path):
    from taller02_rag import indexing

    reporte = indexing.ReporteIndexacion("kb", "por_tipo", 1, 1, 0, 0)
    _, principal = indexing.escribir_reporte(reporte, "gemini", "m", 768, [], tmp_path)
    _, enriq = indexing.escribir_reporte(
        reporte, "gemini", "m", 768, [], tmp_path, variante="enriq"
    )
    assert principal != enriq and enriq.stem.endswith("_gemini_enriq")
