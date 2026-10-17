# Fase 2: Base de conocimiento

**Caso:** EcoMarket · generación aumentada por recuperación (RAG) para la atención al cliente

> **Estado del documento: versión de entrega.** Todas las cifras salen de las corridas guardadas en
> [`outputs/`](../outputs/); la ronda final de los experimentos de respuesta es del 2026-10-17.

## 0. Criterios y suposiciones

- EcoMarket es ficticia: todos los documentos son **sintéticos**, sin datos de personas, y coherentes
  con el Taller 1 (los mismos 15 productos y categorías, la misma política de devoluciones basada en la
  Ley 1480 de 2011). Esa coherencia no se confía a la vista: la comprueban las pruebas de
  [`tests/test_kb.py`](../tests/test_kb.py).
- La regla para decidir qué entra al RAG: **conocimiento estable y público** de la empresa. Los hechos
  **transaccionales o personales** se consultan con herramientas exactas.
- El chunking no se elige por intuición: el experimento E2 compara la estrategia elegida contra dos
  líneas base de tamaño fijo, con métricas que no dependen de ningún LLM.

## 1. Qué entra al RAG y qué no

| Información | ¿Se indexa? | Por qué |
|---|---|---|
| Políticas, preguntas frecuentes, reglas de financiación, fichas de producto, términos | **Sí** | Conocimiento estable y público: lo que el asistente debe explicar |
| **Pedidos** | **No** | El hallazgo principal del Taller 1 fue que el prompt básico filtraba datos de otros clientes. En una base vectorial, una pregunta parecida podría recuperar el pedido de otra persona. Se siguen consultando por número de seguimiento, desde código |
| **Datos de crédito de cada cliente** (cupo, saldo, cuotas, mora) | **No** | Son personales y financieros. Al RAG solo van las reglas generales; el asistente remite a la sección «Mis créditos» |
| **Precio y stock** | **No** | Cambian a diario y una cifra vieja es peor que ninguna. El catálogo se indexa por su parte descriptiva; el set de evaluación incluye un caso de precio que exige abstenerse y uno de stock que admite explicar la regla general («la disponibilidad cambia a diario») o abstenerse remitiendo a una persona, pero nunca afirmar que hay unidades |

## 2. Inventario: cuatro tipos de documento en cuatro formatos

| # | Documento | Formato | Para qué preguntas | Chunking | Metadatos clave |
|---|---|---|---|---|---|
| 1 | [Políticas y preguntas frecuentes](../data/kb/politicas-y-faq.md): devoluciones y garantías, envíos, pagos y cuenta, sostenibilidad; 24 preguntas frecuentes | Markdown con *front matter* | Plazos, excepciones, envíos, medios de pago, cupones, empaques, reciclaje de envases | Estructural (por encabezados) | `tipo`, `area`, `seccion`, `es_faq`, `version`, `vigente_desde` |
| 2 | [Reglas de crédito](../data/kb/reglas-credito.json): 18 reglas de la financiación en cuotas | JSON | Requisitos, cuotas, intereses, pago anticipado, mora, aviso previo | Un fragmento por regla | `tipo`, `id_regla`, `tema`, `vigente_desde` |
| 3 | [Catálogo](../data/kb/catalogo.csv): los 15 productos con descripción, materiales, uso, cuidados, certificaciones y condición de devolución; **4 fichas en inglés** | CSV | Uso, materiales, cuidados, compatibilidad | Un fragmento por producto | `tipo`, `sku`, `categoria`, `retornable`, `idioma` |
| 4 | [Términos y condiciones](../data/kb/terminos-y-condiciones.pdf): precios, medios de pago, facturación electrónica, datos personales (Ley 1581 de 2012), responsabilidad | PDF | Facturación, tratamiento de datos, responsabilidad, PQR | Recursivo | `tipo`, `pagina` |

Cuatro formatos exigen cuatro *loaders* distintos, que es justo lo que el enunciado sugiere (PDF, hoja
de cálculo, JSON). El detalle de cómo se redactó cada documento está en
[`data/README.md`](../data/README.md).

**Por qué unificar políticas y preguntas frecuentes.** Las preguntas frecuentes casi siempre repiten
una política con otras palabras. Separadas, se desincronizan: la política dice 30 días y la pregunta
frecuente desactualizada dice 15, y el RAG recupera las dos. Unificadas hay **una sola fuente de
verdad**, y cada pregunta hereda la ruta de su área («Devoluciones y garantías › Preguntas frecuentes ›
¿Puedo devolver un producto que ya abrí?»), lo que ayuda al embedding y a la cita. El costo: el
documento es largo y depende de que los encabezados estén bien puestos. Por eso los filtros son por
`area` (la ruta de devolución filtra `area=devoluciones`) y no por documento.

**Por qué las reglas de crédito son delicadas.** Es donde un RAG mal planteado hace más daño:

- **El LLM no aprueba crédito ni calcula cuotas.** Igual que `evaluar_devolucion()` en el Taller 1,
  toda decisión o cálculo es de un sistema determinístico. El RAG solo explica las reglas y remite al
  simulador o a un asesor.
- **Los números son el punto débil de los embeddings.** «Compras desde 200.000 pesos» y «desde
  2.000.000» tienen vectores casi iguales. Por eso cada regla es un fragmento autocontenido con su tema,
  y un chequeo exige que toda cifra de una respuesta de crédito aparezca literal en los fragmentos
  recuperados.
- **Información regulada.** Las reglas se apoyan en el marco colombiano sin cifras reales: interés
  nunca superior a la tasa de usura vigente, pago anticipado sin penalidad (Ley 1555 de 2012) y aviso
  previo antes de reportar a centrales de riesgo (Ley 1266 de 2008, modificada por la Ley 2157 de 2021).

**Por qué el catálogo es un fragmento por producto.** Un CSV no tiene párrafos: un *splitter* recursivo
podría dejar media fila de un producto y media del siguiente en el mismo fragmento. Cada fila se
serializa como una ficha de texto («Producto: … Categoría: … Retornable: …»), con las etiquetas en el
idioma de la ficha, como la subiría el vendedor.

## 3. Estrategias de chunking

El fragmento (*chunk*) es la **unidad de recuperación**: el retriever devuelve fragmentos completos, no
frases. La tensión de fondo: un fragmento pequeño da un embedding preciso pero poco contexto; uno grande
da contexto completo pero un embedding «promediado» entre varios temas y más tokens en el prompt.

| Estrategia | Cómo divide | Ventaja | Desventaja | Uso en EcoMarket |
|---|---|---|---|---|
| Tamaño fijo | Cada N caracteres | Simple, predecible | Corta frases y reglas a la mitad | Solo como **línea base** de E2 (`fija300`, `fija1000`) |
| Recursivo | Separadores en orden (`\n## `, `\n### `, `\n\n`, `\n`, `. `, ` `) hasta cumplir el tamaño | Respeta la estructura si existe y garantiza un tamaño máximo | Hay que elegir tamaño y solapamiento | PDF de términos; respaldo de secciones largas |
| **Estructural** | Por encabezados; el título viaja con el texto | Cada fragmento es una regla o una pregunta completa; permite citar la sección | Solo sirve si el documento está bien estructurado | Políticas y preguntas frecuentes |
| **Por registro** | Un elemento = un fragmento | Perfecto para datos ya atómicos | — | Reglas de crédito y catálogo |
| Semántico | Corta donde cambia el significado | Fronteras naturales | Costo extra, no determinista, difícil de explicar | No se usa |

**Decisión: chunking por tipo de documento** (`por_tipo`). No hay una estrategia mejor en abstracto; hay
una mejor para cada forma de documento.

**Parámetros** ([`parametros.toml`](../parametros.toml)): recursivo con `chunk_size = 800` caracteres
(≈ 200 tokens en español) y `chunk_overlap = 120` (15%). El solapamiento evita perder una regla que cae
en la frontera; más del 20% solo duplica texto y costo.

**La ruta de encabezados va dentro del texto que se embebe.** Cada fragmento de políticas empieza con su
ruta («Envíos › Costos de envío»). Un fragmento que dice «no aplica en estos casos» sin su título es
irrecuperable. El presupuesto del recursivo descuenta la longitud de la ruta, así que ningún fragmento
de políticas o términos supera los 800 caracteres (lo comprueba una prueba).

**Por qué no el `chunk_size=1000` del script de clase.** El documento de ejemplo tiene menos de 1.000
caracteres, así que queda en **un solo fragmento** y la recuperación es trivial: siempre devuelve todo.
Funciona por accidente; con una base real se rompería.

## 4. Calidad de los documentos

«Basura entra, basura sale» aplica doble en un RAG, porque el LLM repite con seguridad lo que le llega.

| Problema | Efecto | Cómo se resolvió aquí |
|---|---|---|
| Contradicciones entre versiones o entre política y pregunta frecuente | El LLM elige una al azar | Un solo documento vigente por tema, con `version` y `vigente_desde`; las preguntas dentro del mismo documento. Pruebas que fallan si el plazo de devolución, el retracto o las categorías no retornables difieren de `evaluar_devolucion()`, o si hay dos umbrales distintos de envío gratis |
| Idioma mezclado sin marcar | No se puede calibrar ni filtrar | Metadato `idioma` en cada fragmento |
| Duplicados | Ocupan varios de los *k* puestos con el mismo contenido | Deduplicación por *hash* del texto al indexar |
| Ruido de formato (encabezados y pies de página del PDF) | Contamina el embedding | El PDF lleva a propósito un encabezado y un pie repetidos; la limpieza detecta las líneas que se repiten en la mayoría de las páginas (con los números normalizados) y las quita |
| Texto sin contexto («ver sección anterior») | Fragmento inútil por sí solo | Secciones autocontenidas; una prueba lo verifica |

La revisión en local encontró y corrigió tres inconsistencias antes de indexar: el reparto de
transportadoras contradecía los pedidos del Taller 1; el plazo de 5 días para reportar un producto
dañado no se distinguía de la garantía legal; y la condición «solo con el empaque sellado» de una ficha
del Taller 1 se había perdido en el catálogo. Es un ejemplo de por qué la calidad se verifica y no se
supone.

## 5. Indexación paso a paso

Implementada en [`src/taller02_rag/indexing.py`](../src/taller02_rag/indexing.py) y ejecutada con
`taller02 indexar`:

1. **Cargar** cada fuente con su *loader*: Markdown con *front matter*, JSON y CSV serializados por
   registro, y el PDF con `pypdf` (lo mismo que `PyPDFLoader`, sin sumar `langchain-community`).
2. **Limpiar y normalizar**: Unicode NFC, espacios, y encabezados y pies de página del PDF.
3. **Dividir** según la estrategia de cada tipo y **enriquecer los metadatos**: `doc_id`, `tipo`,
   `seccion`, `area`, `idioma`, `hash` y un `chunk_id` determinístico (UUID derivado del documento y
   del contenido).
4. **Calcular los embeddings** en lotes con la señal de documento (`RETRIEVAL_DOCUMENT` o el prefijo de
   EmbeddingGemma), con pausa entre lotes por los límites del nivel gratuito y **caché local**: reindexar
   sin cambios no vuelve a gastar cuota.
5. **Guardar en Postgres** con esos ids. La indexación es **idempotente**: solo se embeben los
   fragmentos nuevos, y los que ya no existen (porque un documento cambió) se borran.
6. **Crear el índice HNSW** con distancia coseno.
7. **Verificar**: conteo de fragmentos por tipo y una consulta de humo por tipo de documento, guardados
   como evidencia en `outputs/indexacion_<fecha>_<perfil>.md`.

Hay **una tabla por modelo, dimensión y variante** (`kb_gemini_768`, `kb_embeddinggemma_768`,
`kb_bge_m3_1024`, `kb_gemini_768_fija300`…): nunca se mezclan vectores incompatibles, y los experimentos
comparan variantes sin reindexar cada vez.

**Conteos reales** (`outputs/indexacion_2026-10-1{4,5}_*.md`). El número de fragmentos depende solo de
la estrategia, no del modelo de embeddings:

| Estrategia | Fragmentos | Políticas | Crédito | Catálogo | Términos | Tokens aprox. | Tablas indexadas |
|---|---:|---:|---:|---:|---:|---:|---|
| `por_tipo` | 89 | 49 | 18 | 15 | 7 | 9.491 | `kb_gemini_768`, `kb_embeddinggemma_768`, `kb_bge_m3_1024`, `kb_gemini_768_enriq`* |
| `fija300` | 124 | 51 | 27 | 31 | 15 | 9.086 | `kb_gemini_768_fija300`, `kb_embeddinggemma_768_fija300` |
| `fija1000` | 39 | 16 | 8 | 10 | 5 | 9.103 | `kb_gemini_768_fija1000`, `kb_embeddinggemma_768_fija1000` |

\* La variante enriquecida suma entre 430 y 560 tokens, según la versión de los resúmenes: los 4
resúmenes en español de las fichas en inglés.

El reporte de la tabla principal (`kb_gemini_768`) es del 2026-10-15: el del 2026-10-14 lo sobrescribió
la indexación enriquecida, por un error en el nombre del reporte que ya se corrigió.

- **`por_tipo` respeta las unidades del dominio:** 18 fragmentos de crédito para 18 reglas y 15 de
  catálogo para 15 productos. `fija300` parte reglas y fichas (27 y 31 fragmentos); `fija1000` junta
  varias en uno (8 y 10).
- **Consultas de humo:** una por tipo de documento, top-1 sin filtro. Todas acertaron en todas las
  tablas salvo una en `kb_gemini_768_fija300`: «¿En cuánto tiempo llega la factura electrónica?»
  devolvió un fragmento de políticas en vez del de términos (similitud 0,698). El tema aparece en los
  dos documentos, y un trozo de 300 caracteres conserva poco del contexto que los distingue.
- **Los tiempos no son comparables entre sí** y por eso no se tabulan: dependen de la caché local de
  embeddings (una tabla reindexada sin cambios tarda 0,01 s), de las pausas y reintentos del nivel
  gratuito de Gemini y de la CPU para los modelos locales (`embeddinggemma` tardó 363 s y 494 s en las
  tablas fijas).

## 6. Cómo la división afecta el rendimiento (experimento E2)

Se indexa la misma base con tres estrategias (`fija300`, `fija1000` y `por_tipo`) y se mide, para cada
caso del set de evaluación que tiene fuente esperada:

- **hit@k**: ¿apareció el fragmento correcto entre los *k* primeros?
- **MRR**: el promedio de 1/posición del primer acierto (1 si sale primero, 0,5 si sale segundo…).

Un fragmento «acierta» si es del documento esperado y **contiene la evidencia literal** del caso. Así la
métrica vale igual para las estrategias de tamaño fijo, que no conservan la sección. E2 no llama al
LLM: es barato, determinista y aísla el efecto del chunking.

**Resultados de E2** ([`outputs/E2_2026-10-14_gemini.md`](../outputs/E2_2026-10-14_gemini.md) y
[`…_embeddinggemma.md`](../outputs/E2_2026-10-14_embeddinggemma.md)), 36 casos:

| Embeddings | Estrategia | hit@1 | hit@4 | MRR | Crédito (MRR) | Términos (MRR) | Catálogo (MRR) |
|---|---|---:|---:|---:|---:|---:|---:|
| `gemini` | **`por_tipo`** | **0,833** | **0,972** | **0,892** | **0,808** | **0,84** | 1,0 |
| `gemini` | `fija300` | 0,611 | 0,889 | 0,756 | 0,62 | 0,60 | 1,0 |
| `gemini` | `fija1000` | 0,694 | 0,944 | 0,794 | 0,717 | 0,65 | 0,778 |
| `embeddinggemma` | **`por_tipo`** | **0,778** | 0,889 | **0,833** | 0,733 | 0,629 | 1,0 |
| `embeddinggemma` | `fija300` | 0,611 | 0,861 | 0,736 | 0,50 | **0,70** | 1,0 |
| `embeddinggemma` | `fija1000` | 0,694 | **0,917** | 0,801 | **0,80** | 0,60 | 0,917 |

Lectura:

- **`por_tipo` gana en hit@1 y MRR con los dos modelos**, con ventajas de 0,08 a 0,22 en hit@1. Lo que
  más mejora es el primer puesto: con k = 4, las tres estrategias suelen tener el fragmento correcto
  en algún lugar, pero el LLM recibe primero el que corresponde.
- **El error de cada estrategia fija es el esperado.** `fija300` corta las reglas de crédito a la
  mitad (MRR de crédito 0,62 y 0,50): la condición queda en un trozo y la regla en otro. `fija1000`
  junta varias fichas en un fragmento y baja en el catálogo (0,778 con `gemini`): la ficha correcta
  llega mezclada con otra.
- **No hay un ganador absoluto por documento.** Con `embeddinggemma`, `fija1000` supera a `por_tipo`
  en crédito (0,80 frente a 0,733) y `fija300` lo supera en términos (0,70 frente a 0,629). Son 10 y 5
  casos: una o dos preguntas cambian el resultado, así que no alcanzan para preferir otra estrategia
  en esos documentos.
- **La estrategia pesa más que el modelo.** Pasar de `fija300` a `por_tipo` sube el MRR 0,10 a 0,14;
  pasar de `embeddinggemma` a `gemini` con `por_tipo` lo sube 0,06.

## 7. Conclusión

- **La base cubre lo que el Taller 1 no podía responder** con cuatro tipos de documento en cuatro
  formatos: políticas y FAQ, reglas de crédito, catálogo y términos. Deja fuera, a propósito, lo
  transaccional y personal (pedidos, datos de crédito de cada cliente, precio y stock), que se
  consulta con herramientas exactas o se remite al canal oficial.
- **Dividir respetando la estructura de cada documento es la decisión que más pesa en la
  recuperación.** En E2, `por_tipo` gana en hit@1 y MRR con los dos modelos medidos, y su ventaja
  sobre los tamaños fijos (0,10 a 0,14 de MRR frente a `fija300`) es mayor que la de cambiar de
  modelo de embeddings (0,06). Un fragmento por regla y uno por producto evita los dos errores típicos
  del tamaño fijo: partir una regla y mezclar dos fichas.
- **La calidad se verifica, no se supone.** Las pruebas de coherencia con el Taller 1 y las corridas
  reales encontraron contradicciones (transportadoras, plazos de daño frente a garantía, la condición
  de empaque sellado) que se corrigieron antes de medir.
- **La indexación es reproducible y barata:** idempotente, con caché de embeddings, una tabla por
  modelo y variante, y evidencia de cada corrida en `outputs/`. Reindexar la base completa en una
  máquina nueva tomó unos 10 s con Gemini y 9 s con `embeddinggemma` (2026-10-17).

Lo que queda abierto: con 5 a 15 casos por documento, las diferencias de un caso cambian el ganador
dentro de un documento. Un set más grande permitiría ajustar la estrategia por tipo de documento con
más confianza.
