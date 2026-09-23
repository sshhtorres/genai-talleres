# Taller 1 — EcoMarket: atención al cliente con IA generativa

## El caso

EcoMarket es una tienda en línea de productos sostenibles que recibe **miles de consultas diarias**
por chat, correo y redes sociales. El **80%** son repetitivas (estado de pedido, devoluciones,
características del producto) y el **20%** son complejas (quejas, problemas técnicos, sugerencias).
El tiempo de respuesta llega a **24 horas** y el equipo está desbordado.

El taller pide tres cosas: seleccionar y justificar un modelo, analizar sus fortalezas, limitaciones
y riesgos éticos, y diseñar prompts efectivos para dos tareas concretas.

## Los datos

EcoMarket es una empresa ficticia, así que [`data/`](data/) contiene un dataset sintético que hace el
papel de sus sistemas: el asistente no recuerda el estado de un pedido, lo consulta.

| Archivo | Qué es |
|---|---|
| [`data/pedidos.json`](data/pedidos.json) | 12 pedidos que cubren los 8 estados posibles |
| [`data/catalogo.json`](data/catalogo.json) | 15 productos en 8 categorías, retornables y no retornables |
| [`data/politica_devoluciones.md`](data/politica_devoluciones.md) | La política que aplica el asistente |
| [`data/casos_prueba.yaml`](data/casos_prueba.yaml) | 25 casos de prueba con su comportamiento esperado |

El criterio con el que se construyó cada archivo, y qué cubre, está en
[`data/README.md`](data/README.md).

Todos los datos son **sintéticos y sin información personal**: los pedidos solo llevan ciudad de
destino, no nombres, direcciones ni teléfonos.
