# Indexación — gemini (gemini-embedding-001, 768 dim)

**Fecha:** 2026-10-14 · **Tabla:** `kb_gemini_768_enriq` · **Estrategia:** `por_tipo`

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
| Tokens aproximados | 9925 |
| Tiempo total (s) | 1.99 |
| Índice | HNSW coseno (kb_gemini_768_enriq_hnsw) |

## Consultas de humo (una por tipo de documento, sin filtro, top-1)

| Tipo esperado | Pregunta | Tipo obtenido | Fuente | Similitud | OK |
|---|---|---|---|---:|:--:|
| politicas | ¿Cuántos días tengo para devolver un producto? | politicas | Devoluciones y garantías › Preguntas frecuentes › ¿Cuánto tiempo tengo para devolver un producto? | 0.8114 | ✓ |
| credito | ¿Cuál es el monto mínimo para financiar una compra en cuotas? | credito | Reglas de crédito › CR-05 · Monto mínimo financiable | 0.7886 | ✓ |
| producto | ¿El vaso de vidrio se puede lavar en el lavavajillas? | producto | Catálogo › P-108 · Vaso de vidrio con tapa de bambú 500 ml | 0.6981 | ✓ |
| terminos | ¿En cuánto tiempo llega la factura electrónica? | terminos | Términos y condiciones › página 1 | 0.7383 | ✓ |
