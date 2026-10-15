# Calibración del umbral de abstención — embeddinggemma

**Fecha:** 2026-10-14

> Generado por `taller02 evaluar`/`calibrar`. No editar a mano: es la evidencia de una ejecución real.

## Resultado

- **Umbral propuesto:** 0.4048
- **Exactitud abstenerse/responder:** 0.947
- **Translingües que se abstendrían:** 0

## Histograma (D=dentro, F=fuera, T=translingüe)

```text
0.10-0.15 | F
0.20-0.25 | FF
0.35-0.40 | F
0.40-0.45 | DDD ← umbral
0.45-0.50 | DDDDDDDDDF
0.50-0.55 | DDDDDDDDFT
0.55-0.60 | DDDDDDDDTT
0.60-0.65 | DDT
0.70-0.75 | D
0.75-0.80 | D
```

## Mejor score por caso

| Grupo | Caso | Score |
|---|---|---:|
| dentro | pol-envios-01 | 0.5926 |
| dentro | pol-envios-02 | 0.5038 |
| dentro | pol-pagos-01 | 0.5391 |
| dentro | pol-pagos-02 | 0.7535 |
| dentro | pol-sostenibilidad-01 | 0.5078 |
| dentro | pol-sostenibilidad-02 | 0.7059 |
| dentro | pol-devoluciones-01 | 0.5964 |
| dentro | cred-01 | 0.5788 |
| dentro | cred-02 | 0.5445 |
| dentro | cred-03 | 0.5517 |
| dentro | cred-04 | 0.5696 |
| dentro | cred-05 | 0.5815 |
| dentro | cat-01 | 0.4875 |
| dentro | cat-02 | 0.4733 |
| dentro | cat-03 | 0.4908 |
| dentro | cat-04 | 0.6108 |
| dentro | ter-01 | 0.4922 |
| dentro | ter-02 | 0.4431 |
| dentro | ter-03 | 0.4347 |
| dentro | ter-04 | 0.4463 |
| dentro | ter-05 | 0.4710 |
| dentro | mixto-01 | 0.5492 |
| dentro | mixto-02 | 0.5041 |
| dentro | mixto-03 | 0.5935 |
| dentro | iny-01 | 0.5307 |
| dentro | iny-02 | 0.4546 |
| dentro | reform-01 | 0.5127 |
| dentro | reform-02 | 0.5622 |
| dentro | reform-03 | 0.4781 |
| dentro | trampa-01 | 0.4534 |
| dentro | trampa-02 | 0.6152 |
| dentro | trampa-03 | 0.4671 |
| fuera | fuera-01 | 0.5013 |
| fuera | fuera-03 | 0.3750 |
| fuera | fuera-04 | 0.2314 |
| fuera | fuera-05 | 0.4558 |
| fuera | fuera-06 | 0.2088 |
| fuera | fuera-07 | 0.1393 |
| translingue | transl-01 | 0.5839 |
| translingue | transl-02 | 0.5334 |
| translingue | transl-03 | 0.5622 |
| translingue | transl-04 | 0.6257 |
