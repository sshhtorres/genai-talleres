# Resultados — hibrida-gemini (embeddinggemma:300m + gemini-3.5-flash-lite)

**Fecha de ejecución:** 2026-10-14  
**Proveedor:** `hibrida-gemini` · **Modelo:** `embeddinggemma:300m + gemini-3.5-flash-lite`  
**Casos ejecutados:** 10 · **Con todos los chequeos en verde:** 9/10

> Generado automáticamente por `genai_common.runs.RunRecorder`. No editar a mano: es la evidencia de una ejecución real.

## Resumen por variante

| Variante | Casos | Chequeos OK | % |
|---|---:|---:|---:|
| hibrida:gemini | 10 | 9 | 90% |

## Detalle por caso

### `pol-envios-01` · E8:dentro_alcance · **hibrida:gemini**

**Consulta:** ¿Cuánto cuesta el envío y desde qué monto es gratis?

**Respuesta:**

```text
El costo del envío depende de la ciudad de destino y se muestra antes de pagar [Envíos › Preguntas frecuentes › ¿Cuánto cuesta el envío?]. El envío es gratis en compras de 150.000 pesos o más, después de aplicar los cupones [Envíos › Preguntas frecuentes › ¿Cuánto cuesta el envío?].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 2 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:150.000 | ✓ | ok |

*Latencia: 0.882 s · tokens: 1349 entrada / 74 salida*

### `pol-envios-02` · E8:dentro_alcance · **hibrida:gemini**

**Consulta:** ¿Hacen envíos a otros países?

**Respuesta:**

```text
No, por ahora EcoMarket solo realiza envíos dentro del territorio colombiano y no hay envíos internacionales [Envíos › Preguntas frecuentes › ¿Hacen envíos fuera de Colombia?], [Envíos › Cobertura].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 2 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:Colombia | ✓ | ok |

*Latencia: 0.829 s · tokens: 1273 entrada / 48 salida*

### `pol-pagos-01` · E8:dentro_alcance · **hibrida:gemini**

**Consulta:** ¿Puedo pagar en efectivo cuando me llegue el pedido?

**Respuesta:**

```text
No, no puede pagar en efectivo ni contra entrega [Pagos y cuenta › Preguntas frecuentes › ¿Puedo pagar contra entrega?]. Los medios de pago aceptados son tarjeta de crédito o débito, PSE, saldo EcoMarket y financiación en cuotas [Pagos y cuenta › Preguntas frecuentes › ¿Puedo pagar contra entrega?].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 2 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:efectivo | ✓ | ok |

*Latencia: 0.709 s · tokens: 1423 entrada / 70 salida*

### `pol-pagos-02` · E8:dentro_alcance · **hibrida:gemini**

**Consulta:** ¿Puedo usar dos cupones en una sola compra?

**Respuesta:**

```text
No, solo se puede usar un cupón por compra [Pagos y cuenta › Preguntas frecuentes › ¿Puedo usar dos cupones en la misma compra?]. Además, tenga en cuenta que los cupones no se acumulan con otras promociones [Pagos y cuenta › Cupones de descuento].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 2 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:un cupón | ✓ | ok |

*Latencia: 0.708 s · tokens: 1372 entrada / 65 salida*

### `pol-sostenibilidad-01` · E8:dentro_alcance · **hibrida:gemini**

**Consulta:** ¿Qué hago con los frascos de vidrio vacíos?

**Respuesta:**

```text
Puede devolver los envases vacíos de vidrio (siempre que hayan sido comprados en EcoMarket) entregándoselos al transportador en su siguiente entrega o en un punto aliado [Sostenibilidad › Preguntas frecuentes › ¿Qué hago con los envases vacíos?], [Sostenibilidad › Programa de reciclaje de envases], [Sostenibilidad › Preguntas frecuentes › ¿Puedo devolver envases de productos que no compré en EcoMarket?]. Por cada 5 envases devueltos, usted recibirá un cupón del 10% de descuento para su próxima compra [Sostenibilidad › Preguntas frecuentes › ¿Qué hago con los envases vacíos?].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 4 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:10% | ✓ | ok |

*Latencia: 0.867 s · tokens: 1491 entrada / 141 salida*

### `pol-sostenibilidad-02` · E8:dentro_alcance · **hibrida:gemini**

**Consulta:** ¿Los empaques de los pedidos tienen plástico?

**Respuesta:**

```text
No, los pedidos se envían en cajas de cartón reciclado y con relleno de papel [Sostenibilidad › Preguntas frecuentes › ¿Los empaques de los pedidos tienen plástico?], [Sostenibilidad › Empaques]. EcoMarket no usa plástico de un solo uso en sus empaques [Sostenibilidad › Preguntas frecuentes › ¿Los empaques de los pedidos tienen plástico?], [Sostenibilidad › Empaques]. Las cintas de cierre son de papel kraft [Sostenibilidad › Preguntas frecuentes › ¿Los empaques de los pedidos tienen plástico?] con adhesivo a base de agua [Sostenibilidad › Empaques].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 6 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:cartón | ✓ | ok |

*Latencia: 0.821 s · tokens: 1331 entrada / 138 salida*

### `pol-devoluciones-01` · E8:dentro_alcance · **hibrida:gemini**

**Consulta:** ¿En cuánto tiempo me reembolsan si pagué con PSE?

**Respuesta:**

```text
Si pagó con transferencia o PSE, el tiempo estimado para el reembolso es de 3 a 5 días hábiles [Devoluciones y garantías › Tiempos de reembolso] [Devoluciones y garantías › Preguntas frecuentes › ¿Me devuelven el dinero o me dan un cupón?].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 2 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:3 a 5 días hábiles | ✓ | ok |

*Latencia: 0.701 s · tokens: 1638 entrada / 63 salida*

### `cred-01` · E8:dentro_alcance · **hibrida:gemini**

**Consulta:** ¿Cuál es el monto mínimo para pagar a cuotas?

**Respuesta:**

```text
El monto mínimo para financiar compras es de 200.000 pesos, después de aplicar los cupones de descuento, y el costo del envío no cuenta para alcanzar dicho monto [Reglas de crédito › CR-05 · Monto mínimo financiable].
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

*Latencia: 0.718 s · tokens: 1708 entrada / 56 salida*

### `cred-02` · E8:dentro_alcance · **hibrida:gemini**

**Consulta:** Si me atraso en una cuota, ¿me reportan de una vez a las centrales de riesgo?

**Respuesta:**

```text
No, antes de reportar información negativa a una central de riesgo, EcoMarket envía una comunicación previa para que usted pueda pagar o controvertir la deuda [Reglas de crédito › CR-14 · Aviso previo antes de reportar a centrales de riesgo]. El reporte solo puede realizarse después de 20 días calendario contados a partir del envío de dicha comunicación [Reglas de crédito › CR-14 · Aviso previo antes de reportar a centrales de riesgo].
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

*Latencia: 0.802 s · tokens: 1731 entrada / 97 salida*

### `cred-03` · E8:dentro_alcance · **hibrida:gemini**

**Consulta:** ¿Puedo pagar todo el crédito antes de tiempo?

**Respuesta:**

```text
Sí, usted puede pagar por anticipado una parte o la totalidad de su compra financiada en cualquier momento, sin ninguna penalidad [Reglas de crédito › CR-10 · Pago anticipado].
```

| Chequeo | Resultado | Detalle |
|---|:--:|---|
| cita_una_fuente | ✓ | 1 cita(s) válidas |
| sin_datos_de_pedidos | ✓ | ok |
| cifras_con_respaldo | ✓ | ok |
| respuesta_completa | ✓ | ok |
| no_se_abstiene_sin_motivo | ✓ | ok |
| responde_en_el_idioma_del_cliente | ✓ | detectado 'es', esperado 'es' |
| contiene:sin penalidad | ✗ | ausente |

*Latencia: 0.659 s · tokens: 1720 entrada / 41 salida*

