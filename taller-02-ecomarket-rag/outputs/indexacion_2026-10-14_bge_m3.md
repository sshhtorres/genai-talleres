# Indexación — bge_m3 (bge-m3, 1024 dim)

**Fecha:** 2026-10-14 · **Tabla:** `kb_bge_m3_1024` · **Estrategia:** `por_tipo`

> Generado por `taller02 indexar`. No editar a mano: es la evidencia de una ejecución real.

| Métrica | Valor |
|---|---:|
| Chunks | 89 |
| · credito | 18 |
| · politicas | 49 |
| · producto | 15 |
| · terminos | 7 |
| Agregados (embebidos en esta corrida) | 89 |
| Eliminados (ya no existen) | 0 |
| Sin cambios | 0 |
| Tokens aproximados | 9491 |
| Tiempo total (s) | 23.64 |
| Índice | HNSW coseno (kb_bge_m3_1024_hnsw) |

## Consultas de humo (una por tipo de documento, sin filtro, top-1)

| Tipo esperado | Pregunta | Tipo obtenido | Fuente | Similitud | OK |
|---|---|---|---|---:|:--:|
| politicas | ¿Cuántos días tengo para devolver un producto? | politicas | Devoluciones y garantías › Preguntas frecuentes › ¿Cuánto tiempo tengo para devolver un producto? | 0.7698 | ✓ |
| credito | ¿Cuál es el monto mínimo para financiar una compra en cuotas? | credito | Reglas de crédito › CR-06 · Número de cuotas según el monto | 0.6919 | ✓ |
| producto | ¿El vaso de vidrio se puede lavar en el lavavajillas? | producto | Catálogo › P-108 · Vaso de vidrio con tapa de bambú 500 ml | 0.6155 | ✓ |
| terminos | ¿En cuánto tiempo llega la factura electrónica? | terminos | Términos y condiciones › página 1 | 0.7101 | ✓ |
