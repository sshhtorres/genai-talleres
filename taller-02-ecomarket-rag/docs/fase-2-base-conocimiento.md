# Fase 2: Base de conocimiento

**Caso:** EcoMarket · generación aumentada por recuperación (RAG) para la atención al cliente

> **Estado del documento: borrador.** Las secciones marcadas con ⏳ se completan con las corridas
> reales (indexación y experimento E2), que se guardan en [`outputs/`](../outputs/).

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
| **Precio y stock** | **No** | Cambian a diario y una cifra vieja es peor que ninguna. El catálogo se indexa por su parte descriptiva; el set de evaluación incluye un caso de precio que exige abstenerse y uno de stock que exige remitir a la tienda |

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

> ⏳ **Conteos reales** (`outputs/indexacion_<fecha>_gemini.md` y los de las demás tablas): fragmentos
> por tipo, tokens aproximados, tiempo y resultado de las consultas de humo.

## 6. Cómo la división afecta el rendimiento (experimento E2)

Se indexa la misma base con tres estrategias (`fija300`, `fija1000` y `por_tipo`) y se mide, para cada
caso del set de evaluación que tiene fuente esperada:

- **hit@k**: ¿apareció el fragmento correcto entre los *k* primeros?
- **MRR**: el promedio de 1/posición del primer acierto (1 si sale primero, 0,5 si sale segundo…).

Un fragmento «acierta» si es del documento esperado y **contiene la evidencia literal** del caso. Así la
métrica vale igual para las estrategias de tamaño fijo, que no conservan la sección. E2 no llama al
LLM: es barato, determinista y aísla el efecto del chunking.

> ⏳ **Resultados de E2** (`outputs/E2_<fecha>_gemini.md` y `…_embeddinggemma.md`): hit@1, hit@4 y MRR
> por estrategia, global y por tipo de documento, y su lectura.

## 7. Conclusión

> ⏳ Se redacta con los conteos de indexación y los resultados de E2.
