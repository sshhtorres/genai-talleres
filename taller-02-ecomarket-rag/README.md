# Taller 2 — EcoMarket: RAG para la atención al cliente

> **Estado: en desarrollo.** Este README crece con cada hito; la versión final (rúbrica, experimentos
> y prueba desde un clon limpio) llega en el hito H9.

## Entregables y rúbrica

| Criterio | Dónde está |
|---|---|
| **Selección de componentes**: embedding y base vectorial justificados por español, costo, escalabilidad, ventajas y desventajas, ligados a EcoMarket; impacto de cada componente | [`docs/fase-1-componentes.md`](docs/fase-1-componentes.md) · experimentos E4, E7 y E8 |
| **Base de conocimiento**: al menos tres tipos de documento (hay cuatro, en cuatro formatos), chunking justificado, calidad e indexación | [`docs/fase-2-base-conocimiento.md`](docs/fase-2-base-conocimiento.md), [`data/`](data/README.md) · experimento E2 |
| **Integración y código**: el script de clase explicado paso a paso y modernizado; cómo se conectan embedding, base vectorial y cadena; modificaciones de código y prompt con cambios observados; limitaciones y suposiciones | [`docs/fase-3-integracion.md`](docs/fase-3-integracion.md), [`scripts/`](scripts/), [`src/taller02_rag/`](src/taller02_rag/), [`prompts/`](prompts/), [`notebooks/fase3_demo.ipynb`](notebooks/fase3_demo.ipynb) · experimentos E1, E3 y E5 |
| Evidencia de todas las corridas reales | [`outputs/`](outputs/) (no se edita a mano) |

## El caso

En el Taller 1, el asistente de EcoMarket respondía bien dos tipos de solicitud (estado de pedido y
devoluciones) porque la información estaba en código o dentro del prompt. El Taller 2 añade
**generación aumentada por recuperación (RAG)**: el asistente responde cualquier pregunta respaldada
por los documentos de la empresa (envíos, pagos, financiación, productos), en español o en inglés,
cita la fuente y **se abstiene** cuando no hay evidencia. La cadena del Taller 1 se reutiliza: los
pedidos se siguen consultando por código y la decisión de una devolución sigue saliendo de
`evaluar_devolucion()`.

## Estado por hito

| Hito | Contenido | Estado |
|---|---|---|
| H0 | Versiones y APIs verificadas ([`docs/versiones.md`](docs/versiones.md)) | Hecho (en la nube y en local); pendientes los límites del nivel gratuito de Gemini |
| H1 | Infraestructura y configuración (`docker compose`, perfiles, `taller02 proveedores`) | Hecho |
| H2 | Base de conocimiento sintética y set de evaluación ([`data/`](data/README.md)) | Hecho |
| H3 | Carga, chunking e indexación (`taller02 indexar`) | Hecho con embeddings `fake`; pendiente la indexación real |
| H4 | Recuperación y cadena RAG (`taller02 preguntar`) | Hecho con LLM `fake`; pendiente con modelos reales |
| H5 | Router e integración con el Taller 1 (`taller02 atender`) | Hecho con modelos `fake`; pendiente con modelos reales |
| H6 | Script de clase, original y modernizado (`scripts/`) | Hecho; pendiente la ejecución con Ollama |
| H7 | Evaluación y experimentos (`taller02 evaluar`, `calibrar`) | Código hecho y probado con modelos `fake`; pendientes las corridas reales |
| H8 | Documentos de las fases y notebook | Borradores con la parte conceptual completa; pendientes las cifras de las corridas reales. Notebook ejecutado en modo `pruebas` |
| H9 | Calidad, CI y README final | CI con job de integración (pgvector); pendiente el README final |

## Puesta en marcha

Requisitos: [uv](https://docs.astral.sh/uv/), Docker y, para las configuraciones `hibrida` y
`local`, [Ollama](https://ollama.com).

```bash
uv sync --all-groups                    # desde la raíz del repositorio
cp .env.example .env                    # completa las claves y elige RAG_CONFIG
docker compose up -d                    # Postgres + pgvector en el puerto 5433
uv run taller02 proveedores --recomendar
```

`taller02 proveedores` muestra la configuración activa, los perfiles de LLM y de embeddings, la tabla
de la base vectorial que se usará y si Postgres y Ollama responden. Con `--recomendar` sugiere un
nivel de hardware según la RAM; no modifica el `.env`.

## Indexar y preguntar

```bash
uv run taller02 indexar                          # embeddings de RAG_CONFIG, estrategia por_tipo
uv run taller02 indexar --embeddings embeddinggemma
uv run taller02 indexar --estrategia fija300     # línea base del experimento E2 (otra tabla)
uv run taller02 preguntar "¿Qué hago con los frascos de vidrio vacíos?" --mostrar-contexto
uv run taller02 preguntar "¿Cuánto cuesta el envío?" --variante basico --k 2
```

`indexar` es idempotente: el id de cada chunk es un hash de su contenido, así que repetirlo sin
cambios no vuelve a calcular embeddings, y si un documento cambió, sus chunks viejos se borran. Al
terminar ejecuta una consulta de humo por tipo de documento y guarda la evidencia en
`outputs/indexacion_<fecha>_<perfil>[_<estrategia>][_enriq].md` (las variantes no pisan el reporte
de la base principal).

`preguntar` ejecuta solo la cadena RAG (sin router) y muestra los chunks recuperados con su
similitud, la decisión de abstención, la respuesta con sus citas y los chequeos automáticos.

Sin Docker ni claves: `RAG_CONFIG=pruebas uv run taller02 preguntar "…" --backend memoria` indexa en
memoria con embeddings léxicos falsos y responde con un modelo falso que copia la primera frase del
mejor fragmento.

## Atender: el asistente completo

```bash
uv run taller02 atender "¿Dónde está mi pedido ECO-1005?"                 # pedido (sin router)
uv run taller02 atender "Mi pedido ECO-1004 llegó, ¿cómo devuelvo la botella?"   # devolución
uv run taller02 atender "¿A cuántas cuotas puedo pagar una compra de 700.000?"   # crédito
uv run taller02 atender "¿Qué hago con los frascos de vidrio vacíos?"     # consulta general
```

`atender` es el punto de entrada único y muestra la ruta elegida:

| Ruta | Quién responde | Cómo se decide |
|---|---|---|
| `estado_pedido` | Cadena del Taller 1, solo con el registro del pedido | Hay un `ECO-xxxx` en el mensaje: regla en código, sin LLM |
| `devolucion` | Cadena del Taller 1 con la política **recuperada** (`area=devoluciones`); la decisión sale de `evaluar_devolucion()` | Tracking + palabras de devolución (sin LLM), o el router |
| `credito` | Cadena RAG con las reglas de crédito y las de "no decidir": no aprueba, no calcula cuotas, no recomienda endeudarse | Router (modelo del rol `router`) |
| `consulta_general` | Cadena RAG sobre toda la base | Router |
| `fuera_de_alcance` | Respuesta desde código | Router, o una etiqueta no válida |

## Evaluación y experimentos

```bash
uv run taller02 calibrar --embeddings gemini            # umbral de abstención del perfil
uv run taller02 evaluar --experimento E2 --embeddings gemini     # chunking (sin LLM)
uv run taller02 evaluar --experimento E2 --embeddings embeddinggemma  # requiere indexar sus 3 tablas
uv run taller02 evaluar --experimento E4                          # embeddings (sin LLM)
uv run taller02 enriquecer && uv run taller02 indexar --enriquecer-ingles
uv run taller02 evaluar --experimento E7 --embeddings gemini     # fichas en inglés (sin LLM)
uv run taller02 evaluar --experimento E1 --pausa 4               # prompt basico vs mejorado
uv run taller02 evaluar --experimento E3 --pausa 4               # k = 1, 4, 8
uv run taller02 evaluar --experimento E5 --pausa 4               # sin RAG vs con RAG
uv run taller02 evaluar --experimento E8 --limite 10             # nube, hibrida y local
# --limite toma una muestra estratificada: un caso de cada tipo por turno, no los N primeros.
```

| Exp. | Qué se modifica | LLM | Requisitos previos |
|---|---|---|---|
| E1 | Prompt `basico` vs `mejorado` (casos en verde con y sin el chequeo de citas, que el básico no pide) | Sí | Base indexada con los embeddings de `RAG_CONFIG` |
| E2 | Chunking `por_tipo` / `fija300` / `fija1000` | No | `indexar --estrategia …` para las tres, con el perfil de `--embeddings` (cada perfil y estrategia es otra tabla: `kb_embeddinggemma_768_fija300`…) |
| E3 | *k* = 1, 4, 8 | Sí | Base indexada |
| E4 | `gemini` / `embeddinggemma` / `bge_m3` | No | `indexar --embeddings …` para los tres (`--perfiles` elige cuáles) |
| E5 | Asistente sin RAG vs `atender` con RAG | Sí | Base indexada |
| E7 | Catálogo tal cual vs fichas en inglés enriquecidas | No | `enriquecer` y `indexar --enriquecer-ingles` |
| E8 | Configuraciones con *streaming*: TTFT, latencia, tokens y costo | Sí | Bases de `gemini` y `embeddinggemma`; Ollama; `--configuraciones` elige cuáles |

Las métricas de recuperación (hit@k, MRR) cuentan un acierto cuando un chunk recuperado contiene
la `evidencia` literal del caso. `calibrar` muestra la distribución del mejor *score* dentro y
fuera de alcance (con los translingües aparte), propone el umbral y lo guarda en
`parametros.toml`, uno por perfil de embeddings. Todo queda en `outputs/` con el formato
`<experimento>_<fecha>_<proveedor o perfil>.{md,jsonl|json}`.

## Script de clase

```bash
uv run --with "langchain-chroma==1.1.0" python taller-02-ecomarket-rag/scripts/rag_ejemplo_modernizado.py
```

Los mismos 7 pasos del ejemplo de clase con las APIs actuales (embeddinggemma con prefijos en vez
de `llama2`, `langchain_chroma`, LCEL en vez de `RetrievalQA`, `.invoke` en vez de `.run`, fuentes en
la respuesta). Al final del archivo está la tabla "Qué cambió y por qué". Chroma no es dependencia
del taller: `uv run --with` lo instala solo para esa ejecución.

## Configuraciones de ejecución

Se elige con `RAG_CONFIG` en el `.env`; cambiar de configuración no requiere tocar el código. Embedding
y LLM son piezas independientes: lo único que debe coincidir es el modelo de embeddings con el que se
indexó y el que se usa al consultar, por eso cada uno tiene su propia tabla.

| | `nube` | `hibrida` | `local` |
|---|---|---|---|
| Embeddings | `gemini-embedding-001` @ 768 | `embeddinggemma:300m` @ 768 (Ollama) | `embeddinggemma:300m` @ 768 (Ollama) |
| LLM | Gemini | Gemini o Claude Haiku 5.5 (`RAG_LLM`) | Gemma 4 según `LOCAL_TIER` |
| Tabla | `kb_gemini_768` | `kb_embeddinggemma_768` | `kb_embeddinggemma_768` |
| Requisitos | `GEMINI_API_KEY` | Ollama + clave del LLM elegido | Ollama |
| Modelos a descargar | — | `ollama pull embeddinggemma:300m` | `ollama pull embeddinggemma:300m` y el del nivel |

Niveles de hardware de la configuración `local` (se eligen a mano; solo `cpu-16gb` se ejecuta en el
taller):

| `LOCAL_TIER` | Máquina | LLM |
|---|---|---|
| `cpu-8gb` | Solo CPU, 8 GB | `gemma4:e2b` |
| `cpu-16gb` | Solo CPU, 16 GB o más | `gemma4:e4b` |
| `gpu-12gb` | GPU con ~12 GB | `gemma4:12b` |
| `gpu-24gb` | GPU con 24 GB | `gemma4:26b` |

Medido en un equipo solo CPU (Snapdragon X, ARM64, WSL2 con 19 GiB, 2026-10-14):

| | `nube` | `hibrida` (Haiku 5.5) | `local` (`gemma4:e4b`) |
|---|---:|---:|---:|
| Indexar las 89 secciones | 3,3 s | 214 s (embeddinggemma en CPU) | 214 s |
| `atender`, por pregunta | 3,6–4,5 s | 5,2–15,2 s | 20–160 s |

- `gemma4:e4b` ocupa ≈ 7,1 GiB de RAM residente y `embeddinggemma` ≈ 0,7 GiB, más Postgres: cabe
  holgado en `cpu-16gb`; con unos 11 GiB visibles, la sugerencia `cpu-8gb` es la correcta.
- Gemma 4 piensa por defecto: el perfil `ollama` lo desactiva (`reasoning = false` en LangChain,
  `reasoning_effort = "none"` en el Taller 1). Aun así, en CPU el cuello de botella es leer el prompt
  (≈ 38 tokens/s) y cada ruta hace dos llamadas.
- **`local` sirve para demostrar que todo corre sin salir de la máquina, no para uso interactivo**:
  los experimentos con LLM se corren completos con `nube` y `hibrida`, y con `local` sobre un
  subconjunto (`--limite`).
- La indexación es idempotente: los 3,5 minutos de `embeddinggemma` se pagan una sola vez.

Existe además la configuración `pruebas` (embeddings y LLM falsos, sin red), que usan los tests y la CI.

Todos los IDs de modelo, dimensiones y niveles viven en [`providers.toml`](../providers.toml); los
parámetros del RAG (tamaño de chunk, *k*, umbral), en [`parametros.toml`](parametros.toml).

## Pruebas

```bash
uv run pytest                  # sin red ni servicios externos
uv run pytest -m integration   # contra el Postgres de docker compose, con embeddings falsos
uv run ruff check . && uv run ruff format --check .
```
