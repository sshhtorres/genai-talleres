# Indexación — embeddinggemma (embeddinggemma:300m, 768 dim)

**Fecha:** 2026-10-14 · **Tabla:** `kb_embeddinggemma_768_fija1000` · **Estrategia:** `fija1000`

> Generado por `taller02 indexar`. No editar a mano: es la evidencia de una ejecución real.

| Métrica | Valor |
|---|---:|
| Chunks | 39 |
| · credito | 8 |
| · politicas | 16 |
| · producto | 10 |
| · terminos | 5 |
| Agregados (embebidos en esta corrida) | 39 |
| Eliminados (ya no existen) | 0 |
| Sin cambios | 0 |
| Tokens aproximados | 9103 |
| Tiempo total (s) | 362.83 |
| Índice | HNSW coseno (kb_embeddinggemma_768_fija1000_hnsw) |

## Consultas de humo (una por tipo de documento, sin filtro, top-1)

| Tipo esperado | Pregunta | Tipo obtenido | Fuente | Similitud | OK |
|---|---|---|---|---:|:--:|
| politicas | ¿Cuántos días tengo para devolver un producto? | politicas | politicas-y-faq | 0.5948 | ✓ |
| credito | ¿Cuál es el monto mínimo para financiar una compra en cuotas? | credito | reglas-credito | 0.5988 | ✓ |
| producto | ¿El vaso de vidrio se puede lavar en el lavavajillas? | producto | catalogo | 0.3926 | ✓ |
| terminos | ¿En cuánto tiempo llega la factura electrónica? | terminos | terminos-y-condiciones | 0.3865 | ✓ |
