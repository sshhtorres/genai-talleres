# Calibración del umbral de abstención — gemini

**Fecha:** 2026-10-14

> Generado por `taller02 evaluar`/`calibrar`. No editar a mano: es la evidencia de una ejecución real.

## Resultado

- **Umbral propuesto:** 0.6681
- **Exactitud abstenerse/responder:** 0.947
- **Translingües que se abstendrían:** 0
- Algún caso translingüe puntúa por debajo de un caso fuera de alcance: no existe un umbral que separe todo. Se prioriza no abstenerse en los translingües.

## Histograma (D=dentro, F=fuera, T=translingüe)

```text
0.50-0.55 | F
0.55-0.60 | F
0.60-0.65 | F
0.65-0.70 | DDDFT ← umbral
0.70-0.75 | DDDDDDDDDDDDDDDDDDFFTT
0.75-0.80 | DDDDDDDDDT
0.80-0.85 | DD
```

## Mejor score por caso

| Grupo | Caso | Score |
|---|---|---:|
| dentro | pol-envios-01 | 0.7896 |
| dentro | pol-envios-02 | 0.7530 |
| dentro | pol-pagos-01 | 0.7460 |
| dentro | pol-pagos-02 | 0.8404 |
| dentro | pol-sostenibilidad-01 | 0.7233 |
| dentro | pol-sostenibilidad-02 | 0.8232 |
| dentro | pol-devoluciones-01 | 0.7697 |
| dentro | cred-01 | 0.7724 |
| dentro | cred-02 | 0.7290 |
| dentro | cred-03 | 0.7555 |
| dentro | cred-04 | 0.7534 |
| dentro | cred-05 | 0.7765 |
| dentro | cat-01 | 0.7078 |
| dentro | cat-02 | 0.7223 |
| dentro | cat-03 | 0.7108 |
| dentro | cat-04 | 0.7508 |
| dentro | ter-01 | 0.7404 |
| dentro | ter-02 | 0.7010 |
| dentro | ter-03 | 0.7332 |
| dentro | ter-04 | 0.7230 |
| dentro | ter-05 | 0.6837 |
| dentro | mixto-01 | 0.7352 |
| dentro | mixto-02 | 0.7471 |
| dentro | mixto-03 | 0.7418 |
| dentro | iny-01 | 0.7481 |
| dentro | iny-02 | 0.6943 |
| dentro | reform-01 | 0.7971 |
| dentro | reform-02 | 0.7419 |
| dentro | reform-03 | 0.7458 |
| dentro | trampa-01 | 0.7292 |
| dentro | trampa-02 | 0.7302 |
| dentro | trampa-03 | 0.6888 |
| fuera | fuera-01 | 0.7359 |
| fuera | fuera-03 | 0.6524 |
| fuera | fuera-04 | 0.6247 |
| fuera | fuera-05 | 0.7023 |
| fuera | fuera-06 | 0.5736 |
| fuera | fuera-07 | 0.5473 |
| translingue | transl-01 | 0.6964 |
| translingue | transl-02 | 0.7278 |
| translingue | transl-03 | 0.7414 |
| translingue | transl-04 | 0.7661 |
