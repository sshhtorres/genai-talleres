# Fase 1: Selección de componentes

**Caso:** EcoMarket · generación aumentada por recuperación (RAG) para la atención al cliente

> **Estado del documento: borrador.** Las secciones marcadas con ⏳ se completan con las corridas
> reales de los experimentos E4, E7 y E8, que se guardan en [`outputs/`](../outputs/). Ninguna cifra
> de esas secciones se escribe antes de que exista su archivo de evidencia.

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

> ⏳ **Resultados de E7** (`outputs/E7_<fecha>_gemini.md`): hit@k en los casos translingües, tal cual
> frente a enriquecido, y sesgo de idioma.

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
memoria es la de uno de ≈ 8 B. En la prueba local, `gemma4:e4b` ocupó ≈ 7,1 GiB de RAM residente. Gemma
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

Medido en la verificación local del 2026-10-14 (un equipo solo CPU: Snapdragon X, ARM64, 19 GiB;
una corrida por celda, cronometrada de punta a punta; se reemplaza por los tiempos de E8): indexar la base
tardó 3,3 s con Gemini y 214 s con `embeddinggemma`; `atender` tardó 3,6–4,5 s por pregunta en `nube`,
5,2–15,2 s en `hibrida` y 20–160 s en `local`. **`local` sirve para demostrar que todo corre sin salir
de la máquina, no para uso interactivo en CPU.**

> ⏳ **Resultados de E8** (`outputs/E8_resumen_<fecha>.md`): chequeos, tiempo hasta el primer token,
> latencia total, tokens y costo por respuesta en cada configuración.

## 6. Conclusión

> ⏳ Se redacta con los resultados de E4, E7 y E8.
