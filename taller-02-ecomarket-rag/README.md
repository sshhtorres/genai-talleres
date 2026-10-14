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
| H0 | Versiones y APIs verificadas ([`docs/versiones.md`](docs/versiones.md)) | Hecho en la nube; pendiente lo que requiere Ollama y claves |
| H1 | Infraestructura y configuración (`docker compose`, perfiles, `taller02 proveedores`) | Hecho |
| H2 | Base de conocimiento sintética y set de evaluación ([`data/`](data/README.md)) | Hecho |
| H3 | Carga, chunking e indexación | Pendiente |
| H4 | Recuperación y cadena RAG | Pendiente |
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

Existe además la configuración `pruebas` (embeddings y LLM falsos, sin red), que usan los tests y la CI.

Todos los IDs de modelo, dimensiones y niveles viven en [`providers.toml`](../providers.toml); los
parámetros del RAG (tamaño de chunk, *k*, umbral), en [`parametros.toml`](parametros.toml).

## Pruebas

```bash
uv run pytest            # sin red ni servicios externos
uv run ruff check . && uv run ruff format --check .
```
