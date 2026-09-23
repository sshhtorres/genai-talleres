"""Pruebas de integridad de los datos sintéticos y de las reglas de negocio."""

from datetime import date

import pytest

from taller01 import data


def test_hay_al_menos_doce_pedidos():
    assert len(data.load_pedidos()["pedidos"]) >= 12


def test_trackings_unicos_y_con_formato():
    trackings = [p["tracking_number"] for p in data.load_pedidos()["pedidos"]]
    assert len(set(trackings)) == len(trackings)
    assert all(data.TRACKING_RE.fullmatch(t) for t in trackings)


def test_todos_los_estados_declarados_estan_cubiertos():
    documento = data.load_pedidos()
    estados_usados = {p["estado"] for p in documento["pedidos"]}
    assert estados_usados == set(documento["estados_validos"])


def test_los_productos_de_los_pedidos_existen_en_el_catalogo():
    ids = {p["id"] for p in data.load_catalogo()["productos"]}
    for pedido in data.load_pedidos()["pedidos"]:
        for item in pedido["productos"]:
            assert item["id"] in ids, f"{item['id']} no está en el catálogo"


def test_el_catalogo_cubre_las_categorias_criticas():
    categorias = {p["categoria"] for p in data.load_catalogo()["productos"]}
    assert {"alimentos_perecederos", "higiene_personal", "granel", "tarjeta_regalo"} <= categorias


def test_los_enlaces_de_rastreo_son_coherentes():
    for pedido in data.load_pedidos()["pedidos"]:
        esperado = f"https://ecomarket.example/rastreo/{pedido['tracking_number']}"
        assert pedido["link_rastreo"] == esperado


def test_los_pedidos_no_contienen_pii():
    """Los registros solo traen ciudad: ni nombres, ni correos, ni teléfonos, ni direcciones."""
    import json

    registros = json.dumps(data.load_pedidos()["pedidos"], ensure_ascii=False).lower()
    prohibidos = ["@", "teléfono", "cédula", "dirección", "calle ", "carrera ", "nombre_cliente"]
    for prohibido in prohibidos:
        assert prohibido not in registros, f"posible PII en pedidos.json: {prohibido}"

    campos_permitidos = {
        "tracking_number",
        "fecha_compra",
        "productos",
        "estado",
        "transportadora",
        "fecha_estimada_entrega",
        "fecha_entrega_real",
        "motivo_retraso",
        "ciudad_destino",
        "link_rastreo",
        "observacion",
    }
    for pedido in data.load_pedidos()["pedidos"]:
        assert set(pedido) <= campos_permitidos, set(pedido) - campos_permitidos


def test_los_retrasados_tienen_motivo():
    for pedido in data.load_pedidos()["pedidos"]:
        if pedido["estado"] in {"retrasado", "extraviado"}:
            assert pedido["motivo_retraso"], pedido["tracking_number"]


def test_los_casos_de_prueba_referencian_datos_existentes():
    for caso in data.load_casos():
        if caso.get("tracking") and caso["id"] != "ej1-inexistente":
            assert data.buscar_pedido(caso["tracking"]), caso["id"]
        if caso.get("producto_id"):
            assert data.buscar_producto(caso["producto_id"]), caso["id"]


# -- búsquedas ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("hola, mi pedido ECO-1003 no llega", ["ECO-1003"]),
        ("quiero saber de ECO-1001 y de ECO-1005", ["ECO-1001", "ECO-1005"]),
        ("eco-1007 en minúsculas", ["ECO-1007"]),
        ("ECO-1001 y otra vez ECO-1001", ["ECO-1001"]),
        ("no tengo el número", []),
    ],
)
def test_extraer_trackings(texto, esperado):
    assert data.extraer_trackings(texto) == esperado


def test_buscar_pedido_inexistente_devuelve_none():
    assert data.buscar_pedido("ECO-9999") is None
    assert data.buscar_pedido(None) is None


def test_buscar_producto_por_nombre():
    assert data.buscar_producto_por_nombre("quiero devolver el café en grano")["id"] == "P-103"
    assert data.buscar_producto_por_nombre("la botella térmica")["id"] == "P-106"
    assert data.buscar_producto_por_nombre("una licuadora") is None


def test_dias_desde_entrega():
    pedido = data.buscar_pedido("ECO-1007")
    assert data.dias_desde_entrega(pedido, hoy=date(2026, 9, 23)) == 3
    assert data.dias_desde_entrega(data.buscar_pedido("ECO-1001")) is None


# -- reglas de devolución ----------------------------------------------------


def _evaluar(tracking, producto_id, defectuoso=False):
    return data.evaluar_devolucion(
        data.buscar_pedido(tracking),
        data.buscar_producto(producto_id),
        defectuoso=defectuoso,
        hoy=date(2026, 9, 23),
    )


def test_retornable_en_plazo_es_elegible():
    regla = _evaluar("ECO-1004", "P-106")
    assert regla.elegible == "si"
    assert regla.regla_aplicada == "retornable_en_plazo"


def test_fuera_de_plazo_no_es_elegible():
    regla = _evaluar("ECO-1008", "P-107")
    assert regla.elegible == "no"
    assert regla.regla_aplicada == "fuera_de_plazo"
    assert regla.dias_desde_entrega > data.PLAZO_DEVOLUCION_DIAS


def test_perecedero_no_es_elegible():
    assert _evaluar("ECO-1007", "P-103").regla_aplicada == "categoria_no_retornable"


def test_defecto_vence_a_la_categoria_no_retornable():
    regla = _evaluar("ECO-1004", "P-113", defectuoso=True)
    assert regla.elegible == "si"
    assert regla.regla_aplicada == "excepcion_producto_defectuoso"


def test_pedido_no_entregado_requiere_revision():
    regla = _evaluar("ECO-1009", "P-109")
    assert regla.elegible == "requiere_revision"
    assert regla.regla_aplicada == "pedido_no_entregado"


def test_datos_faltantes_requieren_revision():
    regla = data.evaluar_devolucion(None, None)
    assert regla.elegible == "requiere_revision"
    assert set(regla.datos_faltantes) == {"numero_de_pedido", "producto"}


def test_pedido_cancelado_y_devuelto_no_son_elegibles():
    assert _evaluar("ECO-1010", "P-112").regla_aplicada == "pedido_cancelado"
    assert _evaluar("ECO-1012", "P-102").regla_aplicada == "pedido_ya_devuelto"
