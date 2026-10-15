# Indexación — embeddinggemma (embeddinggemma:300m, 768 dim)

**Fecha:** 2026-10-14 · **Tabla:** `kb_embeddinggemma_768` · **Estrategia:** `por_tipo`

> Generado por `taller02 indexar`. No editar a mano: es la evidencia de una ejecución real.

| Métrica | Valor |
|---|---:|
| Chunks | 89 |
| · credito | 18 |
| · politicas | 49 |
| · producto | 15 |
| · terminos | 7 |
| Agregados (embebidos en esta corrida) | 0 |
| Eliminados (ya no existen) | 0 |
| Sin cambios | 89 |
| Tokens aproximados | 9491 |
| Tiempo total (s) | 0.01 |
| Índice | HNSW coseno (kb_embeddinggemma_768_hnsw) |

## Consultas de humo (una por tipo de documento, sin filtro, top-1)

| Tipo esperado | Pregunta | Tipo obtenido | Fuente | Similitud | OK |
|---|---|---|---|---:|:--:|
| politicas | ¿Cuántos días tengo para devolver un producto? | politicas | Devoluciones y garantías › Plazo para solicitar una devolución | 0.6153 | ✓ |
| credito | ¿Cuál es el monto mínimo para financiar una compra en cuotas? | credito | Reglas de crédito › CR-05 · Monto mínimo financiable | 0.6416 | ✓ |
| producto | ¿El vaso de vidrio se puede lavar en el lavavajillas? | producto | Catálogo › P-108 · Vaso de vidrio con tapa de bambú 500 ml | 0.4924 | ✓ |
| terminos | ¿En cuánto tiempo llega la factura electrónica? | terminos | Términos y condiciones › página 1 | 0.4876 | ✓ |
