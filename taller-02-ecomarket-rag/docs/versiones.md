# Versiones y verificación de APIs (H0)

LangChain, los IDs de modelo y las etiquetas de imágenes cambian rápido. Este documento registra
**qué se verificó, cuándo y contra qué fuente**. Lo que no se pudo verificar queda marcado como
pendiente, con el comando que lo verifica: no se supone.

## Entornos de verificación

| Entorno | Qué tenía | Qué no tenía |
|---|---|---|
| Sesión en la nube (2026-10-14) | PyPI, Docker Hub, documentación de Anthropic, Postgres 16 + pgvector 0.6.0 instalado con `apt` como sustituto del contenedor | Demonio de Docker, Ollama (su registro está bloqueado), claves de API, acceso a `ai.google.dev` y `ollama.com` |
| Equipo local, 1.ª tanda (2026-10-14) | WSL2 sobre Windows ARM64 (Snapdragon X, 6 núcleos, 11 GiB visibles, sin GPU), Docker 29.7.1, claves de Gemini y Anthropic | Ollama |
| Equipo local, 2.ª tanda (2026-10-14) | Lo mismo con 19 GiB visibles y Ollama 0.40.4 (`systemd`) | — |

## Paquetes de Python fijados

Versiones vigentes en PyPI el 2026-10-14. Se fijan con `==` los paquetes de LangChain porque sus
APIs cambian entre versiones menores; `langchain-postgres` sigue en 0.0.x.

| Paquete | Versión | Uso | Fuente |
|---|---|---|---|
| `langchain-core` | 1.6.10 | `Embeddings`, `Document`, LCEL, `InMemoryVectorStore`, modelos falsos | [PyPI](https://pypi.org/project/langchain-core/) |
| `langchain-classic` | 1.0.8 | `CacheBackedEmbeddings` + `LocalFileStore` (en LangChain 1.x ya no están en `langchain`) y `RetrievalQA` del script de clase | [PyPI](https://pypi.org/project/langchain-classic/) |
| `langchain-text-splitters` | 1.1.3 | `RecursiveCharacterTextSplitter`, `MarkdownHeaderTextSplitter` | [PyPI](https://pypi.org/project/langchain-text-splitters/) |
| `langchain-postgres` | 0.0.19 | `PGEngine` + `PGVectorStore` (no la clase `PGVector`, obsoleta) | [PyPI](https://pypi.org/project/langchain-postgres/), [docs](https://docs.langchain.com/oss/python/integrations/vectorstores/pgvectorstore) |
| `langchain-google-genai` | 4.4.2 | `GoogleGenerativeAIEmbeddings` y `ChatGoogleGenerativeAI` | [PyPI](https://pypi.org/project/langchain-google-genai/) |
| `langchain-anthropic` | 1.7.6 | `ChatAnthropic`: Claude Haiku 5.5 con su integración nativa (controla el pensamiento adaptativo y el esfuerzo, que la capa compatible con OpenAI no permite) | [PyPI](https://pypi.org/project/langchain-anthropic/) |
| `langchain-ollama` | 1.1.0 | `OllamaEmbeddings` y `ChatOllama` (`reasoning=False` desactiva el pensamiento de Gemma 4) | [PyPI](https://pypi.org/project/langchain-ollama/) |
| `langchain-chroma` | 1.1.0 | Solo el script de clase modernizado. **No es dependencia del taller**: se usa con `uv run --with`, porque arrastra `chromadb` completo (con `onnxruntime` y `kubernetes`) | [PyPI](https://pypi.org/project/langchain-chroma/) |
| `psycopg[binary]` | ≥ 3.2 | Driver de Postgres de `langchain-postgres` y comprobaciones | [PyPI](https://pypi.org/project/psycopg/) |
| `pypdf` | ≥ 6.0 | Lectura del PDF de términos | [PyPI](https://pypi.org/project/pypdf/) |
| `reportlab` | ≥ 4.0 | Regenerar el PDF de términos. Tampoco es dependencia: `uv run --with "reportlab>=4.0"` | [PyPI](https://pypi.org/project/reportlab/) |
| `psutil` | ≥ 7.0 | RAM del equipo para `taller02 proveedores --recomendar` | [PyPI](https://pypi.org/project/psutil/) |

**Integraciones nativas de LangChain para el chat (Taller 2).** Las cadenas LCEL construyen el
modelo de chat con la integración nativa de cada proveedor (`genai_common.lc`), elegida por la
sección `[providers.<nombre>.langchain]` de providers.toml. `langchain-openai` dejó de ser
dependencia. El Taller 1 no cambia: `LLMClient` sigue usando el endpoint compatible con OpenAI
(`base_url`), y así sus corridas guardadas siguen siendo reproducibles. Motivo del cambio, medido en
la verificación local: por la capa compatible de Anthropic, `thinking` adaptativo da 400 y
`reasoning_effort` se ignora; `ChatAnthropic` expone `thinking`, `output_config` y `reasoning_effort`.

⚠ Pendiente en local: una llamada real con cada integración nativa (`taller02 preguntar` con
`--proveedor gemini`, `anthropic` y `ollama`), porque la sesión en la nube no tiene claves ni Ollama.

Comprobaciones hechas sobre el código instalado (no sobre la documentación):

- `GoogleGenerativeAIEmbeddings` acepta `output_dimensionality` en el constructor y `task_type` **por
  llamada** en `embed_documents` y `embed_query`. Por eso basta un objeto, envuelto en
  `AsymmetricEmbeddings`, que pasa `RETRIEVAL_DOCUMENT` al indexar y `RETRIEVAL_QUERY` al consultar.
- `OllamaEmbeddings` acepta `dimensions` y lo envía a Ollama; aun así, el envoltorio trunca si llega
  un vector más largo, para que nunca entre a la tabla un vector de otra forma.
- **El envoltorio normaliza siempre a norma 1.** En la prueba local, `gemini-embedding-001` a 768
  devolvió vectores con norma ≈ 0,59: la documentación de Gemini indica que con `-001` hay que
  normalizar a mano toda salida distinta de 3072. Con distancia coseno el ranking no cambia, pero un
  producto interno o un umbral sobre el producto punto quedarían mal calibrados.
- `PGVectorStore.create_sync` usa por defecto `DistanceStrategy.COSINE_DISTANCE` (operador `<=>`).

## Modelos y servicios

| Elemento | Valor | Estado | Fuente / cómo verificarlo |
|---|---|---|---|
| Imagen de pgvector | `pgvector/pgvector:0.8.7-pg17` | ✓ Verificado en Docker Hub y en local: existe para `linux/arm64`, arranca `healthy` en menos de 10 s con la extensión 0.8.7 | [Docker Hub](https://hub.docker.com/r/pgvector/pgvector/tags) |
| Claude Haiku 5.5 | `claude-haiku-5-5`, US$0,10 / US$0,50 por millón de tokens (prompts ≤ 100.000 tokens) | ✓ Verificado el 2026-10-14 | [Visión general](https://platform.claude.com/docs/en/models/haiku-5-5/overview) |
| Haiku 5.5: parámetros | `temperature`, `top_p` y `top_k` devuelven 400 → en `omit_params` | ✓ Verificado | [Guía de migración](https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide) |
| Haiku 5.5: pensamiento | Adaptativo y activado por defecto; esfuerzo `medium`. Según la documentación, los tokens de pensamiento cuentan dentro de `max_tokens` | ✓ Documentado. En local, con `max_tokens=50` **no** salió vacía (respondió una palabra), pero la clasificación cambió frente a `max_tokens=4000`. Se mantiene `max_tokens_min = 4000` por precaución | Guía de migración; prueba local |
| Haiku 5.5 por la capa compatible con OpenAI | `reasoning_effort` se ignora. `thinking: {"type": "adaptive"}` en `extra_body` → **400** («Adaptive thinking is not available via the OpenAI compatibility endpoint»). `output_config.effort = "low"` en `extra_body` → aceptado, sin ahorro medible (186 frente a 138 tokens de salida, una muestra). Como argumento directo (`params`), el SDK de OpenAI lo rechaza con `TypeError` antes de enviar | ✓ Verificado en local. Los perfiles admiten ahora `extra_body` para parámetros propios del proveedor; no se activa `effort` sin más evidencia | [Compatibilidad con el SDK de OpenAI](https://platform.claude.com/docs/en/api/openai-sdk); prueba local |
| Haiku 5.5: prefill | Rechaza mensajes que terminan en un turno del asistente. Las cadenas del T1 y del T2 siempre terminan en un turno del usuario | ✓ Revisado en el código | Guía de migración |
| Embeddings de Gemini | `gemini-embedding-001`, 768 dimensiones (MRL) | ✓ Verificado en local: estable, sin aviso de obsolescencia; 768/768 por el código del repo; vectores sin normalizar (ver arriba) | [Documentación de embeddings](https://ai.google.dev/gemini-api/docs/embeddings) |
| Alternativa registrada | `gemini-embedding-2` (estable) y `gemini-embedding-2-preview` | Disponibles para la clave. **No se adopta**: no admite `task_type` (usa los prefijos de EmbeddingGemma), su espacio vectorial es incompatible con el de `-001` y el envoltorio actual tendría que usar prefijos en vez de `task_type` | Documentación de embeddings |
| Límites del nivel gratuito de embeddings | — | ⚠ No publicados en la página de límites («can be viewed in Google AI Studio»): consultarlos en AI Studio con la sesión del usuario | [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) |
| `embeddinggemma:300m` | 768 dimensiones, prefijos `task: search result \| query: ` y `title: none \| text: ` | ✓ Verificado en local: 621 MB, 307,58 M parámetros, contexto 2048. Plantilla `{{ .Prompt }}`: **Ollama no añade los prefijos** (el envoltorio del repo sí). Acepta `dimensions` 768 y 256 y devuelve vectores normalizados. Los prefijos desplazan las similitudes absolutas (0,68 → 0,50 en un par de prueba): el umbral se calibra por perfil | [Hugging Face](https://huggingface.co/blog/embeddinggemma), prueba local |
| `bge-m3` | 1024 dimensiones | ✓ Verificado en local: 1,2 GB, vectores de 1024 normalizados. Acepta en silencio `dimensions: 256` y trunca, aunque **no está entrenado con MRL**: el perfil fija 1024 | Prueba local |
| Gemma 4 | `gemma4:e2b` 4,59 GB · `gemma4:e4b` 6,58 GB · `gemma4:12b` 8,02 GB · `gemma4:26b` 18,73 GB (`27b` no existe) | ✓ Las cuatro existen (manifiestos del registro); `e4b` descargada: 7,5 B, Q4_K_M, contexto 131.072. **Piensa por defecto** (`thinking default true`). RAM residente en CPU: ≈ 7,1 GiB (más ≈ 0,7 GiB de `embeddinggemma`) | `ollama show gemma4:e4b`, prueba local |
| Ollama, endpoint OpenAI | `http://localhost:11434/v1` | ✓ Responde. Sin parámetros, `gemma4:e4b` tardó 89 s en frío y 36 s en caliente por pensar, y con `max_tokens=200` devolvió texto vacío. Con `reasoning_effort: "none"`: 4–7 s y ≈ 30 tokens, por las dos fábricas del repo. `"think": false` se ignora en `/v1`. → perfil `ollama` en `implementado` con `params = { reasoning_effort = "none" }` | Prueba local |

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
ollama show gemma4:e4b                              # "thinking ... default true"
curl http://localhost:11434/v1/models               # endpoint compatible con OpenAI
uv run taller02 proveedores --recomendar            # resumen de todo lo anterior
```
