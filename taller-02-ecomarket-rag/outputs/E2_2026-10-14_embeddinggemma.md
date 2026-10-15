# E2 — Chunking: hit@k y MRR por estrategia (embeddinggemma)

**Fecha:** 2026-10-14

> Generado por `taller02 evaluar`/`calibrar`. No editar a mano: es la evidencia de una ejecución real.

## Métricas por estrategia y por documento

**global**

| Variante | Casos | hit@1 | hit@4 | mrr |
|---|---:|---:|---:|---:|
| por_tipo | 36 | 0.778 | 0.889 | 0.833 |
| fija300 | 36 | 0.611 | 0.861 | 0.736 |
| fija1000 | 36 | 0.694 | 0.917 | 0.801 |

**doc:politicas-y-faq**

| Variante | Casos | hit@1 | hit@4 | mrr |
|---|---:|---:|---:|---:|
| por_tipo | 15 | 0.867 | 0.933 | 0.9 |
| fija300 | 15 | 0.667 | 0.933 | 0.8 |
| fija1000 | 15 | 0.667 | 1.0 | 0.822 |

**doc:reglas-credito**

| Variante | Casos | hit@1 | hit@4 | mrr |
|---|---:|---:|---:|---:|
| por_tipo | 10 | 0.6 | 0.9 | 0.733 |
| fija300 | 10 | 0.3 | 0.7 | 0.5 |
| fija1000 | 10 | 0.7 | 0.9 | 0.8 |

**doc:catalogo**

| Variante | Casos | hit@1 | hit@4 | mrr |
|---|---:|---:|---:|---:|
| por_tipo | 6 | 1.0 | 1.0 | 1.0 |
| fija300 | 6 | 1.0 | 1.0 | 1.0 |
| fija1000 | 6 | 0.833 | 1.0 | 0.917 |

**doc:terminos-y-condiciones**

| Variante | Casos | hit@1 | hit@4 | mrr |
|---|---:|---:|---:|---:|
| por_tipo | 5 | 0.6 | 0.6 | 0.629 |
| fija300 | 5 | 0.6 | 0.8 | 0.7 |
| fija1000 | 5 | 0.6 | 0.6 | 0.6 |

**translingue**

| Variante | Casos | hit@1 | hit@4 | mrr |
|---|---:|---:|---:|---:|
| por_tipo | 4 | 1.0 | 1.0 | 1.0 |
| fija300 | 4 | 0.75 | 1.0 | 0.875 |
| fija1000 | 4 | 1.0 | 1.0 | 1.0 |


## Detalle por caso (por_tipo)

| Caso | Tipo | Esperado | Rango | Top-1 | Score top-1 |
|---|---|---|---:|---|---:|
| pol-envios-01 | dentro_alcance | politicas-y-faq | 1 | Envíos › Preguntas frecuentes › ¿Cuánto cuesta el envío? | 0.5926 |
| pol-envios-02 | dentro_alcance | politicas-y-faq | 1 | Envíos › Preguntas frecuentes › ¿Hacen envíos fuera de Colombia? | 0.5038 |
| pol-pagos-01 | dentro_alcance | politicas-y-faq | 1 | Pagos y cuenta › Preguntas frecuentes › ¿Puedo pagar contra entrega? | 0.5391 |
| pol-pagos-02 | dentro_alcance | politicas-y-faq | 1 | Pagos y cuenta › Preguntas frecuentes › ¿Puedo usar dos cupones en la misma compra? | 0.7535 |
| pol-sostenibilidad-01 | dentro_alcance | politicas-y-faq | 1 | Sostenibilidad › Preguntas frecuentes › ¿Qué hago con los envases vacíos? | 0.5078 |
| pol-sostenibilidad-02 | dentro_alcance | politicas-y-faq | 1 | Sostenibilidad › Preguntas frecuentes › ¿Los empaques de los pedidos tienen plástico? | 0.7059 |
| pol-devoluciones-01 | dentro_alcance | politicas-y-faq | 1 | Devoluciones y garantías › Tiempos de reembolso | 0.5964 |
| cred-01 | dentro_alcance | reglas-credito | 2 | Reglas de crédito › CR-06 · Número de cuotas según el monto | 0.5788 |
| cred-02 | dentro_alcance | reglas-credito | 1 | Reglas de crédito › CR-14 · Aviso previo antes de reportar a centrales de riesgo | 0.5445 |
| cred-03 | dentro_alcance | reglas-credito | 1 | Reglas de crédito › CR-10 · Pago anticipado | 0.5517 |
| cred-04 | dentro_alcance | reglas-credito | 1 | Reglas de crédito › CR-09 · Costos adicionales | 0.5696 |
| cred-05 | dentro_alcance | reglas-credito | 1 | Reglas de crédito › CR-16 · Productos y compras no financiables | 0.5815 |
| cat-01 | dentro_alcance | catalogo | 1 | Catálogo › P-103 · Café orgánico en grano 500 g | 0.4875 |
| cat-02 | dentro_alcance | catalogo | 1 | Catálogo › P-105 · Detergente concentrado a granel 1 L | 0.4733 |
| cat-03 | dentro_alcance | catalogo | 1 | Catálogo › P-108 · Vaso de vidrio con tapa de bambú 500 ml | 0.4908 |
| cat-04 | dentro_alcance | catalogo | 1 | Catálogo › P-115 · Esponjas vegetales de lufa (pack x3) | 0.6108 |
| ter-01 | dentro_alcance | terminos-y-condiciones | 1 | Términos y condiciones › página 1 | 0.4922 |
| ter-02 | dentro_alcance | terminos-y-condiciones | 1 | Términos y condiciones › página 1 | 0.4431 |
| ter-03 | dentro_alcance | terminos-y-condiciones | 1 | Términos y condiciones › página 2 | 0.4347 |
| ter-04 | dentro_alcance | terminos-y-condiciones | 7 | Reglas de crédito › CR-15 · Devolución de una compra financiada | 0.4463 |
| ter-05 | dentro_alcance | terminos-y-condiciones | — | Devoluciones y garantías › Preguntas frecuentes › Mi cargador solar dejó de funcionar a los tres meses, ¿qué hago? | 0.4710 |
| mixto-01 | mixto | politicas-y-faq | 6 | Devoluciones y garantías › Tiempos de reembolso | 0.5492 |
| mixto-02 | mixto | politicas-y-faq | 3 | Envíos › Preguntas frecuentes › ¿Dónde encuentro el número de seguimiento? | 0.5041 |
| mixto-03 | mixto | politicas-y-faq | 1 | Envíos › Preguntas frecuentes › ¿Puedo cambiar la dirección de entrega después de comprar? | 0.5935 |
| iny-01 | inyeccion | politicas-y-faq | 1 | Devoluciones y garantías › Plazo para solicitar una devolución | 0.5307 |
| iny-02 | inyeccion | reglas-credito | 3 | Reglas de crédito › CR-03 · Cupo de financiación | 0.4546 |
| reform-01 | reformulacion | politicas-y-faq | 1 | Devoluciones y garantías › Preguntas frecuentes › ¿Puedo devolver un producto que ya abrí? | 0.5127 |
| reform-02 | reformulacion | politicas-y-faq | 1 | Envíos › Tiempos de entrega | 0.5622 |
| reform-03 | reformulacion | reglas-credito | 1 | Reglas de crédito › CR-13 · Mora e intereses de mora | 0.4781 |
| transl-01 | translingue | catalogo | 1 | Catálogo › P-101 · Bamboo toothbrush (pack of 4) | 0.5839 |
| transl-02 | translingue | catalogo | 1 | Catálogo › P-106 · Stainless steel thermal bottle 750 ml | 0.5334 |
| transl-03 | translingue | politicas-y-faq | 1 | Devoluciones y garantías › Plazo para solicitar una devolución | 0.5622 |
| transl-04 | translingue | politicas-y-faq | 1 | Envíos › Preguntas frecuentes › ¿Hacen envíos fuera de Colombia? | 0.6257 |
| trampa-01 | credito_trampa | reglas-credito | — | Reglas de crédito › CR-06 · Número de cuotas según el monto | 0.4534 |
| trampa-02 | credito_trampa | reglas-credito | 1 | Reglas de crédito › CR-06 · Número de cuotas según el monto | 0.6152 |
| trampa-03 | credito_trampa | reglas-credito | 2 | Devoluciones y garantías › Preguntas frecuentes › Mi cargador solar dejó de funcionar a los tres meses, ¿qué hago? | 0.4671 |
