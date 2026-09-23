# Talleres de GenAI — Inteligencia Artificial Generativa

Talleres de trabajo del curso de Inteligencia Artificial Generativa (GenAI). Desarrollo estos
talleres de manera individual con apoyo de asistentes de código como Claude Code y Antigravity
(Gemini), como ejercicio de aprendizaje de estas herramientas para estudio y productividad.

El repositorio es un monorepo: cada taller es un paquete independiente que comparte una librería
común (`genai_common`) para comunicación con los modelos de lenguaje via APIs.

## Talleres

| # | Taller | Caso | Estado | Carpeta |
|---|---|---|---|---|
| 1 | Selección de modelo e ingeniería de prompts | EcoMarket · atención al cliente | En desarrollo | [`taller-01-ecomarket/`](taller-01-ecomarket/) |

## Estructura

```
.
├── providers.toml          # única fuente de verdad de los IDs de modelo
├── packages/genai_common/  # cliente de LLM, prompts, registro de ejecuciones, proveedor fake
├── taller-01-ecomarket/    # taller 1
└── .github/workflows/      # CI: ruff + pytest sin claves
```
