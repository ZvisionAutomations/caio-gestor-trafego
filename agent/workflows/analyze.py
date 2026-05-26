"""Workflow: Ciclo de Análise — classifica cada ad set e decide próximas ações."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from ..tools.meta_ads import AdSetMetrics, MetaAdsTool

logger = logging.getLogger("caio.workflows.analyze")

_DEFAULT_SETTINGS = Path(__file__).parent.parent.parent / "config" / "settings.yaml"


class AdSetState(str, Enum):
    CHAMPION = "CHAMPION"       # CPL < R$20, ROAS > 3x, CTR > 3% — candidato a escalar
    GOOD = "GOOD"               # Dentro dos thresholds — manter
    ALERT = "ALERT"             # Zona de atenção — ajuste de bid
    CRITICAL = "CRITICAL"       # CPL acima do threshold — pausar
    INSUFFICIENT = "INSUFFICIENT"  # Menos de 50 cliques — não agir
    FATIGUED = "FATIGUED"       # Frequência > 3.5 — criativo fatigado


@dataclass
class AdSetAnalysis:
    """Resultado da análise de um ad set."""

    metrics: AdSetMetrics
    state: AdSetState
    actions_recommended: list[str] = field(default_factory=list)
    requires_approval: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Resultado completo do ciclo de análise."""

    ad_sets: list[AdSetAnalysis]
    autonomous_actions: list[dict[str, Any]]
    approval_requests: list[dict[str, Any]]
    critical_alerts: list[dict[str, Any]]
    total_spend: float
    total_leads: int
    account_cpl: float
    notes: list[str] = field(default_factory=list)


class AnalyzeWorkflow:
    """
    Ciclo de análise do Caio.
    Busca métricas, classifica cada ad set e determina ações.
    """

    def __init__(
        self,
        meta_tool: MetaAdsTool,
        settings_path: Path | None = None,
    ) -> None:
        self.meta = meta_tool
        self._cfg = self._load_settings(settings_path)
        self._thresholds = self._cfg.get("thresholds", {})
        self._budget_cfg = self._cfg.get("budget", {})
        self._champion_cfg = self._cfg.get("champion", {})

    def run(self, days: int = 7) -> AnalysisResult:
        """
        Executa o ciclo de análise completo.

        Args:
            days: Janela de dados em dias (padrão: 7)

        Returns:
            AnalysisResult com classificações e ações recomendadas
        """
        logger.info("Iniciando ciclo de análise — janela: %d dias", days)

        ad_sets = self.meta.get_ad_set_insights(days=days)
        account_insights = self.meta.get_account_insights(days=1)

        analyses: list[AdSetAnalysis] = []
        autonomous_actions: list[dict] = []
        approval_requests: list[dict] = []
        critical_alerts: list[dict] = []

        for metrics in ad_sets:
            analysis = self._classify(metrics)
            analyses.append(analysis)

            for action in analysis.actions_recommended:
                autonomous_actions.append({"adset_id": metrics.id, "action": action, "metrics": metrics})

            for req in analysis.requires_approval:
                approval_requests.append({"adset_id": metrics.id, "action": req, "metrics": metrics})

            if analysis.state == AdSetState.CRITICAL and metrics.cpl > self._thresholds.get("cpl_critical", 105.0):
                critical_alerts.append({
                    "adset_id": metrics.id,
                    "adset_name": metrics.name,
                    "cpl": metrics.cpl,
                    "threshold": self._thresholds.get("cpl_critical", 105.0),
                })

        total_spend = sum(m.metrics.spend for m in analyses)
        total_leads = sum(m.metrics.leads for m in analyses)
        account_cpl = round(total_spend / total_leads, 2) if total_leads > 0 else 0.0

        result = AnalysisResult(
            ad_sets=analyses,
            autonomous_actions=autonomous_actions,
            approval_requests=approval_requests,
            critical_alerts=critical_alerts,
            total_spend=total_spend,
            total_leads=total_leads,
            account_cpl=account_cpl,
        )

        logger.info(
            "Análise concluída — %d ad sets | gasto total: R$%.2f | leads: %d | CPL conta: R$%.2f",
            len(analyses), total_spend, total_leads, account_cpl,
        )
        return result

    def _classify(self, metrics: AdSetMetrics) -> AdSetAnalysis:
        """Classifica um ad set e determina ações recomendadas."""
        min_clicks = self._thresholds.get("min_clicks_to_act", 50)
        cpl_max = self._thresholds.get("cpl_max", 35.0)
        cpl_alert = self._thresholds.get("cpl_alert", 25.0)
        ctr_pause = self._thresholds.get("ctr_pause", 1.0)
        ctr_min = self._thresholds.get("ctr_min", 1.5)
        roas_min = self._thresholds.get("roas_min", 2.0)
        roas_bid = self._thresholds.get("roas_bid_adjust", 1.8)
        freq_pause = self._thresholds.get("frequency_pause", 3.5)
        freq_alert = self._thresholds.get("frequency_alert", 3.0)

        champion_cpl = self._champion_cfg.get("max_cpl", 20.0)
        champion_ctr = self._champion_cfg.get("min_ctr", 3.0)
        champion_roas = self._champion_cfg.get("min_roas", 3.0)
        champion_clicks = self._champion_cfg.get("min_clicks", 500)
        champion_days = self._champion_cfg.get("min_days", 3)

        actions: list[str] = []
        approvals: list[str] = []
        notes: list[str] = []

        # Dados insuficientes — não agir
        if metrics.clicks < min_clicks:
            notes.append(f"Dados insuficientes ({metrics.clicks} cliques < {min_clicks} mínimo)")
            return AdSetAnalysis(metrics=metrics, state=AdSetState.INSUFFICIENT, notes=notes)

        # Criativo fatigado — pausar anúncio (não o ad set)
        if metrics.frequency > freq_pause:
            notes.append(f"Frequência {metrics.frequency:.1f} > {freq_pause} — criativo fatigado")
            actions.append("pause_creative")
            approvals.append("request_new_creative")
            return AdSetAnalysis(
                metrics=metrics,
                state=AdSetState.FATIGUED,
                actions_recommended=actions,
                requires_approval=approvals,
                notes=notes,
            )

        # CPL crítico — pausar ad set
        if metrics.cpl > cpl_max and metrics.days_above_cpl_threshold >= 2:
            notes.append(f"CPL R${metrics.cpl:.2f} > R${cpl_max} por 2+ dias — pausa")
            actions.append("pause_ad_set")
            return AdSetAnalysis(
                metrics=metrics,
                state=AdSetState.CRITICAL,
                actions_recommended=actions,
                notes=notes,
            )

        # CTR crítico — pausar ad set
        if metrics.ctr < ctr_pause and metrics.impressions >= 1000:
            notes.append(f"CTR {metrics.ctr:.1f}% < {ctr_pause}% após {metrics.impressions:,} impressões")
            actions.append("pause_ad_set")
            return AdSetAnalysis(
                metrics=metrics,
                state=AdSetState.CRITICAL,
                actions_recommended=actions,
                notes=notes,
            )

        # Zona de atenção — ajuste de bid
        if cpl_alert <= metrics.cpl <= cpl_max:
            notes.append(f"CPL R${metrics.cpl:.2f} na zona de atenção — ajuste de bid -10%")
            actions.append("adjust_bid:-0.10")
            state = AdSetState.ALERT
        elif roas_bid <= metrics.roas < roas_min:
            notes.append(f"ROAS {metrics.roas:.1f}x abaixo do mínimo — ajuste de bid -10%")
            actions.append("adjust_bid:-0.10")
            state = AdSetState.ALERT
        elif metrics.frequency > freq_alert:
            notes.append(f"Frequência {metrics.frequency:.1f} em zona de atenção")
            state = AdSetState.ALERT
        elif metrics.ctr < ctr_min:
            notes.append(f"CTR {metrics.ctr:.1f}% abaixo do mínimo ({ctr_min}%)")
            state = AdSetState.ALERT
        elif (
            metrics.cpl < champion_cpl
            and metrics.ctr > champion_ctr
            and metrics.roas > champion_roas
            and metrics.clicks >= champion_clicks
            and metrics.days_below_champion_cpl >= champion_days
        ):
            notes.append(
                f"Ad set campeão — CPL R${metrics.cpl:.2f} | ROAS {metrics.roas:.1f}x | "
                f"CTR {metrics.ctr:.1f}% por {metrics.days_below_champion_cpl} dias"
            )
            max_budget = self._budget_cfg.get("max_daily_per_adset", 0.0)
            if max_budget > 0 and metrics.daily_budget <= max_budget:
                actions.append("duplicate_ad_set")
            else:
                approvals.append("duplicate_ad_set_budget_exceeded")
            state = AdSetState.CHAMPION
        else:
            notes.append(f"Performance dentro dos thresholds — CPL R${metrics.cpl:.2f} | ROAS {metrics.roas:.1f}x")
            state = AdSetState.GOOD

        return AdSetAnalysis(
            metrics=metrics,
            state=state,
            actions_recommended=actions,
            requires_approval=approvals,
            notes=notes,
        )

    @staticmethod
    def _load_settings(settings_path: Path | None) -> dict:
        path = settings_path or _DEFAULT_SETTINGS
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
