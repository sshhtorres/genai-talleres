# Datos del Taller 2

EcoMarket es una empresa ficticia: todos los documentos son **sintéticos**, sin datos de personas, y
coherentes con los datos del Taller 1 (mismos 15 productos y categorías, misma política de
devoluciones basada en la Ley 1480 de 2011).

## Base de conocimiento (`kb/`)

Cuatro tipos de documento en cuatro formatos, porque cada formato exige su propio *loader* y su
propia estrategia de chunking:

| Archivo | Formato | Contenido | Idioma |
|---|---|---|---|
| [`politicas-y-faq.md`](kb/politicas-y-faq.md) | Markdown con front matter (`version`, `vigente_desde`) | Un solo documento con cuatro áreas (`#`): Devoluciones y garantías, Envíos, Pagos y cuenta, Sostenibilidad. Cada área tiene sus reglas (`##`) y sus preguntas frecuentes (`###`): 24 en total | Español |
| [`reglas-credito.json`](kb/reglas-credito.json) | JSON | 18 reglas de la financiación de compras en cuotas: requisitos, cupo, cuotas por monto, tasa (siempre frente a la usura vigente, sin cifras reales), pago anticipado, mora, aviso previo, devoluciones y productos no financiables | Español |
| [`catalogo.csv`](kb/catalogo.csv) | CSV | Los 15 productos del Taller 1 con descripción, materiales, modo de uso, cuidados, certificaciones y la condición de devolución de cada ficha (la `nota_retorno` del Taller 1). **Sin precio ni stock**, que cambian a diario y se consultan en el sistema | 11 en español, **4 en inglés** |
| [`terminos-y-condiciones.pdf`](kb/terminos-y-condiciones.pdf) | PDF (generado desde [`fuentes/terminos-y-condiciones.md`](kb/fuentes/terminos-y-condiciones.md)) | Precios, medios de pago, facturación electrónica, datos personales (Ley 1581 de 2012), responsabilidad y PQR | Español |

Decisiones de contenido:

- **Políticas y FAQ en un solo documento.** Las preguntas frecuentes repiten las políticas con otras
  palabras; separadas, se desincronizan (la política dice 30 días y la FAQ vieja dice 15). Juntas hay
  una sola fuente de verdad, y cada pregunta hereda la ruta de su área.
- **Las 4 fichas en inglés** (cepillo de bambú, botella térmica, compostera y cargador solar) simulan
  a un vendedor internacional y sirven para probar la recuperación translingüe. Todo lo demás está
  en español.
- **El PDF lleva encabezado y pie de página repetidos** a propósito, para que la limpieza tenga ruido
  que quitar. Se regenera con `uv run python taller-02-ecomarket-rag/scripts/generar_pdf.py`, que
  produce exactamente el mismo archivo si la fuente no cambia.
- **Información que solo tiene el RAG:** el programa de reciclaje de envases (Sostenibilidad), la
  facturación electrónica y las reglas de crédito no estaban en ningún dato del Taller 1.
- **Garantía legal frente al plazo de 5 días:** el plazo de 5 días es para reportar un producto que
  *llegó* dañado; las fallas que aparecen después, durante el uso, se atienden por la garantía legal.
- **Qué no entra:** los pedidos y los datos de crédito de cada cliente (son transaccionales y
  personales: se consultan con herramientas, no se recuperan por similitud), ni precios ni stock.

## Set de evaluación (`eval/casos_rag.jsonl`)

42 casos, uno por línea:

| Tipo | Casos | Qué se espera |
|---|---:|---|
| `dentro_alcance` | 21 | Recuperar la fuente correcta y responder con sus datos (al menos 4 por documento y uno por área de políticas) |
| `fuera_alcance` | 6 | Abstenerse. Incluye negativos difíciles: el precio (no indexado) y "tienda física en Bogotá" |
| `mixto` | 3 | Pedido + política en el mismo mensaje |
| `inyeccion` | 2 | Ignorar instrucciones incrustadas en el mensaje |
| `reformulacion` | 3 | Preguntas coloquiales ("¿me devuelven la plata si…?") |
| `translingue` | 4 | 2 en español sobre fichas en inglés y 2 en inglés sobre políticas en español |
| `credito_trampa` | 3 | Piden aprobar, calcular una cuota o recomendar endeudarse: explicar la regla y remitir, sin cifras calculadas |

El stock tampoco se indexa, pero su caso (`ter-05`) es de alcance: la respuesta correcta no da un
número de unidades, sino que explica la regla general de los términos ("la disponibilidad cambia a
diario") y remite a la tienda.

En `debe_contener`, las alternativas válidas se separan con `|` ("12 horas|12 h|doce horas"). El campo
opcional `cifras_con_respaldo: true` exige que toda cifra de dinero o porcentaje de la respuesta
aparezca literal en el contexto recuperado o en la pregunta: así un precio inventado o una cuota
calculada fallan aunque no se pueda prever la cifra exacta.

Cada fuente esperada lleva, además del documento y la sección, una **`evidencia`**: un fragmento
literal del documento. Un chunk recuperado "acierta" si contiene esa evidencia; así hit@k y MRR se
miden igual con cualquier estrategia de chunking, incluso con las de tamaño fijo, que no conservan
la sección.

## Verificación

[`tests/test_kb.py`](../tests/test_kb.py) comprueba en cada `uv run pytest`, entre otras cosas: que
la política coincide con `evaluar_devolucion()` del Taller 1 en plazos y categorías no retornables;
que el catálogo tiene los mismos productos, categorías y banderas de retorno que el del Taller 1;
que no hay precios, stock, tasas concretas, correos reales ni números que parezcan teléfonos o
cédulas; que el PDF conserva el texto de su fuente; y que cada fuente esperada del set de evaluación
existe y contiene su evidencia.
