# CLAUDE.md

Repositorio de talleres del curso IA Generativa. Entrega individual, en español.

- Estructura: `packages/genai_common` (librería compartida) + `taller-NN-<slug>/` (uno por taller), en la raíz del repo.
- Gestor: uv workspace. Comandos: `uv sync --all-groups`, `uv run pytest`, `uv run ruff check .`.
- LLMs: solo a través de `genai_common.LLMClient`; los IDs de modelo viven solo en `providers.toml`.
  Proveedor por defecto: gemini (tier gratuito). Alternativa ejecutada: anthropic (de pago).
  Ollama: perfil definido, por implementar.
- Idioma: docs, prompts y mensajes en español; identificadores de código en inglés.
- Tests sin red (proveedor `fake`). Nunca commitear `.env` ni keys. Datos siempre sintéticos y sin PII.
- Cada taller: `docs/` (fases en Markdown), `data/`, `prompts/` (TOML), `src/`, `notebooks/`, `outputs/` (evidencia), `tests/`.
- Ante decisiones de contenido académico (qué argumentar), consultar siempre al usuario.
  Los documentos de planificación de cada taller son locales y no se versionan (ver .git/info/exclude).
- No inventar resultados: las tablas de los documentos deben venir de ejecuciones reales guardadas en `outputs/`.
