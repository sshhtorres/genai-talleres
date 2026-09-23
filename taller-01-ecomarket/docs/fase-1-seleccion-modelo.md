# Fase 1: Selección y justificación del modelo

**Caso:** EcoMarket · optimización de la atención al cliente con IA generativa

## 0. Criterios y suposiciones

Estas son mis decisiones de partida como autor del taller. El resto del documento las argumenta;
declararlas aquí permite juzgar la propuesta sabiendo desde dónde se construyó.

- Prefiero desarrollar rápido un prototipo que permita evaluar y validar una solución base, usando
  modelos de proveedores comerciales como Gemini o Claude. Las consideraciones de infraestructura
  propia, local o en la nube, las dejo para una etapa posterior de optimización.
- Elijo dos proveedores, Gemini y Claude, por familiaridad y facilidad de integración.
- Un modelo liviano como enrutador es suficiente para clasificar el tipo de consulta, por ejemplo
  `gemini-3.1-flash-lite` o `claude-haiku-4-5`.
- Un modelo intermedio como `gemini-3.5-flash-lite` o `claude-sonnet-5` puede bastar para procesar
  las solicitudes que impliquen validar datos y redactar una respuesta.
- Los modelos mencionados, apoyados en RAG, tienen desempeño y ventana de contexto suficientes para
  operar sin fine-tuning, al menos en una primera etapa de evaluación de la propuesta.
- Asumo un volumen de 5.000 consultas diarias, 150.000 al mes, para dimensionar el costo, repartidas
  según el 80/20 del enunciado.
- Asumo que el 20% complejo mantiene siempre a una persona en el circuito: el modelo asiste al
  agente humano y no decide por él.
- Uso el tier gratuito de los proveedores únicamente porque todos los datos del taller son
  sintéticos. En producción haría falta el tier de pago con un acuerdo de tratamiento de datos.

Los identificadores exactos de modelo viven en `providers.toml`, no en este documento ni en el
código; aquí se nombran en su forma corta por legibilidad.

---

## 1. Requisitos del caso

Antes de nombrar un modelo hay que decir qué tiene que resolver. Cada hecho del enunciado genera un
requisito técnico, y es contra esos requisitos que se justifica la elección.

| Hecho del caso | Requisito que genera |
|---|---|
| Miles de consultas diarias por chat, correo y redes sociales | Alta concurrencia, baja latencia y **costo por consulta bajo**; un solo motor para varios canales |
| El 80% son repetitivas: estado de pedido, devoluciones, características del producto | **Precisión factual** sobre datos vivos. El modelo no debe "saber" un estado de pedido: debe **consultarlo** |
| El 20% son complejas: quejas, problemas técnicos, sugerencias | Empatía, razonamiento y **escalamiento a un humano**; el modelo apoya al agente, no lo reemplaza |
| El tiempo de respuesta actual llega a 24 horas | Respuesta inmediata en el 80% y borrador asistido en minutos para el 20% |
| La empresa crece rápido | Escalabilidad elástica **sin reentrenar** cuando cambian el catálogo o las políticas |
| La marca se basa en productos sostenibles | Tono coherente con la marca y cero respuestas inventadas: la confianza es el activo |

Dos requisitos mandan sobre el resto. El primero es que **la mayor parte del trabajo es de consulta,
no de generación**: el cliente que pregunta por el pedido ECO-1005 quiere un dato, no una redacción
creativa. El segundo es que **los datos cambian todos los días**: pedidos, inventario y políticas se
mueven constantemente. Ambos empujan hacia la misma conclusión arquitectónica, que se desarrolla en
la sección 2.

## 2. Solución propuesta: arquitectura híbrida

El sistema propuesto consiste en el uso de modelos y controles alrededor:

```mermaid
flowchart LR
    C[Cliente<br/>chat · email · redes] --> G[Gateway omnicanal<br/>+ anonimización de PII]
    G --> R{Router de intención<br/>modelo liviano / Flash-Lite}
    R -- estado de pedido --> T1[Herramienta: API de pedidos<br/>consulta determinística]
    R -- devolución / producto --> T2[RAG: políticas + catálogo<br/>base vectorial]
    T1 --> L[Modelo liviano<br/>gemini-3.5-flash-lite]
    T2 --> L
    L --> V[Validador<br/>guardrails + verificación de datos]
    V -- ok --> C
    R -- queja / técnico / baja confianza --> H[Agente humano<br/>+ copiloto: gemini-3.1-pro-preview]
    V -- falla / cliente pide humano --> H
    H --> C
    V --> M[(Logs y métricas<br/>CSAT, FCR, tasa de escalamiento)]
```

Cada componente responde a un requisito concreto:

1. **Router de intención.** Un clasificador muy barato separa el 80% del 20% y decide qué
   herramienta usar. Evita pagar el modelo robusto en consultas triviales; es la pieza que hace que
   el costo total sea sostenible.
2. **Tool calling contra la base de pedidos.** El estado de un pedido es un **dato**, no
   conocimiento. Se consulta de forma determinística y el LLM solo redacta con el resultado a la
   vista. Esta es la mitigación principal de las alucinaciones, y la que se demuestra en la Fase 3.
3. **RAG sobre políticas y catálogo.** El catálogo y las políticas cambian con frecuencia; con
   recuperación se actualizan sin reentrenar nada. El fine-tuning no sirve para datos que cambian.
4. **Modelo liviano** para el volumen: menor latencia y costo, y calidad suficiente cuando el
   contexto viene dado. Cuando el modelo no tiene que recordar, un modelo pequeño basta.
5. **Modelo robusto como copiloto del agente humano** en el 20% complejo: resume el caso, propone un
   borrador empático y sugiere una solución. El humano decide y firma.
6. **Validador y guardrails.** Comprueba que los números de pedido, las fechas y los enlaces de la
   respuesta existan de verdad en los datos consultados; bloquea las promesas fuera de política y
   deriva a un humano si detecta frustración.
7. **Observabilidad.** Métricas de negocio (CSAT, tiempo de primera respuesta, tasa de resolución en
   el primer contacto, tasa de escalamiento) y de calidad (tasa de alucinación medida por auditoría
   por muestreo).

La Fase 3 de este taller implementa una versión en miniatura de los componentes 2, 4 y 6: búsqueda
determinística en JSON, redacción con un modelo liviano y validación en código de la respuesta.

## 3. Modelos seleccionados

La elección es una **familia de modelos con dos tamaños**, no un modelo único, porque los dos
segmentos del tráfico tienen necesidades opuestas: volumen barato frente a razonamiento fino.

| Rol | Opción principal (Google) | Alternativa comercial (Anthropic) | Por qué ese tamaño |
|---|---|---|---|
| Router de intención | `gemini-3.1-flash-lite` | `claude-haiku-4-5` | Clasificar entre cinco intenciones no necesita un modelo grande |
| Motor del 80% repetitivo | `gemini-3.5-flash-lite` | `claude-sonnet-5` | Con el contexto ya recuperado, la tarea es redactar, no razonar; un modelo con razonamiento sería gasto inútil |
| Copiloto del 20% complejo | `gemini-3.1-pro-preview` | `claude-opus-5-5` | Quejas y problemas técnicos exigen razonamiento y matiz de tono |

Se elige **Gemini como opción principal** por tres razones concretas del proyecto: tiene un tier
gratuito que permite iterar desde el primer día, expone una **API compatible con la de OpenAI** (lo
que reduce el acoplamiento, como se explica abajo), y su modelo liviano tiene una relación
costo-latencia adecuada para miles de consultas diarias. Anthropic queda documentado como
alternativa de calidad equivalente, y en el código basta cambiar un perfil de configuración para
usarlo.

**Por qué Flash-Lite y no Flash para el motor del 80%.** La elección inicial fue `gemini-3.8-flash`,
el modelo intermedio de la familia. Al ejecutar la Fase 3 contra la API aparecieron dos límites que
la descartaron:

- Su **tier gratuito permite 20 peticiones al día**, insuficiente para iterar sobre una suite de
  evaluación, y muy lejos de las 5.000 consultas diarias del caso.
- Es un **modelo con razonamiento**: consume el presupuesto de `max_tokens` pensando antes de
  responder, así que con un presupuesto ajustado devuelve una respuesta vacía. Para redactar sobre un
  contexto ya recuperado, ese razonamiento no aporta y sí se paga.

`gemini-3.5-flash-lite` responde en menos de un segundo, no gasta tokens en razonamiento y su cuota
gratuita permite ejecutar la matriz completa. Es el modelo con el que se produjo la evidencia de la
Fase 3 y el que se recomienda para el 80% repetitivo. El escenario con Flash se conserva en la tabla
de costos de §6.1 como comparación.

Este episodio ilustra algo que ninguna hoja de especificaciones anticipa: **la cuota y el
comportamiento real del modelo pesan tanto como su calidad nominal**, y solo se conocen ejecutando.
Es un argumento más para la capa de abstracción de proveedores.

**Los IDs de modelo no están en el código.** Viven en un único archivo `providers.toml`, y el código
pide "el modelo liviano" o "el modelo robusto", no un ID concreto. Esta decisión es deliberada: los
proveedores retiran y renombran versiones con frecuencia, y una migración debe costar una línea de
configuración, no una refactorización.

## 4. ¿Modelo de propósito general o afinado?

**Propósito general, con RAG y herramientas, sin fine-tuning en la versión 1.** Los argumentos:

- **Los datos críticos cambian a diario.** Pedidos, inventario y políticas se mueven cada día, y el
  fine-tuning congela conocimiento en los pesos. Un modelo afinado con el catálogo de septiembre
  responde con el catálogo de septiembre en diciembre. RAG no tiene ese problema.
- **El tono y el formato se logran con prompting.** Rol, ejemplos *few-shot* y reglas explícitas
  producen la voz de marca, y se iteran en horas. La Fase 3 lo demuestra midiendo la diferencia
  entre un prompt básico y uno con esas técnicas.
- **No hay datos curados.** El fine-tuning exige conversaciones etiquetadas, consistentes y limpias
  de PII, que EcoMarket todavía no tiene. Afinar con datos sucios reproduce y amplifica los errores
  y sesgos históricos del equipo.
- **El costo de equivocarse es distinto.** Cambiar un prompt es gratis; reentrenar un modelo, no.

**Evolución futura.** Cuando existan miles de conversaciones resueltas y anonimizadas, tiene sentido
evaluar un SLM afinado para el router o para el 80% repetitivo, y reducir así costo y latencia. Esa
es la alternativa C de la sección siguiente, y el diseño actual no la cierra.

## 5. Comparación de alternativas

| Criterio | **A. Híbrida con modelos de frontera (elegida)** | B. Open-source autoalojado + RAG | C. SLM afinado + LLM |
|---|---|---|---|
| Arquitectura | Router + modelo liviano con RAG y herramientas + modelo robusto como copiloto | Llama / Qwen / gpt-oss en GPU propias o nube privada | SLM (1–8B) afinado para lo repetitivo + LLM para lo complejo |
| Calidad de respuesta | Muy alta; buen español; tool calling maduro | Buena a muy buena según el tamaño; exige más ajuste de prompts | Muy buena en tareas estrechas; frágil fuera de su distribución |
| Tiempo al primer piloto | **Días** | Semanas (infraestructura, MLOps) | Semanas a meses (datos, entrenamiento, evaluación) |
| Costo | Variable por token, sin inversión inicial | Costo fijo alto (GPU y equipo); barato a gran escala | Costo de entrenamiento; inferencia muy barata |
| Escalabilidad | Elástica, gestionada por el proveedor | La gestiona EcoMarket | Buena por el tamaño del modelo |
| Integración | SDK y APIs compatibles con OpenAI; function calling nativo | APIs compatibles (vLLM, Ollama), con más piezas propias | Pipeline de datos y reentrenamiento continuo |
| Privacidad | Depende del contrato: tier de pago, DPA y región | **Máxima**: los datos no salen de la empresa | Alta si se autoaloja |
| Dependencia del proveedor | Media; se mitiga con la capa de abstracción | Baja | Baja a media |
| Cuándo conviene | Validar valor rápido y crecer | Volumen muy alto o regulación estricta | Tareas estables con muchos datos históricos |

**Conclusión.** La alternativa A es la mejor opción *hoy* por tiempo al valor, calidad e integración.
Lo importante es que la decisión no es irreversible: la capa de abstracción de proveedores permite
**migrar a B** —la Fase 3 de este taller comprueba que las mismas cadenas corren sin cambios contra
otra familia de modelos— si crecen el volumen o las exigencias de privacidad, y **evolucionar hacia C**
cuando existan datos curados. Elegir A no cierra ninguna puerta; empezar por B o C sí retrasa el
aprendizaje varios meses.

## 6. Costo, escalabilidad e integración

### 6.1 Costo

**Supuestos de carga:** 5.000 consultas/día, es decir 150.000/mes, repartidas 80/20 en 120.000
repetitivas y 30.000 complejas. El router procesa las 150.000 con ~600 tokens de entrada y 50 de
salida; una consulta repetitiva consume ~3.000 de entrada (prompt de sistema más contexto
recuperado) y 300 de salida; un caso complejo, ~4.000 de entrada y 500 de salida.

**Precios de lista por millón de tokens (entrada / salida), consultados el 2026-09-23** en
[Gemini](https://ai.google.dev/gemini-api/docs/pricing) y
[Claude](https://platform.claude.com/docs/en/about-claude/models/overview):

| Modelo | Entrada | Salida |
|---|---:|---:|
| `gemini-3.1-flash-lite` | US$0,25 | US$1,50 |
| `gemini-3.5-flash-lite` | US$0,30 | US$2,50 |
| `gemini-3.8-flash` | US$0,75 | US$3,75 |
| `gemini-3.1-pro-preview` | US$2,00 | US$12,00 |
| `claude-haiku-4-5` | US$1,00 | US$5,00 |
| `claude-sonnet-5` | US$2,00 | US$10,00 |
| `claude-opus-5-5` | US$4,00 | US$20,00 |

Aplicando esos precios a los supuestos de carga:

| Escenario | Router | 80% repetitivo | 20% complejo (copiloto) | **Total/mes** |
|---|---:|---:|---:|---:|
| **Recomendado** — Flash-Lite 3.1 / Flash-Lite 3.5 / Pro | US$34 | US$198 | US$420 | **US$652** |
| Con Flash como motor — Flash-Lite 3.1 / Flash 3.8 / Pro | US$34 | US$405 | US$420 | **US$859** |
| Con Flash, al precio vigente desde enero de 2027 | US$34 | US$810 | US$420 | **US$1.264** |
| Claude — Haiku 4.5 / Sonnet 5 / Opus 5.5 | US$128 | US$1.080 | US$780 | **US$1.988** |
| Claude económico — Haiku 4.5 / Haiku 4.5 / Sonnet 5 | US$128 | US$540 | US$390 | **US$1.058** |

Estas cifras son un **orden de magnitud para comparar escenarios, no un presupuesto**: suponen
precios de lista, sin descuentos por volumen ni por procesamiento por lotes. Lo relevante para la
decisión son tres lecturas:

- El escenario recomendado cuesta **menos de la mitad** que el más caro, y la diferencia la explica
  casi por completo la elección del motor del 80%: es el componente que se multiplica por 120.000.
- Incluso el escenario más caro cuesta menos que un agente adicional de tiempo completo, y atiende
  150.000 consultas al mes.
- El *prompt caching* —el prompt de sistema y la política se repiten idénticos en cada consulta—
  reduciría de forma importante el costo de entrada, que es el componente dominante.

### 6.2 Escalabilidad

La escalabilidad de la alternativa A es elástica y no requiere inversión: en un pico de temporada el
proveedor absorbe la carga y el costo crece de forma proporcional al uso, no en escalones. Los
límites reales son los *rate limits* del proveedor, que se gestionan con colas, reintentos con
backoff exponencial y degradación controlada (si el modelo liviano no responde, la conversación pasa
a la fila de agentes humanos en lugar de fallar). El código de la Fase 3 ya implementa los reintentos
con backoff por esta razón.

El componente que **no** escala solo es el equipo humano: si la tasa de escalamiento se mantiene en
el 20%, atender el doble de consultas exige el doble de agentes para ese segmento. Por eso la métrica
de tasa de escalamiento es una métrica de negocio y no solo técnica.

### 6.3 Integración

Toda la comunicación con los modelos pasa por **un único cliente compatible con la API de OpenAI**,
configurado con un perfil por proveedor: URL base, variable de la clave y modelos por rol. Cambiar de
Gemini a Anthropic o a un modelo local es cambiar un valor de configuración, sin tocar la
lógica de negocio.
Esta decisión tiene un costo: el código común no puede usar parámetros exclusivos de un proveedor.
La restricción es sobre el código, no sobre el sistema, porque las particularidades se declaran en
configuración; en la Fase 3 hizo falta, por ejemplo, para que `claude-sonnet-5` no reciba el
parámetro `temperature`, que ese modelo rechaza. El beneficio compensa de sobra: reduce la
dependencia del proveedor, que es uno de los riesgos identificados en la Fase 2.

Hacia los sistemas de EcoMarket, la integración es la habitual: la API de pedidos se expone como
herramienta (*function calling*) y el catálogo y las políticas se indexan en una base vectorial. El
gateway omnicanal normaliza chat, correo y redes en un mismo formato de mensaje, de modo que hay un
solo motor para los tres canales.

## 7. Hoja de ruta

| Etapa | Alcance | Criterio para pasar a la siguiente |
|---|---|---|
| **1. Piloto (4–6 semanas)** | Un canal (chat web) y dos intenciones (estado de pedido y devoluciones), con human-in-the-loop en el 100% de los casos al inicio | Tasa de alucinación por debajo del umbral acordado en la auditoría por muestreo; CSAT igual o mejor que la línea base |
| **2. Producción acotada** | Respuesta automática sin revisión previa en las intenciones validadas; el resto sigue escalando a un humano | Tasa de resolución en el primer contacto estable; sin incidentes de privacidad |
| **3. Omnicanal** | Correo y redes sociales sobre el mismo motor; copiloto para agentes en el 20% complejo | Volumen atendido y tiempos sostenidos en los tres canales |
| **4. Optimización** | Evaluar un SLM afinado para el router o para el 80% repetitivo; *prompt caching*; posible migración a open-source autoalojado | Decisión basada en costo por conversación y en exigencias de privacidad |

Cada etapa mantiene la misma arquitectura; lo que cambia es cuánto se automatiza y con qué modelo se
ejecuta cada rol.

## 8. Conclusión

Para EcoMarket, la recomendación es una **arquitectura híbrida con modelos de propósito general de
frontera, RAG y tool calling, sin fine-tuning en la versión 1**, usando `gemini-3.5-flash-lite` para
el 80% repetitivo y un modelo robusto como copiloto del agente humano en el 20% complejo.

La justificación se apoya en cuatro factores conectados con el caso:

- **Arquitectura**: el problema dominante no es de generación sino de acceso a datos que cambian a
  diario, y eso lo resuelven RAG y las herramientas, no un modelo más grande ni un modelo afinado.
- **Costo**: el diseño de dos tamaños con un router deja el gasto en unos US$650 mensuales para
  150.000 consultas, por debajo del costo de un agente adicional.
- **Escalabilidad**: la capacidad es elástica y no exige inversión en infraestructura, lo que encaja
  con una empresa en crecimiento rápido y con picos estacionales.
- **Integración**: un solo cliente compatible con la API de OpenAI, con los IDs de modelo en
  configuración, permite cambiar de proveedor sin reescribir la aplicación y reduce el riesgo de
  quedar atrapado en un vendedor.

La elección es además **reversible por diseño**, que es quizá su mejor propiedad: el mismo código
corre sin cambios contra otra familia de modelos, como se comprueba en la Fase 3 ejecutando las
mismas cadenas contra Gemini y contra Claude. Migrar a un modelo open-source autoalojado usaría esa
misma capa de abstracción —solo cambia el perfil del proveedor—, aunque probarlo queda fuera del
alcance de este taller.
