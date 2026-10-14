# Taller 2 — EcoMarket: RAG para la atención al cliente

> **Estado: en desarrollo.** Este README crece con cada hito; la versión final (rúbrica, experimentos
> y prueba desde un clon limpio) llega en el hito H9.

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
| H5 | Router e integración con el Taller 1 | Pendiente |
| H6 | Script de clase, original y modernizado | Pendiente |
| H7 | Evaluación y experimentos | Pendiente |
| H8 | Documentos de las fases y notebook | Pendiente |
| H9 | Calidad, CI y README final | Pendiente |

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
`outputs/indexacion_<fecha>_<perfil>.md`.

`preguntar` ejecuta solo la cadena RAG (sin router) y muestra los chunks recuperados con su
similitud, la decisión de abstención, la respuesta con sus citas y los chequeos automáticos.

Sin Docker ni claves: `RAG_CONFIG=pruebas uv run taller02 preguntar "…" --backend memoria` indexa en
memoria con embeddings léxicos falsos y responde con un modelo falso que copia la primera frase del
mejor fragmento.

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

Medido en un equipo solo CPU (ARM64, WSL2): `gemma4:e4b` ocupa ≈ 7,1 GiB de RAM residente y
`embeddinggemma` ≈ 0,7 GiB, más Postgres. Cabe holgado en `cpu-16gb`; con unos 11 GiB visibles, la
sugerencia `cpu-8gb` es la correcta. Gemma 4 piensa por defecto: el perfil `ollama` lo desactiva con
`reasoning_effort = "none"` (sin eso, una respuesta corta tardó entre 36 y 89 s).

Existe además la configuración `pruebas` (embeddings y LLM falsos, sin red), que usan los tests y la CI.

Todos los IDs de modelo, dimensiones y niveles viven en [`providers.toml`](../providers.toml); los
parámetros del RAG (tamaño de chunk, *k*, umbral), en [`parametros.toml`](parametros.toml).

## Pruebas

```bash
uv run pytest                  # sin red ni servicios externos
uv run pytest -m integration   # contra el Postgres de docker compose, con embeddings falsos
uv run ruff check . && uv run ruff format --check .
```
