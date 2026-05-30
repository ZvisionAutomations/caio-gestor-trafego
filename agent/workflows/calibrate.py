"""Workflow: safe threshold self-improvement proposals for Caio."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .analyze import AnalysisResult

_DEFAULT_SETTINGS = Path(__file__).parent.parent.parent / "config" / "settings.yaml"


@dataclass
class ThresholdProposal:
    approved_for_auto_apply: bool
    blocked_reason: str
    sample_clicks: int
    confidence: float
    current_thresholds: dict[str, float] = field(default_factory=dict)
    proposed_thresholds: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def has_proposal(self) -> bool:
        return not self.blocked_reason and bool(self.proposed_thresholds)

    def render_message(self) -> str:
        if self.blocked_reason:
            return (
                "Caio - Self-improvement\n"
                f"Proposta bloqueada: {self.blocked_reason}\n"
                f"Amostra: {self.sample_clicks} cliques. Thresholds mantidos."
            )

        lines = [
            "Caio - Proposta de Recalibracao",
            f"Amostra: {self.sample_clicks} cliques",
            f"Confianca: {self.confidence:.0%}",
            "Modo: proposta manual, sem auto-aplicar",
            "",
            "Thresholds sugeridos:",
        ]
        for key, value in self.proposed_thresholds.items():
            current = self.current_thresholds.get(key)
            lines.append(f"- {key}: {current} -> {value}")
        if self.notes:
            lines.append("")
            lines.append("Notas:")
            lines.extend(f"- {note}" for note in self.notes)
        lines.append("")
        lines.append("Kaue/Fernando: aprovar manualmente antes de qualquer mudanca em settings.yaml.")
        return "\n".join(lines)


class CalibrationWorkflow:
    """Builds conservative threshold proposals without writing config files."""

    def __init__(self, settings_path: Path | None = None) -> None:
        self.settings_path = settings_path or _DEFAULT_SETTINGS
        self._cfg = self._load_settings(self.settings_path)
        self._thresholds = self._cfg.get("thresholds", {})
        self._calibration = self._cfg.get("calibration", {})

    def build_proposal(self, analysis: AnalysisResult) -> ThresholdProposal:
        min_clicks = int(self._thresholds.get("min_clicks_to_act", 50))
        min_data_points = int(self._calibration.get("min_data_points", 500))

        eligible = [
            item.metrics
            for item in analysis.ad_sets
            if item.metrics.clicks >= min_clicks and item.metrics.cpl > 0 and item.metrics.ctr > 0
        ]
        sample_clicks = sum(item.clicks for item in eligible)

        current = {
            "cpl_max": float(self._thresholds.get("cpl_max", 35.0)),
            "cpl_alert": float(self._thresholds.get("cpl_alert", 25.0)),
            "ctr_min": float(self._thresholds.get("ctr_min", 1.5)),
        }

        if sample_clicks < min_data_points:
            return ThresholdProposal(
                approved_for_auto_apply=False,
                blocked_reason=f"dados insuficientes ({sample_clicks} < {min_data_points} cliques)",
                sample_clicks=sample_clicks,
                confidence=0.0,
                current_thresholds=current,
            )

        cpls = sorted(item.cpl for item in eligible)
        ctrs = sorted(item.ctr for item in eligible)

        proposed_cpl_max = _clamp_delta(
            current["cpl_max"],
            round(_percentile(cpls, 75), 2),
            max_delta_pct=0.20,
        )
        proposed_cpl_alert = min(
            round(proposed_cpl_max * 0.72, 2),
            proposed_cpl_max - 1.0,
        )
        proposed_ctr_min = _clamp_delta(
            current["ctr_min"],
            round(_percentile(ctrs, 25), 2),
            max_delta_pct=0.20,
        )

        confidence = min(0.9, 0.55 + (sample_clicks / max(min_data_points, 1)) * 0.15)
        return ThresholdProposal(
            approved_for_auto_apply=False,
            blocked_reason="",
            sample_clicks=sample_clicks,
            confidence=confidence,
            current_thresholds=current,
            proposed_thresholds={
                "cpl_max": proposed_cpl_max,
                "cpl_alert": proposed_cpl_alert,
                "ctr_min": proposed_ctr_min,
            },
            notes=[
                "frequency_pause mantido fixo no MVP",
                "proposta limitada a 20% de variacao por ciclo",
                "nenhum arquivo de configuracao foi alterado",
            ],
        )

    @staticmethod
    def _load_settings(settings_path: Path) -> dict[str, Any]:
        with open(settings_path, encoding="utf-8") as f:
            return yaml.safe_load(f)


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    rank = (len(values) - 1) * (percentile / 100)
    lower = int(rank)
    upper = min(lower + 1, len(values) - 1)
    weight = rank - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def _clamp_delta(current: float, proposed: float, max_delta_pct: float) -> float:
    lower = current * (1 - max_delta_pct)
    upper = current * (1 + max_delta_pct)
    return round(max(lower, min(upper, proposed)), 2)
