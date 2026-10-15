"""Integridad de la base de conocimiento sintética y del set de evaluación (H2)."""

import re
from collections import Counter

import pytest

from taller01 import data as t1
from taller02_rag import kb
from taller02_rag.config import KB_DIR

AREAS = ["Devoluciones y garantías", "Envíos", "Pagos y cuenta", "Sostenibilidad"]


def _area(nombre: str) -> list[kb.Seccion]:
    return [s for s in kb.politicas()[1] if s.ruta[0] == nombre]


def _faqs() -> list[kb.Seccion]:
    return [
        s for s in kb.politicas()[1] if len(s.ruta) == 3 and s.ruta[1] == "Preguntas frecuentes"
    ]


# -- políticas y preguntas frecuentes ------------------------------------------


def test_politicas_tiene_version_y_vigencia():
    datos, _ = kb.politicas()
    assert datos["version"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", datos["vigente_desde"])


def test_politicas_tiene_las_cuatro_areas_y_cada_una_sus_preguntas():
    areas = [s.ruta[0] for s in kb.politicas()[1]]
    assert list(dict.fromkeys(areas)) == AREAS
    for area in AREAS:
        faqs = [s for s in _faqs() if s.ruta[0] == area]
        assert len(faqs) >= 4, f"{area} tiene {len(faqs)} preguntas frecuentes"


def test_entre_20_y_25_preguntas_frecuentes():
    faqs = _faqs()
    assert 20 <= len(faqs) <= 25
    assert all(s.ruta[-1].endswith("?") for s in faqs)
    assert len({s.nombre for s in faqs}) == len(faqs), "hay preguntas repetidas"


def test_ninguna_seccion_vacia_ni_ambigua():
    """Secciones autocontenidas: nada de 'ver sección anterior' (inútil como chunk)."""
    for seccion in kb.politicas()[1]:
        assert len(seccion.cuerpo) > 40, seccion.nombre
        assert "sección anterior" not in seccion.cuerpo.lower(), seccion.nombre


# -- coherencia con las reglas en código del Taller 1 ---------------------------


def test_plazo_de_devolucion_coincide_con_evaluar_devolucion():
    """Toda mención de 'N días calendario' en Devoluciones es el plazo de 30 días de data.py."""
    texto = " ".join(s.cuerpo for s in _area("Devoluciones y garantías"))
    plazos = {int(n) for n in re.findall(r"(\d+) días calendario", texto)}
    assert plazos == {t1.PLAZO_DEVOLUCION_DIAS}


def test_retracto_coincide_con_data_py():
    retracto = next(
        s for s in _area("Devoluciones y garantías") if "retracto" in s.ruta[-1].lower()
    )
    assert f"{t1.PLAZO_RETRACTO_DIAS_HABILES} días hábiles" in retracto.cuerpo


@pytest.mark.parametrize(
    ("categoria", "en_politica"),
    [
        ("alimentos_perecederos", "alimentos perecederos"),
        ("granel", "a granel"),
        ("tarjeta_regalo", "tarjetas de regalo"),
        ("personalizado", "personalizados"),
    ],
)
def test_categorias_no_retornables_coinciden(categoria, en_politica):
    assert categoria in t1.CATEGORIAS_NO_RETORNABLES
    seccion = next(
        s for s in _area("Devoluciones y garantías") if s.ruta[-1] == "Productos no retornables"
    )
    assert en_politica in seccion.cuerpo.lower()


def test_todas_las_categorias_no_retornables_estan_en_la_politica():
    assert len(t1.CATEGORIAS_NO_RETORNABLES) == 4  # si data.py cambia, actualizar el test anterior


def test_la_excepcion_por_defecto_cubre_todas_las_categorias():
    seccion = next(
        s for s in _area("Devoluciones y garantías") if s.ruta[-1].startswith("Producto defectuoso")
    )
    assert "aunque pertenezca a una categoría no retornable" in seccion.cuerpo


def test_umbral_de_envio_gratis_es_unico():
    texto = " ".join(s.cuerpo for s in _area("Envíos"))
    assert set(re.findall(r"(\d{3}\.\d{3}) pesos", texto)) == {"150.000"}


# -- reglas de crédito -----------------------------------------------------------


def test_reglas_de_credito_completas_y_unicas():
    reglas = kb.reglas_credito()["reglas"]
    assert 15 <= len(reglas) <= 20
    ids = [r["id"] for r in reglas]
    assert len(set(ids)) == len(ids)
    campos = {"id", "tema", "regla", "condiciones", "ejemplo", "vigente_desde"}
    for regla in reglas:
        assert set(regla) == campos, regla["id"]
        assert all(str(regla[c]).strip() for c in campos), regla["id"]


def test_credito_sin_tasas_reales():
    """Las tasas se describen frente a la usura vigente: ningún porcentaje concreto."""
    texto = str(kb.reglas_credito())
    assert "%" not in texto
    assert "tasa de usura" in texto


def test_credito_cubre_los_temas_del_plan():
    texto = kb.normalizar(str(kb.reglas_credito()))
    for tema in (
        "mayores de 18",
        "cupo",
        "cuotas",
        "monto",
        "usura",
        "anticipad",
        "corte",
        "mora",
        "centrales de riesgo",
        "devolucion",
        "no se pueden financiar",
    ):
        assert tema in texto, tema


def test_la_politica_y_el_credito_dicen_lo_mismo_de_las_compras_financiadas():
    politica = kb.normalizar(" ".join(s.cuerpo for s in _area("Devoluciones y garantías")))
    regla = next(r for r in kb.reglas_credito()["reglas"] if r["id"] == "CR-15")
    assert "anula las cuotas pendientes" in politica
    assert "se anulan las cuotas pendientes" in kb.normalizar(regla["regla"])


# -- catálogo ---------------------------------------------------------------------


def test_catalogo_tiene_los_15_productos_del_taller_1():
    filas = kb.catalogo()
    t1_productos = {p["id"]: p for p in t1.load_catalogo()["productos"]}
    assert {f["sku"] for f in filas} == set(t1_productos)
    for fila in filas:
        original = t1_productos[fila["sku"]]
        assert fila["categoria"] == original["categoria"], fila["sku"]
        assert (fila["retornable"] == "true") == original["retornable"], fila["sku"]


def test_catalogo_conserva_las_notas_de_retorno_del_taller_1():
    t1_productos = {p["id"]: p for p in t1.load_catalogo()["productos"]}
    for fila in kb.catalogo():
        if fila["idioma"] == "es":
            assert fila["nota_retorno"] == t1_productos[fila["sku"]]["nota_retorno"], fila["sku"]


def test_catalogo_sin_precio_ni_stock():
    columnas = set(kb.catalogo()[0])
    assert not {"precio", "stock", "price"} & columnas


def test_cuatro_fichas_en_ingles_y_el_resto_en_espanol():
    idiomas = Counter(f["idioma"] for f in kb.catalogo())
    assert idiomas == {"es": 11, "en": 4}


def test_ninguna_ficha_vacia():
    for fila in kb.catalogo():
        assert all(valor.strip() for valor in fila.values()), fila["sku"]


# -- términos y condiciones (PDF) -------------------------------------------------


def test_pdf_existe_y_conserva_el_texto_de_la_fuente():
    from pypdf import PdfReader

    lector = PdfReader(KB_DIR / "terminos-y-condiciones.pdf")
    paginas = [p.extract_text() for p in lector.pages]
    texto = kb.normalizar(" ".join(paginas))
    for seccion in kb.terminos_fuente()[1]:
        assert kb.normalizar(seccion.cuerpo[:80]) in texto, seccion.nombre
    # El ruido que la limpieza debe quitar: encabezado y pie repetidos en cada página.
    assert all("Términos y condiciones de compra — Versión" in p for p in paginas)
    assert all("Página" in p for p in paginas)


def test_terminos_cubren_lo_que_pide_el_plan():
    titulos = " ".join(s.ruta[-1] for s in kb.terminos_fuente()[1]).lower()
    for tema in ("medios de pago", "facturación", "datos personales", "responsabilidad"):
        assert tema in titulos


# -- sin datos personales ---------------------------------------------------------


def _todo_el_texto() -> str:
    archivos = [
        KB_DIR / "politicas-y-faq.md",
        KB_DIR / "reglas-credito.json",
        KB_DIR / "catalogo.csv",
        KB_DIR / "fuentes" / "terminos-y-condiciones.md",
    ]
    return "\n".join(a.read_text(encoding="utf-8") for a in archivos)


def test_sin_correos_reales_ni_telefonos_ni_documentos():
    texto = _todo_el_texto()
    correos = re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", texto)
    assert all(c.endswith("@ecomarket.example") for c in correos), correos
    assert not re.search(r"\b\d{7,}\b", texto), "secuencia que parece teléfono o cédula"
    assert not re.search(r"\b3\d{2}[ -]?\d{3}[ -]?\d{4}\b", texto), "número de celular"


# -- set de evaluación --------------------------------------------------------------

TIPOS = {
    "dentro_alcance",
    "fuera_alcance",
    "mixto",
    "inyeccion",
    "reformulacion",
    "translingue",
    "credito_trampa",
}
INTENCIONES = {"consulta_general", "devolucion", "credito", "estado_pedido", "fuera_de_alcance"}


def test_casos_con_esquema_valido_e_ids_unicos():
    casos = kb.casos_rag()
    ids = [c["id"] for c in casos]
    assert len(set(ids)) == len(ids)
    obligatorios = {
        "id",
        "mensaje",
        "tipo",
        "intencion_esperada",
        "fuentes_esperadas",
        "debe_contener",
        "no_debe_contener",
        "debe_abstenerse",
        "idioma_respuesta",
    }
    opcionales = {"nota", "cifras_con_respaldo"}
    for caso in casos:
        assert obligatorios <= set(caso), caso["id"]
        assert set(caso) <= obligatorios | opcionales, set(caso) - obligatorios - opcionales
        assert caso["tipo"] in TIPOS, caso["id"]
        assert caso["intencion_esperada"] in INTENCIONES, caso["id"]
        assert caso["idioma_respuesta"] in {"es", "en"}, caso["id"]
        assert caso["debe_abstenerse"] in (True, False, "opcional"), caso["id"]
        if caso["debe_abstenerse"] is True:
            assert not caso["fuentes_esperadas"], caso["id"]
        else:
            assert caso["fuentes_esperadas"], caso["id"]


def test_distribucion_minima_del_plan():
    casos = kb.casos_rag()
    tipos = Counter(c["tipo"] for c in casos)
    assert 38 <= len(casos) <= 45
    assert tipos["fuera_alcance"] >= 5
    assert tipos["mixto"] >= 3
    assert tipos["inyeccion"] >= 2
    assert tipos["reformulacion"] >= 3
    assert tipos["translingue"] >= 4
    assert tipos["credito_trampa"] >= 3

    dentro = [c for c in casos if c["tipo"] == "dentro_alcance"]
    por_doc = Counter(c["fuentes_esperadas"][0]["doc_id"] for c in dentro)
    assert all(por_doc[d] >= 4 for d in kb.DOCUMENTOS), por_doc
    areas = {
        f["seccion_o_id"].split(kb.SEPARADOR_RUTA)[0]
        for c in dentro
        for f in c["fuentes_esperadas"]
        if f["doc_id"] == kb.DOC_POLITICAS
    }
    assert set(AREAS) <= areas


def test_translingues_en_ambos_sentidos():
    casos = [c for c in kb.casos_rag() if c["tipo"] == "translingue"]
    hacia_ingles = [
        c
        for c in casos
        if c["idioma_respuesta"] == "es" and c["fuentes_esperadas"][0]["doc_id"] == kb.DOC_CATALOGO
    ]
    hacia_espanol = [c for c in casos if c["idioma_respuesta"] == "en"]
    assert len(hacia_ingles) >= 2 and len(hacia_espanol) >= 2
    fichas_en = {f["sku"] for f in kb.catalogo() if f["idioma"] == "en"}
    assert all(c["fuentes_esperadas"][0]["seccion_o_id"] in fichas_en for c in hacia_ingles)


def test_cada_fuente_esperada_existe_y_contiene_su_evidencia():
    """La evidencia es un fragmento literal: con ella se mide hit@k sin depender del chunking."""
    for caso in kb.casos_rag():
        for fuente in caso["fuentes_esperadas"]:
            texto = kb.unidad(fuente["doc_id"], fuente["seccion_o_id"])
            assert texto is not None, f"{caso['id']}: no existe {fuente}"
            assert kb.normalizar(fuente["evidencia"]) in kb.normalizar(texto), (
                f"{caso['id']}: la evidencia no está en {fuente['seccion_o_id']}"
            )
