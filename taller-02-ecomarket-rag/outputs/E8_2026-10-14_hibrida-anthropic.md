# Resultados — hibrida-anthropic (embeddinggemma:300m + claude-haiku-5-5)

**Fecha de ejecución:** 2026-10-14  
**Proveedor:** `hibrida-anthropic` · **Modelo:** `embeddinggemma:300m + claude-haiku-5-5`  
**Casos ejecutados:** 10 · **Con todos los chequeos en verde:** 10/10

> Generado automáticamente por `genai_common.runs.RunRecorder`. No editar a mano: es la evidencia de una ejecución real.

## Resumen por variante

| Variante | Casos | Chequeos OK | % |
|---|---:|---:|---:|
| hibrida:anthropic | 10 | 10 | 100% |

## Detalle por caso

### `pol-envios-01` · E8:dentro_alcance · **hibrida:anthropic**

**Consulta:** ¿Cuánto cuesta el envío y desde qué monto es gratis?

**Respuesta:**

```text
El costo del envío depende de la ciudad de destino y se muestra antes de pagar [Envíos › Preguntas frecuentes › ¿Cuánto cuesta el envío?]. El envío es gratis en compras desde 150.000 pesos colombianos, después de aplicar cupones de descuento [Envíos › Costos de envío].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 2 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:150.000 | ✓ | ok |

*Latencia: 1.297 s · tokens: 2284 entrada / 116 salida*

### `pol-envios-02` · E8:dentro_alcance · **hibrida:anthropic**

**Consulta:** ¿Hacen envíos a otros países?

**Respuesta:**

```text
No, por ahora EcoMarket solo envía dentro del territorio colombiano y no realiza envíos internacionales [Envíos › Preguntas frecuentes › ¿Hacen envíos fuera de Colombia?] [Envíos › Cobertura].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 2 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:Colombia | ✓ | ok |

*Latencia: 0.944 s · tokens: 2203 entrada / 90 salida*

### `pol-pagos-01` · E8:dentro_alcance · **hibrida:anthropic**

**Consulta:** ¿Puedo pagar en efectivo cuando me llegue el pedido?

**Respuesta:**

```text
No, EcoMarket no acepta pago contra entrega ni pagos en efectivo [Pagos y cuenta › Preguntas frecuentes › ¿Puedo pagar contra entrega?]. Puede pagar con tarjeta de crédito o débito, PSE, saldo EcoMarket o financiación en cuotas [Pagos y cuenta › Medios de pago].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 2 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:efectivo | ✓ | ok |

*Latencia: 0.96 s · tokens: 2498 entrada / 131 salida*

### `pol-pagos-02` · E8:dentro_alcance · **hibrida:anthropic**

**Consulta:** ¿Puedo usar dos cupones en una sola compra?

**Respuesta:**

```text
No, solo se puede usar un cupón por compra y no se acumula con otras promociones [Pagos y cuenta › Preguntas frecuentes › ¿Puedo usar dos cupones en la misma compra?] [Pagos y cuenta › Cupones de descuento]. Además, cada cupón tiene fecha de vencimiento [Pagos y cuenta › Cupones de descuento].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 3 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:un cupón | ✓ | ok |

*Latencia: 1.005 s · tokens: 2347 entrada / 135 salida*

### `pol-sostenibilidad-01` · E8:dentro_alcance · **hibrida:anthropic**

**Consulta:** ¿Qué hago con los frascos de vidrio vacíos?

**Respuesta:**

```text
Puede devolver los frascos de vidrio vacíos con el programa de reciclaje de envases: entréguelos al transportador en su siguiente entrega o en un punto aliado. EcoMarket los limpia y los reutiliza o los envía a reciclaje certificado. Por cada 5 envases devueltos recibe un cupón del 10% de descuento para su siguiente compra [Sostenibilidad › Programa de reciclaje de envases].

Tenga en cuenta que el programa solo recibe envases de vidrio y de productos a granel comprados en EcoMarket [Sostenibilidad › Preguntas frecuentes › ¿Puedo devolver envases de productos que no compré en EcoMarket?].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 2 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:10% | ✓ | ok |

*Latencia: 1.429 s · tokens: 2533 entrada / 244 salida*

### `pol-sostenibilidad-02` · E8:dentro_alcance · **hibrida:anthropic**

**Consulta:** ¿Los empaques de los pedidos tienen plástico?

**Respuesta:**

```text
No, los empaques de los pedidos no tienen plástico: se envían en cajas de cartón reciclado, con relleno de papel y cinta de papel kraft, y EcoMarket no usa plástico de un solo uso en sus empaques [Sostenibilidad › Preguntas frecuentes › ¿Los empaques de los pedidos tienen plástico?]. Las cintas de cierre son de papel kraft con adhesivo a base de agua [Sostenibilidad › Empaques].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 2 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:cartón | ✓ | ok |

*Latencia: 1.461 s · tokens: 2299 entrada / 167 salida*

### `pol-devoluciones-01` · E8:dentro_alcance · **hibrida:anthropic**

**Consulta:** ¿En cuánto tiempo me reembolsan si pagué con PSE?

**Respuesta:**

```text
Si pagó con PSE, el reembolso se emite al mismo medio de pago en un plazo de 3 a 5 días hábiles, una vez verificado el producto en bodega [Devoluciones y garantías › Tiempos de reembolso]. Esto también aparece en las preguntas frecuentes [Devoluciones y garantías › Preguntas frecuentes › ¿Me devuelven el dinero o me dan un cupón?].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 2 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:3 a 5 días hábiles | ✓ | ok |

*Latencia: 1.103 s · tokens: 2785 entrada / 149 salida*

### `cred-01` · E8:dentro_alcance · **hibrida:anthropic**

**Consulta:** ¿Cuál es el monto mínimo para pagar a cuotas?

**Respuesta:**

```text
El monto mínimo para financiar en cuotas es de 200.000 pesos, calculado después de aplicar los cupones de descuento. El costo del envío no cuenta para alcanzar ese mínimo [Reglas de crédito › CR-05 · Monto mínimo financiable].

Para revisar el costo total de su compra y el número de cuotas disponibles, puede usar el simulador en la página de pago. Si tiene dudas sobre financiación, también puedo comunicarle con un asesor de financiación.
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 1 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| cifras_con_respaldo | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:200.000 | ✓ | ok |

*Latencia: 1.316 s · tokens: 2845 entrada / 173 salida*

### `cred-02` · E8:dentro_alcance · **hibrida:anthropic**

**Consulta:** Si me atraso en una cuota, ¿me reportan de una vez a las centrales de riesgo?

**Respuesta:**

```text
No, no de inmediato. Antes de reportar información negativa a una central de riesgo, EcoMarket le envía una comunicación previa para que pueda pagar o controvertir la deuda, y el reporte solo puede hacerse después de 20 días calendario desde el envío de esa comunicación. Si paga la cuota vencida dentro de ese plazo, no se hace el reporte negativo [Reglas de crédito › CR-14 · Aviso previo antes de reportar a centrales de riesgo].

Además, si la cuota no se paga a más tardar en su fecha límite, la cuenta entra en mora desde el día siguiente y se cobra interés de mora [Reglas de crédito › CR-13 · Mora e intereses de mora].

Para conocer el estado de su crédito, puede consultarlo en la sección "Mis créditos" de su cuenta. Si tiene dudas, puedo comunicarle con un agente humano.
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 2 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| cifras_con_respaldo | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:20 días | ✓ | ok |

*Latencia: 1.746 s · tokens: 2930 entrada / 316 salida*

### `cred-03` · E8:dentro_alcance · **hibrida:anthropic**

**Consulta:** ¿Puedo pagar todo el crédito antes de tiempo?

**Respuesta:**

```text
Sí, puede pagar por anticipado una parte o la totalidad de su compra financiada en cualquier momento, sin penalidad, como lo establece la Ley 1555 de 2012 [Reglas de crédito › CR-10 · Pago anticipado]. Si hace un abono parcial, usted decide si este reduce el número de cuotas o el valor de cada cuota [Reglas de crédito › CR-10 · Pago anticipado].

Para revisar el costo total de su caso, puede usar el simulador de la página de pago. Si desea más orientación, puedo comunicarle con un asesor de financiación.
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 2 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| cifras_con_respaldo | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:sin penalidad | ✓ | ok |

*Latencia: 1.414 s · tokens: 2919 entrada / 208 salida*

