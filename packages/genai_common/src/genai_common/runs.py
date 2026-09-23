"""Registro de ejecuciones: JSONL + reporte Markdown como evidencia."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

Check = tuple[str, bool, str]  # (nombre, ok, detalle)


@dataclass
class RunRecord:
    """Una ejecución: un caso, una variante, un proveedor."""

    caso_id: str
    ejercicio: str
    variante: str
    mensaje: str
    respuesta: str
    checks: list[Check] = field(default_factory=list)
    metadatos: dict[str, Any] = field(default_factory=dict)
    pasos: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(ok for _, ok, _ in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "caso_id": self.caso_id,
            "ejercicio": self.ejercicio,
            "variante": self.variante,
            "mensaje": self.mensaje,
            "respuesta": self.respuesta,
            "checks": [{"nombre": n, "ok": o, "detalle": d} for n, o, d in self.checks],
            "metadatos": self.metadatos,
            "pasos": self.pasos,
        }


class RunRecorder:
    """Acumula ejecuciones y las escribe en outputs/<fecha>_<proveedor>.{jsonl,md}."""

    def __init__(
        self,
        outputs_dir: str | Path,
        proveedor: str,
        modelo: str,
        fecha: str | None = None,
        etiqueta: str = "resultados",
    ) -> None:
        self.dir = Path(outputs_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.proveedor = proveedor
        self.modelo = modelo
        self.fecha = fecha or date.today().isoformat()
        self.etiqueta = etiqueta
        self.records: list[RunRecord] = []

    @property
    def base(self) -> Path:
        return self.dir / f"{self.etiqueta}_{self.fecha}_{self.proveedor}"

    def add(self, record: RunRecord) -> None:
        self.records.append(record)

    def write(self) -> tuple[Path, Path]:
        """Escribe el JSONL y el reporte Markdown. Devuelve ambas rutas."""
        jsonl = self.base.with_suffix(".jsonl")
        with jsonl.open("w", encoding="utf-8") as fh:
            for record in self.records:
                fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

        md = self.base.with_suffix(".md")
        md.write_text(self._markdown(), encoding="utf-8")
        return jsonl, md

    # -- reporte ---------------------------------------------------------

    def _markdown(self) -> str:
        total = len(self.records)
        verdes = sum(1 for r in self.records if r.ok)
        lineas = [
            f"# Resultados — {self.proveedor} ({self.modelo})",
            "",
            f"**Fecha de ejecución:** {self.fecha}  ",
            f"**Proveedor:** `{self.proveedor}` · **Modelo:** `{self.modelo}`  ",
            f"**Casos ejecutados:** {total} · "
            f"**Con todos los chequeos en verde:** {verdes}/{total}",
            "",
            "> Generado automáticamente por `genai_common.runs.RunRecorder`. "
            "No editar a mano: es la evidencia de una ejecución real.",
            "",
            "## Resumen por variante",
            "",
            "| Variante | Casos | Chequeos OK | % |",
            "|---|---:|---:|---:|",
        ]
        for variante in sorted({r.variante for r in self.records}):
            subset = [r for r in self.records if r.variante == variante]
            ok = sum(1 for r in subset if r.ok)
            pct = f"{100 * ok / len(subset):.0f}%" if subset else "—"
            lineas.append(f"| {variante} | {len(subset)} | {ok} | {pct} |")

        lineas += ["", "## Detalle por caso", ""]
        for record in self.records:
            lat = record.metadatos.get("latencia_s", "—")
            lineas += [
                f"### `{record.caso_id}` · {record.ejercicio} · **{record.variante}**",
                "",
                f"**Consulta:** {record.mensaje}",
                "",
                "**Respuesta:**",
                "",
                "```text",
                record.respuesta.strip() or "(vacía)",
                "```",
                "",
                "| Chequeo | Resultado | Detalle |",
                "|---|:--:|---|",
            ]
            if record.checks:
                for nombre, ok, detalle in record.checks:
                    lineas.append(f"| {nombre} | {'✓' if ok else '✗'} | {detalle} |")
            else:
                lineas.append("| (sin chequeos) | — | |")
            lineas += ["", f"*Latencia: {lat} s · {self._tokens(record)}*", ""]

        return "\n".join(lineas) + "\n"

    @staticmethod
    def _tokens(record: RunRecord) -> str:
        entrada = record.metadatos.get("tokens_entrada")
        salida = record.metadatos.get("tokens_salida")
        if entrada is None and salida is None:
            return "tokens: no reportados"
        return f"tokens: {entrada} entrada / {salida} salida"
