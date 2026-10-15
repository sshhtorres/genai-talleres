# Indexación — embeddinggemma (embeddinggemma:300m, 768 dim)

**Fecha:** 2026-10-14 · **Tabla:** `kb_embeddinggemma_768_fija300` · **Estrategia:** `fija300`

> Generado por `taller02 indexar`. No editar a mano: es la evidencia de una ejecución real.

| Métrica | Valor |
|---|---:|
| Chunks | 124 |
| · credito | 27 |
| · politicas | 51 |
| · producto | 31 |
| · terminos | 15 |
| Agregados (embebidos en esta corrida) | 124 |
| Eliminados (ya no existen) | 0 |
| Sin cambios | 0 |
| Tokens aproximados | 9086 |
| Tiempo total (s) | 493.84 |
| Índice | HNSW coseno (kb_embeddinggemma_768_fija300_hnsw) |

## Consultas de humo (una por tipo de documento, sin filtro, top-1)

| Tipo esperado | Pregunta | Tipo obtenido | Fuente | Similitud | OK |
|---|---|---|---|---:|:--:|
| politicas | ¿Cuántos días tengo para devolver un producto? | politicas | politicas-y-faq | 0.5716 | ✓ |
| credito | ¿Cuál es el monto mínimo para financiar una compra en cuotas? | credito | reglas-credito | 0.6422 | ✓ |
| producto | ¿El vaso de vidrio se puede lavar en el lavavajillas? | producto | catalogo | 0.4649 | ✓ |
| terminos | ¿En cuánto tiempo llega la factura electrónica? | terminos | terminos-y-condiciones | 0.3927 | ✓ |
