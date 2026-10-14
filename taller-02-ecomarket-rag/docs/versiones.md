# Versiones y verificación de APIs (H0)

LangChain, los IDs de modelo y las etiquetas de imágenes cambian rápido. Este documento registra
**qué se verificó, cuándo y contra qué fuente**. Lo que no se pudo verificar queda marcado como
pendiente, con el comando que lo verifica: no se supone.

## Entornos de verificación

| Entorno | Qué tenía | Qué no tenía |
|---|---|---|
| Sesión en la nube (2026-10-14) | PyPI, Docker Hub, documentación de Anthropic, Postgres 16 + pgvector 0.6.0 instalado con `apt` como sustituto del contenedor | Demonio de Docker, Ollama (su registro está bloqueado), claves de API, acceso a `ai.google.dev` y `ollama.com` |
| Equipo local (pendiente) | Docker, Ollama, claves de Gemini y Anthropic | — |

## Paquetes de Python fijados

Versiones vigentes en PyPI el 2026-10-14. Se fijan con `==` los paquetes de LangChain porque sus
APIs cambian entre versiones menores; `langchain-postgres` sigue en 0.0.x.

| Paquete | Versión | Uso | Fuente |
|---|---|---|---|
| `langchain-core` | 1.6.10 | `Embeddings`, `Document`, LCEL, `InMemoryVectorStore`, modelos falsos | [PyPI](https://pypi.org/project/langchain-core/) |
| `langchain-classic` | 1.0.8 | `CacheBackedEmbeddings` + `LocalFileStore` (en LangChain 1.x ya no están en `langchain`) y `RetrievalQA` del script de clase | [PyPI](https://pypi.org/project/langchain-classic/) |
| `langchain-text-splitters` | 1.1.3 | `RecursiveCharacterTextSplitter`, `MarkdownHeaderTextSplitter` | [PyPI](https://pypi.org/project/langchain-text-splitters/) |
| `langchain-postgres` | 0.0.19 | `PGEngine` + `PGVectorStore` (no la clase `PGVector`, obsoleta) | [PyPI](https://pypi.org/project/langchain-postgres/), [docs](https://docs.langchain.com/oss/python/integrations/vectorstores/pgvectorstore) |
| `langchain-google-genai` | 4.4.2 | `GoogleGenerativeAIEmbeddings` | [PyPI](https://pypi.org/project/langchain-google-genai/) |
| `langchain-openai` | 1.7.2 | `ChatOpenAI` con `base_url` (Gemini, Anthropic y Ollama por su endpoint compatible) | [PyPI](https://pypi.org/project/langchain-openai/) |
| `langchain-ollama` | 1.1.0 | `OllamaEmbeddings` | [PyPI](https://pypi.org/project/langchain-ollama/) |
| `langchain-chroma` | 1.1.0 | Solo el script de clase modernizado (extra `scripts`) | [PyPI](https://pypi.org/project/langchain-chroma/) |
| `psycopg[binary]` | ≥ 3.2 | Driver de Postgres de `langchain-postgres` y comprobaciones | [PyPI](https://pypi.org/project/psycopg/) |
| `pypdf` | ≥ 6.0 | Lectura del PDF de términos | [PyPI](https://pypi.org/project/pypdf/) |
| `reportlab` | ≥ 4.0 | Generación del PDF de términos (extra `scripts`) | [PyPI](https://pypi.org/project/reportlab/) |
| `psutil` | ≥ 7.0 | RAM del equipo para `taller02 proveedores --recomendar` | [PyPI](https://pypi.org/project/psutil/) |

Comprobaciones hechas sobre el código instalado (no sobre la documentación):

- `GoogleGenerativeAIEmbeddings` acepta `output_dimensionality` en el constructor y `task_type` **por
  llamada** en `embed_documents` y `embed_query`. Por eso basta un objeto, envuelto en
  `AsymmetricEmbeddings`, que pasa `RETRIEVAL_DOCUMENT` al indexar y `RETRIEVAL_QUERY` al consultar.
- `OllamaEmbeddings` acepta `dimensions` y lo envía a Ollama; aun así, el envoltorio trunca y
  renormaliza si llega un vector más largo, para que nunca entre a la tabla un vector de otra forma.
- `PGVectorStore.create_sync` usa por defecto `DistanceStrategy.COSINE_DISTANCE` (operador `<=>`).

## Modelos y servicios

| Elemento | Valor | Estado | Fuente / cómo verificarlo |
|---|---|---|---|
| Imagen de pgvector | `pgvector/pgvector:0.8.7-pg17` | ✓ Verificado en Docker Hub el 2026-10-14 (también existen `pg17` y `pg18`) | [Docker Hub](https://hub.docker.com/r/pgvector/pgvector/tags) |
| Claude Haiku 5.5 | `claude-haiku-5-5`, US$0,10 / US$0,50 por millón de tokens (prompts ≤ 100.000 tokens) | ✓ Verificado el 2026-10-14 | [Visión general](https://platform.claude.com/docs/en/models/haiku-5-5/overview) |
| Haiku 5.5: parámetros | `temperature`, `top_p` y `top_k` devuelven 400 → en `omit_params` | ✓ Verificado | [Guía de migración](https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide) |
| Haiku 5.5: pensamiento | Adaptativo y activado por defecto; esfuerzo `medium`. **Los tokens de pensamiento cuentan dentro de `max_tokens`**: con un valor pequeño la respuesta puede quedar vacía | ✓ Verificado → `max_tokens_min = 4000` en el perfil | Guía de migración |
| Haiku 5.5 por la capa compatible con OpenAI | `reasoning_effort` se **ignora**; `thinking` se puede pasar en `extra_body`. No está documentado si `output_config.effort` pasa por esta capa | ⚠ Pendiente en local: probar `params = { output_config = { effort = "low" } }` y comparar la latencia | [Compatibilidad con el SDK de OpenAI](https://platform.claude.com/docs/en/api/openai-sdk) |
| Haiku 5.5: prefill | Rechaza mensajes que terminan en un turno del asistente. Las cadenas del T1 y del T2 siempre terminan en un turno del usuario | ✓ Revisado en el código | Guía de migración |
| Embeddings de Gemini | `gemini-embedding-001`, 768 dimensiones (MRL) | ⚠ Pendiente: `ai.google.dev` no era accesible desde la sesión en la nube. Verificar el ID vigente, si hay uno más nuevo y estable (registrarlo como alternativa, sin cambiarlo) y los límites del nivel gratuito | [Documentación de embeddings](https://ai.google.dev/gemini-api/docs/embeddings) |
| `embeddinggemma:300m` | 768 dimensiones, prefijos `task: search result \| query: ` y `title: none \| text: ` | ⚠ Pendiente: `ollama pull embeddinggemma:300m`. Confirmar que Ollama **no** añade los prefijos y si acepta `dimensions` (MRL) | [Hugging Face](https://huggingface.co/blog/embeddinggemma), [Ollama](https://ollama.com/library/embeddinggemma) |
| `bge-m3` | 1024 dimensiones | ⚠ Pendiente: `ollama pull bge-m3` | [Ollama](https://ollama.com/library/bge-m3) |
| Gemma 4 | `gemma4:e2b`, `gemma4:e4b`, `gemma4:12b`, `gemma4:26b` | ⚠ Pendiente: `ollama show gemma4:e4b` (y las demás etiquetas, al menos que existan) | [Ollama](https://ollama.com/library/gemma4) |
| Ollama, endpoint OpenAI | `http://localhost:11434/v1` | ⚠ Pendiente. Tras una prueba manual real, cambiar `status` del perfil `ollama` a `implementado` | `curl http://localhost:11434/v1/models` |

## Marco legal citado en los documentos sintéticos

Se menciona solo como marco, sin cifras reales. Verificación de primer nivel (búsqueda web,
2026-10-14); antes de la entrega, contrastar con el texto consolidado.

| Norma | Qué se toma | Nota |
|---|---|---|
| Ley 1480 de 2011 (Estatuto del Consumidor) | Garantía legal (art. 7) y derecho de retracto (art. 47) | Ya usada en el Taller 1 |
| Ley 1555 de 2012 | Pago anticipado de créditos sin penalidad | Tiene límites (saldo máximo en SMMLV; no aplica a hipotecarios) |
| Ley 1266 de 2008 | Comunicación previa al titular antes de un reporte negativo | Modificada por la Ley 2157 de 2021 |
| Ley 1581 de 2012 | Tratamiento de datos personales | Términos y condiciones |

## Comandos de verificación en el equipo local

```bash
docker compose up -d && docker compose ps          # pgvector "healthy"
ollama pull embeddinggemma:300m && ollama pull bge-m3 && ollama pull gemma4:e4b
ollama show gemma4:e4b
curl http://localhost:11434/v1/models               # endpoint compatible con OpenAI
uv run taller02 proveedores --recomendar            # resumen de todo lo anterior
```
