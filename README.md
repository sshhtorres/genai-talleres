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

## Puesta en marcha

Requisitos: [uv](https://docs.astral.sh/uv/) y Python 3.12 (uv lo descarga si no está).

```bash
git clone <url-del-repo> && cd talleres
uv sync --all-groups          # crea el entorno e instala todo el workspace
cp .env.example .env          # y completa al menos GEMINI_API_KEY
uv run taller01 proveedores   # verifica qué claves están configuradas
```

Dónde conseguir las claves:

| Proveedor | Variable | Dónde | Costo |
|---|---|---|---|
| Google Gemini | `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) | Tier gratuito |
| Anthropic | `ANTHROPIC_API_KEY` | [Consola de Anthropic](https://console.anthropic.com/settings/keys) | De pago |

> El tier gratuito de Gemini usa el contenido enviado para mejorar los productos de Google. Por eso
> **todos los datos de estos talleres son sintéticos**; nunca se envía información real de personas.

Comandos habituales:

```bash
uv run pytest                              # tests, sin red (proveedor fake)
uv run ruff check . && uv run ruff format --check .
uv run --group notebooks jupyter lab       # notebooks de demostración
uv run taller01 --help                     # CLI del taller 1
```

## Convenciones

- Documentos, prompts y mensajes al usuario en **español**; identificadores de código en **inglés**.
- Los IDs de modelo viven **solo** en `providers.toml`. Si una llamada devuelve 404, se actualiza
  ese archivo, nunca el código.
- Los secretos van solo en `.env` (ignorado por git). Los datos de los talleres son sintéticos.
- Los resultados de `outputs/` provienen de ejecuciones reales: no se editan a mano.
