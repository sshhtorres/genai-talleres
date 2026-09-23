# Datos del Taller 1

EcoMarket es una empresa ficticia, así que no existe un dataset real que consultar. Los cuatro
archivos generados lo sustituyen: hacen el papel de **los sistemas de la empresa**. El asistente
nunca "recuerda" el estado de un pedido, lo **consulta** aquí a través de
[`src/taller01/data.py`](../src/taller01/data.py).

| Archivo | Qué es | Contenido |
|---|---|---|
| [`pedidos.json`](pedidos.json) | La base de pedidos | 12 pedidos, `ECO-1001`…`ECO-1012` |
| [`catalogo.json`](catalogo.json) | El catálogo de productos | 15 productos en 8 categorías |
| [`politica_devoluciones.md`](politica_devoluciones.md) | La política que aplica el asistente | Plazo, condiciones, no retornables, excepciones y retracto |
| [`casos_prueba.yaml`](casos_prueba.yaml) | La suite de evaluación | 25 casos: 11 de pedidos y 14 de devoluciones |

Todos los datos son **sintéticos y sin información personal**: los pedidos solo tienen ciudad de
destino, no nombres, direcciones ni teléfonos. Es una decisión deliberada de minimización: al
asistente le basta el estado del pedido para responder, así que no hay motivo para enviar a un
proveedor externo un dato que no necesita. Una prueba automática falla si alguien introduce un campo
con datos personales.

## Cómo se generaron

Los archivos los generó un asistente de código a partir de una especificación de cobertura, no un
generador aleatorio de datos. La diferencia importa: un generador aleatorio produce muchos registros
parecidos y ninguno de los casos difíciles, mientras que aquí cada registro existe para **ejercitar
una rama concreta** de las cadenas de prompts o de las reglas de negocio.

Las secciones siguientes documentan esa especificación: qué tenía que cubrir cada archivo y por qué.

### `pedidos.json`

Doce pedidos elegidos para que los **ocho estados posibles** queden cubiertos, porque el prompt
mejorado del ejercicio 1 define una regla de respuesta distinta para cada uno:

| Estado | Cuántos | Para qué |
|---|:--:|---|
| `en_transito` | 2 | Caso base: fecha estimada y enlace de rastreo |
| `en_reparto` | 1 | Entrega prevista para hoy |
| `entregado` | 3 | Uno reciente (devolución en plazo), uno perecedero y **uno entregado hace más de 30 días** para el caso «fuera de plazo» |
| `retrasado` | 2 | Con **motivos distintos** (cierre vial y avería del vehículo): obliga a citar el motivo real y no uno genérico |
| `en_preparacion` | 1 | Devolución sobre un pedido no entregado aún |
| `cancelado` | 1 | Estado del reembolso |
| `extraviado` | 1 | Disculpa + escalamiento a un agente humano |
| `devuelto` | 1 | Devolución ya procesada |

Campos de cada registro: `tracking_number`, `fecha_compra`, `productos`, `estado`, `transportadora`,
`fecha_estimada_entrega`, `fecha_entrega_real`, `motivo_retraso`, `ciudad_destino`, `link_rastreo` y
`observacion`. Los enlaces usan el dominio de ejemplo `https://ecomarket.example/rastreo/{tracking}`,
reservado por la RFC 2606 y por tanto imposible de confundir con un sitio real.

Las fechas son coherentes entre sí y relativas al campo **`fecha_referencia`** del propio archivo
(`2026-09-23`). Ese campo es lo que hace reproducible el cálculo de plazos: `data.py` lo usa como
«hoy» en lugar de la fecha del sistema, así que la prueba de «fuera de plazo» sigue dando el mismo
resultado dentro de un año.

### `catalogo.json`

Quince productos sostenibles, 10 retornables y 5 no retornables, repartidos en ocho categorías
elegidas para cubrir **todas las reglas de la política**: `hogar`, `cocina`, `textil`,
`alimentos_perecederos`, `higiene_personal`, `granel`, `tarjeta_regalo` y `personalizado`. Cada
producto lleva una bandera `retornable` y una `nota_retorno` que explica su caso.

Los pedidos referencian estos identificadores, y hay una prueba que falla si alguno apunta a un
producto inexistente. Entre los pedidos hay, a propósito, al menos un perecedero, un artículo de
higiene y un producto no retornable que **llegó dañado**, que es el caso que activa la excepción de
la política.

### `politica_devoluciones.md`

Redactada como la escribiría la empresa, no como una lista de reglas para el modelo: plazo de 30 días
desde la entrega, condiciones, categorías no retornables, excepción por producto defectuoso o dañado,
y derecho de retracto. Se apoya en el Estatuto del Consumidor colombiano (Ley 1480 de 2011) para que
las reglas del ejercicio 2 tengan un fundamento real y no inventado.

El texto se pasa íntegro al modelo dentro de `<politica>`, pero **la decisión no la toma el modelo**:
`data.evaluar_devolucion()` implementa las mismas reglas en Python y el código verifica al modelo
contra ellas.

### `casos_prueba.yaml`

Veinticinco casos con el comportamiento esperado de cada uno. Cubren el camino feliz y, sobre todo,
los bordes: número de pedido inexistente, mensaje sin número, mensaje con dos números, intento de
**inyección de prompts**, producto fuera de plazo, perecedero, higiene abierta y producto dañado.

Los últimos cuatro son **pares contrafactuales** (`cf-ciudad-a`/`b` y `cf-registro-a`/`b`): la misma
solicitud de devolución cambiando solo la ciudad, o solo la forma de escribir. Sirven para medir el
riesgo de sesgo: si la decisión o el nivel de detalle cambian dentro de un par, el asistente está
tratando distinto a clientes que merecen el mismo trato.

## Verificación

La integridad del dataset no se confía a la vista: la comprueba
[`tests/test_data.py`](../tests/test_data.py) en cada ejecución de `uv run pytest`. Entre otras
cosas, falla si hay menos de 12 pedidos, si un `tracking_number` está repetido, si un pedido apunta a
un producto que no existe, si un pedido retrasado no tiene motivo, si un enlace de rastreo no
corresponde a su pedido, o si algún registro incorpora un campo con datos personales.
