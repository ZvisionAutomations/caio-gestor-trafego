"""Workflow: Otimização Autônoma — executa ações baseadas na análise."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..tools.meta_ads import MetaAdsTool
from ..tools.whatsapp import WhatsAppTool
from .analyze import AdSetAnalysis, AdSetState, AnalysisResult

logger = logging.getLogger("caio.workflows.optimize")

_LOG_DIR = Path(__file__).parent.parent.parent / "logs"


@dataclass
class ActionLog:
    """Registro de uma ação executada."""

    timestamp: str
    action: str
    target_id: str
    target_name: str
    reason: str
    data: str
    result: str
    autonomous: bool


@dataclass
class OptimizeResult:
    """Resultado do ciclo de otimização."""

    actions_taken: list[ActionLog] = field(default_factory=list)
    approvals_sent: list[dict[str, Any]] = field(default_factory=list)
    alerts_sent: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class OptimizeWorkflow:
    """
    Executa as ações autônomas identificadas pelo AnalyzeWorkflow.
    Envia solicitações de aprovação e alertas críticos via WhatsApp.
    """

    def __init__(
        self,
        meta_tool: MetaAdsTool,
        whatsapp_tool: WhatsAppTool,
    ) -> None:
        self.meta = meta_tool
        self.wa = whatsapp_tool
        _LOG_DIR.mkdir(exist_ok=True)

    def run(self, analysis: AnalysisResult) -> OptimizeResult:
        """
        Processa o resultado da análise e executa ações.

        Args:
            analysis: Resultado do AnalyzeWorkflow

        Returns:
            OptimizeResult com log de tudo que foi feito
        """
        result = OptimizeResult()

        # 1. Alertas críticos (prioridade máxima)
        for alert in analysis.critical_alerts:
            self._send_critical_alert(alert, result)

        # 2. Ações autônomas por ad set
        for ad_set_analysis in analysis.ad_sets:
            self._execute_autonomous_actions(ad_set_analysis, result)

        # 3. Solicitações de aprovação
        for ad_set_analysis in analysis.ad_sets:
            self._send_approval_requests(ad_set_analysis, result)

        # Persistir log de ações
        self._write_action_log(result.actions_taken)

        logger.info(
            "Otimização concluída — ações: %d | aprovações: %d | alertas: %d | erros: %d",
            len(result.actions_taken),
            len(result.approvals_sent),
            len(result.alerts_sent),
            len(result.errors),
        )
        return result

    def _execute_autonomous_actions(
        self, analysis: AdSetAnalysis, result: OptimizeResult
    ) -> None:
        metrics = analysis.metrics

        for action in analysis.actions_recommended:
            ts = datetime.now().isoformat()
            try:
                if action == "pause_ad_set":
                    reason = "; ".join(analysis.notes)
                    api_result = self.meta.pause_ad_set(metrics.id, reason=reason)
                    result.actions_taken.append(ActionLog(
                        timestamp=ts,
                        action="PAUSA AUTÔNOMA — Ad Set",
                        target_id=metrics.id,
                        target_name=metrics.name,
                        reason=reason,
                        data=f"CPL: R${metrics.cpl:.2f} | CTR: {metrics.ctr:.1f}% | ROAS: {metrics.roas:.1f}x",
                        result="OK" if api_result.get("success") else f"ERRO: {api_result.get('error')}",
                        autonomous=True,
                    ))

                elif action == "pause_creative":
                    reason = f"Frequência {metrics.frequency:.1f} > threshold"
                    result.actions_taken.append(ActionLog(
                        timestamp=ts,
                        action="PAUSA AUTÔNOMA — Criativo Fatigado",
                        target_id=metrics.id,
                        target_name=metrics.name,
                        reason=reason,
                        data=f"Frequência: {metrics.frequency:.1f} | CTR: {metrics.ctr:.1f}%",
                        result="REGISTRADO — pausa do anúncio específico requer ID do ad",
                        autonomous=True,
                    ))

                elif action.startswith("adjust_bid:"):
                    pct_str = action.split(":")[1]
                    pct = float(pct_str)
                    api_result = self.meta.adjust_bid(metrics.id, pct)
                    bid_before = api_result.get("bid_before", "?")
                    bid_after = api_result.get("bid_after", "?")
                    result.actions_taken.append(ActionLog(
                        timestamp=ts,
                        action=f"AJUSTE DE BID {pct:+.0%}",
                        target_id=metrics.id,
                        target_name=metrics.name,
                        reason="; ".join(analysis.notes),
                        data=f"CPL: R${metrics.cpl:.2f} | Bid: R${bid_before} → R${bid_after}",
                        result="OK" if api_result.get("success") else f"ERRO: {api_result.get('error')}",
                        autonomous=True,
                    ))

                elif action == "duplicate_ad_set":
                    new_budget = metrics.daily_budget
                    api_result = self.meta.duplicate_ad_set(metrics.id, new_budget)
                    result.actions_taken.append(ActionLog(
                        timestamp=ts,
                        action="DUPLICAÇÃO DE AD SET",
                        target_id=metrics.id,
                        target_name=metrics.name,
                        reason=f"Ad set campeão por {metrics.days_below_champion_cpl} dias",
                        data=f"CPL: R${metrics.cpl:.2f} | ROAS: {metrics.roas:.1f}x | Budget: R${new_budget:.2f}",
                        result="OK" if api_result.get("success") else f"ERRO: {api_result.get('error')}",
                        autonomous=True,
                    ))

            except Exception as exc:
                logger.error("Erro ao executar ação '%s' em %s: %s", action, metrics.id, exc)
                result.errors.append(f"{action} em {metrics.id}: {exc}")

    def _send_approval_requests(
        self, analysis: AdSetAnalysis, result: OptimizeResult
    ) -> None:
        metrics = analysis.metrics

        for req in analysis.requires_approval:
            try:
                if req == "request_new_creative":
                    api_result = self.wa.send_approval_request(
                        action_name="Novo Criativo — Criativo Fatigado",
                        reason=f"Frequência {metrics.frequency:.1f} — criativo precisa ser substituído",
                        data=f"Frequência: {metrics.frequency:.1f} | CTR caiu para {metrics.ctr:.1f}%",
                        estimated_impact="Recuperação de CTR e redução de CPL esperada",
                    )
                elif req == "duplicate_ad_set_budget_exceeded":
                    api_result = self.wa.send_approval_request(
                        action_name=f"Duplicar Ad Set: {metrics.name}",
                        reason=f"Ad set campeão por {metrics.days_below_champion_cpl} dias consecutivos",
                        data=f"CPL: R${metrics.cpl:.2f} | ROAS: {metrics.roas:.1f}x | CTR: {metrics.ctr:.1f}%",
                        estimated_impact=f"+R${metrics.daily_budget:.2f}/dia | Projeção de +{int(metrics.leads * 0.8)} leads/dia",
                    )
                else:
                    continue

                result.approvals_sent.append({
                    "adset_id": metrics.id,
                    "request": req,
                    "message_id": api_result.get("message_id"),
                    "sent": api_result.get("success"),
                })

            except Exception as exc:
                logger.error("Erro ao enviar aprovação '%s': %s", req, exc)
                result.errors.append(f"Aprovação {req}: {exc}")

    def _send_critical_alert(self, alert: dict, result: OptimizeResult) -> None:
        try:
            api_result = self.wa.send_critical_alert(
                problem=f"CPL crítico — {alert['adset_name']}",
                campaign=f"{alert['adset_name']} ({alert['adset_id']})",
                data=f"CPL: R${alert['cpl']:.2f} (threshold: R${alert['threshold']:.2f})",
                action_taken="Nenhuma ação adicional — aguardando decisão humana",
                next_step="Kaue: revise o ad set e considere pausar ou trocar criativo",
            )
            result.alerts_sent.append({
                "adset_id": alert["adset_id"],
                "type": "CPL_CRITICAL",
                "sent": api_result.get("success"),
            })
        except Exception as exc:
            logger.error("Erro ao enviar alerta crítico: %s", exc)
            result.errors.append(f"Alerta crítico {alert['adset_id']}: {exc}")

    @staticmethod
    def _write_action_log(actions: list[ActionLog]) -> None:
        if not actions:
            return
        log_file = _LOG_DIR / f"actions-{datetime.now().strftime('%Y-%m-%d')}.log"
        with open(log_file, "a", encoding="utf-8") as f:
            for action in actions:
                f.write(
                    f"[{action.timestamp}] {'AUTO' if action.autonomous else 'MANUAL'} | "
                    f"{action.action} | {action.target_name} ({action.target_id}) | "
                    f"{action.reason} | {action.data} | {action.result}\n"
                )
