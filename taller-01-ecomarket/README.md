# Taller 1 — EcoMarket: atención al cliente con IA generativa

## Entregables y rúbrica

| Criterio de la rúbrica | Dónde está |
|---|---|
| **1. Selección y justificación del modelo** (2 pts) | [`docs/fase-1-seleccion-modelo.md`](docs/fase-1-seleccion-modelo.md) |
| **2. Fortalezas, limitaciones y riesgos éticos** (2 pts) | [`docs/fase-2-evaluacion-riesgos.md`](docs/fase-2-evaluacion-riesgos.md) |
| **3. Ingeniería de prompts** (1 pt) | [`notebooks/fase3_demo.ipynb`](notebooks/fase3_demo.ipynb), [`docs/fase-3-prompts.md`](docs/fase-3-prompts.md), [`prompts/`](prompts/), [`src/taller01/`](src/taller01/), [`outputs/`](outputs/) |

## El caso

EcoMarket es una tienda en línea de productos sostenibles que recibe **miles de consultas diarias**
por chat, correo y redes sociales. El **80%** son repetitivas (estado de pedido, devoluciones,
características del producto) y el **20%** son complejas (quejas, problemas técnicos, sugerencias).
El tiempo de respuesta llega a **24 horas** y el equipo está desbordado.

El taller pide tres cosas: seleccionar y justificar un modelo, analizar sus fortalezas, limitaciones
y riesgos éticos, y diseñar prompts efectivos para dos tareas concretas.

## Cómo ejecutar

```bash
uv sync --all-groups                 # desde la raíz del repositorio
cp .env.example .env                 # y completa GEMINI_API_KEY (y ANTHROPIC_API_KEY)
uv run taller01 proveedores          # verifica qué claves están configuradas

uv run taller01 pedido "Hola, ¿dónde está mi pedido ECO-1005?"
uv run taller01 devolucion "El café no me gustó, ¿lo puedo devolver?" --tracking ECO-1007
uv run taller01 evaluar --proveedor gemini --variante ambas
```

Opciones útiles:

| Opción | Para qué |
|---|---|
| `--variante basico\|mejorado` | Compara el prompt del enunciado contra el prompt con técnicas |
| `--contexto completo\|registro` | Envía todo el documento de pedidos o solo el registro encontrado |
| `--proveedor gemini\|anthropic\|fake` | Cambia de modelo sin tocar el código |
| `--pausa N` / `--limite N` | Respeta los límites de tasa del tier gratuito |

Sin claves de API también se puede revisar el trabajo: los tests corren con un proveedor falso
(`uv run pytest`) y los resultados de las ejecuciones reales están versionados en [`outputs/`](outputs/).

## Qué hay en cada carpeta

| Carpeta | Contenido |
|---|---|
| [`docs/`](docs/) | Los entregables de las tres fases |
| [`data/`](data/) | Datos sintéticos: 12 pedidos, 15 productos, política de devoluciones y casos de prueba. Cómo se generaron, en [`data/README.md`](data/README.md) |
| [`prompts/`](prompts/) | Prompts en TOML, con las técnicas aplicadas comentadas en el propio archivo |
| [`src/taller01/`](src/taller01/) | `data.py` (búsqueda y reglas), `chains.py` (cadenas), `checks.py` (validaciones), `cli.py` |
| [`notebooks/`](notebooks/) | Demostración ejecutada de la Fase 3, lado a lado |
| [`outputs/`](outputs/) | Evidencia de las ejecuciones reales (no se edita a mano) |
| [`tests/`](tests/) | Pruebas sin red, con el proveedor falso |
