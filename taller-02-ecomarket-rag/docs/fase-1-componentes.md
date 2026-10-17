# Fase 1: Selección de componentes

**Caso:** EcoMarket · generación aumentada por recuperación (RAG) para la atención al cliente

> **Estado del documento: versión de entrega.** Todas las cifras salen de las corridas guardadas en
> [`outputs/`](../outputs/); la ronda final de los experimentos de respuesta es del 2026-10-17.

## 0. Criterios y suposiciones

- El Taller 1 eligió el LLM. Este taller elige las dos piezas que el RAG agrega: el **modelo de
  embeddings** y la **base de datos vectorial**, y revisa qué cambia en el LLM cuando el
  conocimiento ya no tiene que estar dentro del modelo.
- Los criterios son los del enunciado y la rúbrica: calidad en **español**, **costo**,
  **escalabilidad** y **ventajas y desventajas**, siempre ligados a EcoMarket: una tienda colombiana
  con miles de consultas diarias, datos de negocio ya relacionales y un catálogo con algunas fichas
  en inglés.
- La calidad de recuperación no se supone a partir de rankings públicos: se **mide** con el set de
  evaluación propio ([`data/eval/casos_rag.jsonl`](../data/eval/casos_rag.jsonl), 42 casos) y
  métricas deterministas (hit@k y MRR).
- Las versiones, IDs de modelo y límites citados se verificaron el 2026-10-14; el detalle, con su
  fuente, está en [`versiones.md`](versiones.md).

## 1. Resumen de decisiones

| Componente | Decisión | Alternativa documentada |
|---|---|---|
| Modelo de embeddings (nube) | `gemini-embedding-001` a **768 dimensiones** | `gemini-embedding-2` (no adoptado: sin `task_type` y espacio incompatible) |
| Modelo de embeddings (local) | `embeddinggemma:300m` a 768 en Ollama | `bge-m3` (1024) para textos de más de ~2.000 tokens |
| Base de datos vectorial | **PostgreSQL + pgvector** (`PGVectorStore`), índice HNSW coseno | Chroma para prototipar; Pinecone o Weaviate en otros escenarios |
| Idiomas | Un solo índice español + inglés, apoyado en la recuperación translingüe | Enriquecer las fichas en inglés con un resumen en español (E7) |
| LLM generador | Gemini (gratuito) o Claude Haiku 5.5 en la nube; Gemma 4 en local | — |
| Configuraciones | `nube`, `hibrida` y `local`, intercambiables con una variable del `.env` | — |

## 2. Modelo de embeddings

### 2.1 Qué hace y por qué importa

Un *embedding* convierte un texto en un vector de *d* números de forma que textos con significado
parecido quedan cerca (similitud coseno alta). La búsqueda del RAG consiste en encontrar los vectores
más cercanos al vector de la pregunta. Tres consecuencias guían la elección:

- **Vectores de modelos distintos no son comparables.** Si se cambia de modelo, hay que reindexar todo.
  Por eso cada perfil tiene su propia tabla (`kb_<perfil>_<dimensiones>`), y no solo cuando cambia la
  dimensión: `gemini-embedding-001` y `embeddinggemma` producen ambos vectores de 768 números y aun
  así son incompatibles.
- **La pregunta y el documento no se parecen en la superficie.** «¿Puedo devolver un champú abierto?»
  y un párrafo de política son textos muy distintos. Los modelos de recuperación distinguen ambos
  papeles: Gemini con `task_type` (`RETRIEVAL_QUERY` / `RETRIEVAL_DOCUMENT`) y EmbeddingGemma con un
  prefijo de texto. Si se omite no hay ningún error; la recuperación simplemente empeora. El código del
  taller aplica siempre la señal correcta (`genai_common.embeddings.AsymmetricEmbeddings`).
- **Un LLM de chat no es un modelo de embeddings.** El script de clase usa `llama2` para las dos cosas:
  funciona técnicamente, pero llama2 no fue entrenado para recuperación y su español es débil.

### 2.2 Comparativa

| Modelo | Tipo | Español | Dim. | Costo | Ventajas | Desventajas |
|---|---|---|---|---|---|---|
| **`gemini-embedding-001`** | Propietario (API) | Muy bueno; más de 100 idiomas; encabezó el ranking multilingüe de MTEB desde su lanzamiento | 3072 (MRL: 768/1536) | Nivel gratuito; US$0,15 por millón de tokens de entrada | Mismo proveedor que ya usa el repositorio; `task_type`; MRL; sin infraestructura | Límites del nivel gratuito; los textos salen a un tercero; dependencia del proveedor |
| `text-embedding-3-small` (OpenAI) | Propietario (API) | Bueno | 1536 | De pago | Muy usado y estable | Otra clave y otro proveedor sin un beneficio claro aquí |
| **`bge-m3`** (BAAI) | Abierto (MIT) | Muy bueno; contexto de 8.192 tokens | 1024 | Gratis (hardware propio) | Corre en Ollama sin GPU para un corpus pequeño; nada sale de la máquina | ~1,2 GB; más lento en CPU; hay que operarlo |
| `multilingual-e5-large-instruct` | Abierto | Muy bueno; el paper de MMTEB lo reporta como el mejor modelo público | 1024 | Gratis | Excelente relación calidad/tamaño | Exige prefijos; menos cómodo vía Ollama |
| `qwen3-embedding` (0,6B–8B) | Abierto | Excelente en las versiones grandes | 32–4096 | Gratis | Estado del arte multilingüe | La versión de 8B necesita GPU |
| `voyage-4` (Voyage AI) | Propietario (API) | Muy bueno | 1024 | De pago | El proveedor que sugiere Anthropic, que no tiene modelo de embeddings propio | Otra cuenta y otra clave |
| **`embeddinggemma:300m`** (Google) | Abierto | Muy bueno para su tamaño; más de 100 idiomas | 768 (MRL) | Gratis (hardware propio) | ~300 M parámetros; corre en equipos modestos; misma familia que el LLM local | Contexto de 2.048 tokens; exige prefijos distintos para pregunta y documento |
| `llama2` (script de clase) | LLM de chat | Débil | 4096 | Gratis | Ya instalado en el ejemplo | No es un modelo de embeddings; 4096 dimensiones superan el límite del índice HNSW de pgvector |

### 2.3 Decisión

Un modelo por configuración: **`gemini-embedding-001` truncado a 768 dimensiones** en la nube y
**`embeddinggemma:300m` a 768** en local. `bge-m3` queda como alternativa local medida (E4).

Por qué, ligado a EcoMarket:

- **Español.** Los tres están entre los mejores modelos multilingües disponibles. La diferencia real se
  mide con los casos de EcoMarket, no con el ranking: experimento E4.
- **Costo.** Indexar toda la base (89 fragmentos, unos 9.500 tokens según
  `outputs/indexacion_<fecha>_gemini.md`) cuesta centavos incluso pagando. En
  operación, 150.000 consultas al mes de unos 30 tokens son ≈ 4,5 millones de tokens: ≈ US$0,70 al mes
  con `gemini-embedding-001`. **El embedding no es el costo que importa**; el que crece es el del LLM,
  porque cada respuesta lleva ahora *k* fragmentos más en el prompt (sección 4).
- **Escalabilidad.** La API escala sin infraestructura; un modelo abierto escala con hardware propio y
  es la salida si el volumen o la privacidad lo exigen. El código permite cambiar de uno a otro con una
  variable del `.env` y un reindexado.
- **768 y no 3072.** El índice HNSW de pgvector admite hasta 2.000 dimensiones con el tipo `vector`.
  768 cabe holgado, ocupa cuatro veces menos y la pérdida por truncar (MRL) es pequeña. Es un ejemplo de
  cómo **la elección de un componente condiciona al otro**.

Dos hallazgos de la verificación local que no estaban en el plan:

- **`gemini-embedding-001` a 768 dimensiones devuelve vectores sin normalizar** (norma ≈ 0,59): su
  documentación lo indica para toda salida distinta de 3072. Con distancia coseno el ranking no cambia,
  pero un producto interno o un umbral sobre el producto punto quedarían mal calibrados. El envoltorio
  del repositorio normaliza siempre.
- **Los prefijos de EmbeddingGemma desplazan las similitudes absolutas.** En un par de prueba, la
  similitud de la pregunta con el documento relevante pasó de 0,68 sin prefijos a 0,50 con ellos, y el
  margen frente al irrelevante subió de 0,34 a 0,37. Un umbral de abstención calibrado con un modelo
  (o sin prefijos) no sirve para otro: por eso hay **un umbral por perfil de embeddings**.

**`embeddinggemma` frente a `bge-m3`.** EmbeddingGemma tiene la mitad de parámetros y una fracción de la
memoria; sus 2.048 tokens de contexto sobran, porque los fragmentos de este diseño rondan los 200
tokens. `bge-m3` conviene con textos de más de ~2.000 tokens (contratos o manuales sin dividir) y por su
recuperación híbrida nativa, que **no está disponible vía Ollama** (solo entrega el vector denso).
Además, `bge-m3` no está entrenado con Matryoshka: Ollama acepta truncarlo sin avisar, pero el perfil lo
fija en 1024.

**Resultados de E4** ([`outputs/E4_2026-10-14.md`](../outputs/E4_2026-10-14.md)). Los 36 casos del
set con fuente esperada, buscados sin filtro y con la estrategia `por_tipo`. Un acierto es un fragmento
del documento esperado que contiene la evidencia literal del caso.

| Modelo | hit@1 | hit@4 | MRR | Políticas (MRR, 15) | Crédito (MRR, 10) | Catálogo (MRR, 6) | Términos (MRR, 5) | Translingüe (hit@1, 4) | s / consulta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `gemini` (768) | **0,833** | **0,972** | **0,892** | 0,922 | **0,808** | 1,0 | **0,84** | 1,0 | 0,319 |
| `embeddinggemma` (768) | 0,778 | 0,889 | 0,833 | 0,900 | 0,733 | 1,0 | 0,629 | 1,0 | 1,687 |
| `bge_m3` (1024) | 0,806 | 0,917 | 0,845 | 0,922 | 0,758 | 1,0 | 0,600 | 1,0 | 0,387 |

Lo que muestran:

- **`gemini` gana en todas las columnas donde hay diferencia**, y las diferencias se concentran en
  crédito y en términos y condiciones. Políticas, catálogo y translingüe quedan casi empatados.
- **Los locales fallan en los mismos casos difíciles** que `gemini` pone en las posiciones 2 a 5:
  `ter-05` (stock del cargador solar), `trampa-01` y `trampa-03` (crédito con el nombre de un producto)
  y los mixtos. En esas preguntas la palabra del producto («cargador solar») atrae su ficha del
  catálogo por encima de la regla general. Con `embeddinggemma` y `bge_m3`, `ter-05` y `trampa-01` ni
  siquiera aparecen entre los 8 primeros.
- **El techo translingüe es real pero poco exigente:** los 4 casos translingües aciertan en primera
  posición con los tres modelos. El set no distingue a los modelos en esa dimensión (ver E7).
- **Latencia y memoria, con cautela.** Es una sola corrida en un equipo de escritorio. La latencia
  de `embeddinggemma` (1,7 s) es más del cuádruple de la de `bge_m3` (0,4 s), un modelo más grande;
  lo más probable es que incluya la carga del modelo en la primera consulta, y no se repitió para
  confirmarlo. La RAM (2,02 GB en ambos) mide todos los procesos de Ollama al terminar, no cada
  modelo por separado: no sirve para compararlos entre sí.

**Decisión:** `gemini` para la configuración nube, que es la principal; `embeddinggemma` para las
configuraciones híbrida y local, por tamaño y por los prefijos de tarea que ya se manejan.
`embeddinggemma` pierde 0,06 de MRR frente a `gemini` y queda cerca de `bge_m3`, que ocupa más del
doble y no aporta su búsqueda híbrida a través de Ollama.

### 2.4 Español e inglés en el mismo índice

Algunos vendedores suben las fichas en inglés: 4 de los 15 productos del catálogo. Un modelo
multilingüe, entrenado con pares de traducción y pares pregunta–respuesta entre idiomas, proyecta ambos
idiomas en un **espacio vectorial compartido**: «cepillo de bambú» y «bamboo toothbrush» quedan cerca.
Por eso no hace falta un índice por idioma ni traducir la pregunta. Lo que no es perfecto, y para lo
que se diseñó:

1. **Sesgo hacia el mismo idioma.** Con significado equivalente, un fragmento en el idioma de la pregunta
   puntúa algo más alto. Se mide en E7 como la similitud media del acierto ES→ES frente a ES→EN.
2. **El umbral cambia.** Se esperaba que las similitudes translingües fueran en promedio más bajas; por
   eso la calibración separa los casos translingües y no acepta un umbral que los deje sin respuesta.
   (Con los 4 casos del set no se observó: ver la calibración en la Fase 3.)
3. **La búsqueda por palabras clave no es translingüe.** Si se añadiera búsqueda híbrida, el `tsvector`
   con configuración `spanish` estropearía el texto en inglés.
4. **La respuesta sale en el idioma del cliente**, traduciendo el fragmento sin traducir nombres de
   producto ni marcas, y citando la fuente original.

| Opción | Cómo | Ventaja | Desventaja | Decisión |
|---|---|---|---|---|
| A. Indexar tal cual | Texto original + metadato `idioma` | Simple; una sola fuente de verdad | Sesgo de idioma | **Base** |
| B. Enriquecer al indexar | Resumen en español generado una vez y antepuesto | Mejora el emparejamiento ES→EN | Costo de generación; riesgo de errores de traducción | **Experimento E7** |
| C. Traducir la pregunta | Buscar con la pregunta y su traducción | No toca el índice | Una llamada extra al LLM en cada consulta | Descartada |

**Resultados de E7** ([`outputs/E7_2026-10-17_gemini.md`](../outputs/E7_2026-10-17_gemini.md)), con
`gemini` y la estrategia `por_tipo`. Los resúmenes son la tercera versión del prompt de
enriquecimiento (con las cifras, la nota de devolución y español de Colombia):

| Variante | hit@1 global | MRR global | Translingüe (hit@1, 4 casos) | Catálogo (hit@1, 6) | Similitud ES → ficha ES (4) | Similitud ES → ficha EN (2) |
|---|---:|---:|---:|---:|---:|---:|
| Tal cual (A) | 0,833 | 0,892 | 1,0 | 1,0 | 0,7229 | 0,7121 |
| Enriquecida (B) | 0,861 | 0,906 | 1,0 | 1,0 | 0,7229 | 0,7253 |

- **El sesgo de idioma existe, pero es pequeño:** sin enriquecer, una pregunta en español se parece
  0,011 menos a su ficha en inglés que a una ficha en español. Con el resumen, la diferencia
  desaparece (0,7253 frente a 0,7229).
- **No cambia ningún acierto translingüe:** los 4 casos ya salían primeros sin enriquecer. El set no
  alcanza a mostrar el beneficio: harían falta preguntas en español cuya ficha en inglés compita con
  fichas en español parecidas.
- **El único cambio de posición es indirecto.** En `mixto-01` («…¿cuánto tiempo tengo para devolver
  la botella térmica?»), la ficha de la botella (en inglés) salía primero y la política de
  devoluciones segunda. Con el resumen, la política pasa al primer lugar. De ahí la subida global
  (0,833 → 0,861): es un solo caso.
- **El costo y el riesgo se vieron.** Generar los 4 resúmenes tomó unos 6 s, una sola vez. La primera
  versión del prompt omitía cifras (24 h / 12 h de la botella, la garantía del cargador); la segunda,
  la nota de devolución de tres fichas, y usaba «coche». Hubo que corregir el prompt dos veces. La versión final conserva las
  cifras sin inventar hechos, pero omite las certificaciones de P-101 y trae una errata
  («siliciona» en P-106).

**Decisión:** indexar **tal cual** (opción A) como base. El enriquecimiento no mejora la recuperación
translingüe medible en este set y agrega una pieza generada por un LLM que hay que revisar a mano.
Queda como opción para un catálogo con más fichas en inglés.

## 3. Base de datos vectorial

### 3.1 Qué hace

Buscar el vecino más cercano exacto obliga a comparar contra todos los vectores. Los índices **ANN**
como **HNSW** construyen un grafo navegable y responden en milisegundos a cambio de una pequeña pérdida
de *recall*. Además de vectores, la base guarda **metadatos** para **filtrar** («solo las reglas de
crédito») y para **citar la fuente**.

### 3.2 Comparativa

| | **pgvector (Postgres)** | Chroma | Pinecone | Weaviate |
|---|---|---|---|---|
| Modelo | Extensión de Postgres; autoalojado o gestionado | Embebida o cliente-servidor | SaaS gestionado | Abierto autoalojado o nube |
| Costo | Gratis (Docker); en la nube, el de un Postgres que la empresa probablemente ya paga | Gratis local | Plan gratuito limitado; plan de pago desde US$20/mes | Gratis autoalojado; nube desde ≈ US$45/mes |
| Escalabilidad | Muy buena hasta millones de vectores con HNSW | Prototipos y cargas moderadas | La más alta sin esfuerzo operativo | Alta; multi-tenant |
| Filtros por metadatos | SQL completo | Básicos | Buenos | Buenos |
| Búsqueda híbrida | Sí (`tsvector` + fusión) | Limitada | Con vectores *sparse* | Nativa, la más madura |
| Dependencia de proveedor | Ninguna | Ninguna | Alta | Baja |
| Riesgo principal | Hay que operarlo | No pensada para alta concurrencia | Costo y datos fuera de casa | Complejidad para un equipo pequeño |

### 3.3 Decisión: PostgreSQL + pgvector

1. **Los datos de EcoMarket ya son relacionales** (pedidos, productos, devoluciones): vectores y datos de
   negocio pueden vivir en el mismo motor, con filtros SQL y sin sincronizar dos sistemas.
2. **Escala con holgura**: la base tiene cientos de fragmentos; aun creciendo cien veces, sigue dentro de
   lo que HNSW en Postgres resuelve en milisegundos.
3. **Costo marginal casi nulo** y sin dependencia de un proveedor.
4. **Reproducible**: `docker compose up -d` (imagen `pgvector/pgvector:0.8.7-pg17`, verificada también
   en ARM64) y las pruebas usan un almacén en memoria.

**Desventajas.** Hay que operar la base (copias de seguridad, versiones); con cientos de millones de
vectores o latencias muy exigentes, Pinecone o Weaviate rinden mejor con menos esfuerzo. **Cuándo
cambiaría:** si EcoMarket no tuviera Postgres ni equipo para operarlo (Pinecone) o si la búsqueda
híbrida avanzada fuera central (Weaviate). Chroma queda como la opción para prototipar, que es el papel
que tiene en el script de clase.

**Índice y distancia.** HNSW, porque da mejor *recall* que IVFFlat y no necesita reentrenarse al crecer
los datos. Distancia coseno, que es lo que asumen los modelos de embeddings. `PGVectorStore` devuelve la
**distancia** (0 = idéntico) y el almacén en memoria la **similitud** (1 = idéntico); el código convierte
ambas a similitud en [0, 1], y una prueba de integración comprueba que pgvector y memoria devuelven los
mismos fragmentos con los mismos *scores*.

## 4. Cómo cada componente impacta la eficacia del RAG

| Componente | Si falla… | Síntoma | Cómo se detecta |
|---|---|---|---|
| Embedding | La pregunta y el fragmento correcto quedan lejos | «No tengo información» cuando sí la hay, o la sección equivocada | hit@k bajo (E4) |
| Chunking | El dato queda partido o diluido | Respuestas incompletas o genéricas | hit@k por tipo de documento (E2) |
| Base vectorial / índice | *Recall* bajo, filtros mal puestos | Resultados inestables | Prueba pgvector frente a búsqueda exacta en memoria |
| *k* | Pocos: falta contexto; muchos: ruido y costo | Mezcla de políticas, prompts largos | E3 |
| Prompt | El LLM ignora el contexto o inventa | Alucinaciones, citas inválidas | Chequeos de citas y abstención (E1) |
| Umbral de similitud | Muy bajo: responde sin evidencia; muy alto: se abstiene de más | Falsos positivos o negativos de abstención | Calibración con casos dentro y fuera de alcance |

**El costo que sí sube.** Con *k* = 4 fragmentos de unos 200 tokens, cada respuesta lleva ≈ 800 tokens
más de entrada. A 150.000 consultas al mes son ≈ 120 millones de tokens adicionales. Es el argumento
para mantener *k* pequeño (E3 lo mide) y no meter documentos completos en el prompt.

## 5. El modelo generador, en la nube y en local

El RAG cambia lo que se le pide al LLM: ya no necesita «saber» de EcoMarket, solo **leer bien el
contexto y obedecer las reglas**. Eso favorece modelos pequeños y baratos.

**Claude Haiku 5.5 en la nube** (verificado en la documentación de Anthropic el 2026-10-14):

| Dato | Valor | Implicación |
|---|---|---|
| ID | `claude-haiku-5-5` | Rol `router` del perfil `anthropic`; generación en la configuración `hibrida` |
| Precio | US$0,10 / US$0,50 por millón de tokens de entrada / salida (prompts ≤ 100.000 tokens) | Base del costo estimado en E8 |
| Parámetros | Rechaza `temperature`, `top_p` y `top_k` | Se omiten desde `providers.toml` |
| Razonamiento | Adaptativo y activado por defecto; esos tokens cuentan dentro de `max_tokens` | Mínimo de 4.000 tokens en el perfil: con 600, una respuesta del Taller 1 salió cortada |
| Integración | Por la capa compatible con OpenAI el razonamiento adaptativo da error 400 | El Taller 2 usa `ChatAnthropic`, la integración nativa de LangChain |
| Embeddings | Anthropic no ofrece modelo de embeddings | Embedding y LLM pueden ser de proveedores distintos |

**Gemma 4 en local.** Cuatro etiquetas verificadas en el registro de Ollama, cada una para un nivel de
hardware explícito (la RAM se detecta, la VRAM y el ancho de banda de memoria no):

| Nivel (`LOCAL_TIER`) | Máquina | LLM | Descarga |
|---|---|---|---:|
| `cpu-8gb` | Solo CPU, 8 GB | `gemma4:e2b` | 4,59 GB |
| `cpu-16gb` | Solo CPU, 16 GB o más | `gemma4:e4b` | 6,58 GB |
| `gpu-12gb` | GPU con ~12 GB | `gemma4:12b` | 8,02 GB |
| `gpu-24gb` | GPU con 24 GB | `gemma4:26b` | 18,73 GB |

La «E» de E2B y E4B significa *effective*: el cómputo por token es el de un modelo de 4,5 B, pero la
memoria es la de uno de ≈ 8 B. En la prueba local del 2026-10-14, `gemma4:e4b` ocupó ≈ 7,1 GiB de RAM residente; el 2026-10-17,
`ollama ps` reportó 1,9 GB cargados en otra máquina. Las dos mediciones no son comparables (la
primera es la memoria residente del proceso; la segunda, lo que Ollama declara), y no se resolvió
cuál refleja mejor el consumo real. Gemma
4 **piensa por defecto**: sin desactivarlo, una respuesta de una frase tardó entre 36 y 89 s y, con un
`max_tokens` bajo, salió vacía; el perfil `ollama` lo desactiva.

**Tres configuraciones.** Embedding y LLM son piezas independientes; lo único que debe coincidir es el
modelo con que se indexó y el que se usa al consultar.

| | `nube` | `hibrida` | `local` |
|---|---|---|---|
| Embeddings | `gemini-embedding-001` | `embeddinggemma:300m` (Ollama) | `embeddinggemma:300m` (Ollama) |
| LLM | Gemini | Gemini o Claude Haiku 5.5 | Gemma 4 según el nivel |
| Qué sale de la máquina | Documentos al indexar; pregunta y fragmentos en cada consulta | **Solo** la pregunta y los *k* fragmentos de cada consulta | Nada |
| Limitación principal | Cuotas del nivel gratuito | Latencia de dos sistemas | Velocidad en CPU |

La configuración `hibrida` **no hace privado el sistema**: la pregunta y los fragmentos siguen viajando
al LLM en la nube. Lo que gana es que el corpus completo nunca sale y que reindexar no consume cuota.

**`local` sirve para demostrar que todo corre sin salir de la máquina, no para uso interactivo en CPU**:
los tiempos medidos están en E8, abajo.

**Resultados de E8** ([`outputs/E8_resumen_2026-10-17.md`](../outputs/E8_resumen_2026-10-17.md)). Diez
casos, uno de cada tipo por turno (dentro de alcance, fuera, inyección, reformulación, translingüe y
trampa de crédito). Uno de ellos (`fuera-03`) se abstiene desde código en las cuatro configuraciones,
así que tiempos, tokens y costo son medias sobre las **9 respuestas que llamaron al LLM**. Los tiempos
miden solo la llamada al LLM, con *streaming*, sin la recuperación. Equipo: AMD Ryzen 9 9950X, 23 GiB
visibles en WSL2, **sin GPU** (Ollama al 100% en CPU).

| Configuración | Embeddings + LLM | Chequeos OK | TTFT (s) | Latencia (s) | Tokens entrada | Tokens salida | US$ por respuesta | US$ por 1.000 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `nube` | `gemini-embedding-001` + `gemini-3.5-flash-lite` | 10/10 | 0,77 | 0,94 | 1.829 | 70 | 0,000723* | 0,72* |
| `hibrida:gemini` | `embeddinggemma` + `gemini-3.5-flash-lite` | 10/10 | 0,90 | 1,09 | 1.863 | 81 | 0,000762* | 0,76* |
| `hibrida:anthropic` | `embeddinggemma` + `claude-haiku-5-5` | 10/10 | 1,20 | 1,85 | 3.184 | 315 | 0,000476 | 0,48 |
| `local` | `embeddinggemma` + `gemma4:e4b` | 8/10 | 8,11 | 10,66 | 1.908 | 70 | 0 (local) | 0 |

\* Gemini se usó en el nivel gratuito, con costo real 0. La cifra es el equivalente en el nivel
pagado (US$0,30 / US$2,50 por millón de tokens), tomada de agregadores de precios que citan la
página oficial; no se pudo verificar en la página de Google.

- **Las tres configuraciones con LLM en la nube aciertan los 10 casos.** La diferencia está en
  tiempo y costo, no en calidad, al menos con 10 casos.
- **Haiku es más lento y usa más tokens, pero sale más barato.** Recibe unos 1.300 tokens de entrada
  más que Gemini con los mismos fragmentos (probablemente porque su tokenizador cuenta distinto) y produce 315 de salida
  frente a 70. La diferencia probablemente es su razonamiento adaptativo, que se factura como salida;
  aun así, con un precio 3 a 5 veces menor, cuesta un tercio menos por respuesta.
- **`nube` e `hibrida:gemini` usan el mismo LLM:** su diferencia de tiempo (0,77 frente a 0,90 s)
  no viene de los embeddings, que no se cronometran aquí. Es variación entre llamadas a la API.
- **`local` funciona, pero es unas 10 veces más lento y falla dos casos.** En `iny-01` (una
  inyección que pide afirmar 90 días) Gemma se abstuvo en vez de dar los 30 días, aunque tenía el
  fragmento correcto. En `reform-01` omitió la regla general de devolución. Ninguno de los dos fallos
  es de seguridad: no repitió la cifra inyectada ni inventó nada.
- **La latencia local depende de la máquina.** El 2026-10-15, en el equipo ARM64 (Snapdragon X,
  19 GiB, solo CPU), la misma configuración `local` tardó 32,1 s hasta el primer token y 37,8 s en
  total, frente a 8,1 y 10,7 s aquí. La configuración no cambió; cambió la CPU.

## 6. Conclusión

Las dos piezas que el RAG agrega se eligieron por medición, no por ranking público:

1. **Embeddings: `gemini-embedding-001` a 768 dimensiones en la nube** y `embeddinggemma:300m` en
   local. En E4, `gemini` obtuvo el mejor MRR (0,892, frente a 0,845 de `bge_m3` y 0,833 de
   `embeddinggemma`), con la diferencia concentrada en crédito y términos. Los tres modelos
   recuperan bien en español e inglés: los 4 casos translingües salen primeros con todos. Este set
   no alcanza para separarlos en esa dimensión.
2. **Base vectorial: PostgreSQL + pgvector.** EcoMarket ya tiene sus datos en un modelo relacional.
   pgvector agrega la búsqueda semántica sin otro servicio, con filtros por metadatos (tipo, área,
   idioma) en la misma consulta y un índice HNSW coseno. A esta escala (89 fragmentos, y miles con un
   catálogo real) no hace falta una base vectorial dedicada.
3. **Un solo índice bilingüe, sin enriquecer.** E7 midió un sesgo de idioma pequeño (0,011 de
   similitud), que el resumen en español elimina sin cambiar ningún acierto translingüe. El costo, en
   cambio, se vio: dos correcciones del prompt para que los resúmenes no perdieran cifras ni
   condiciones.
4. **El LLM se vuelve intercambiable.** Con el conocimiento en los documentos, el generador solo tiene
   que leer bien y obedecer reglas. En E8, Gemini y Haiku aciertan los 10 casos, en 0,9 y 1,8 s
   respectivamente. Haiku cuesta un tercio menos por respuesta que el equivalente pagado de Gemini.
   Gemma 4 en CPU acierta 8 de 10 en unos 10 s: sirve para demostrar que todo corre sin salir de la
   máquina, no para atender clientes.

La configuración recomendada para EcoMarket es **`nube`**, con el nivel gratuito de Gemini para el
piloto. La configuración `hibrida` con Haiku es la alternativa si se quiere que el corpus completo no
salga de la empresa, sabiendo que cada pregunta y sus fragmentos sí viajan al proveedor del LLM.
