"""Workflow: Relatório Diário — gera TXT estruturado e envia via WhatsApp."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..tools.meta_ads import MetaAdsTool
from ..tools.whatsapp import WhatsAppTool
from .analyze import AnalysisResult, AdSetState
from .optimize import ActionLog, OptimizeResult

logger = logging.getLogger("caio.workflows.report")

_LOG_DIR = Path(__file__).parent.parent.parent / "logs"
_MAX_WA_MESSAGE_CHARS = 4000  # Limite prático de mensagem WA


@dataclass
class DailyReport:
    """Dados consolidados para o relatório diário."""

    date: str
    report_time: str
    executive_summary: dict[str, Any]
    by_product: dict[str, dict]
    actions_taken: list[ActionLog]
    approvals_pending: list[dict]
    anomalies: list[str]
    recommendations: list[str]
    raw_text: str = ""


class ReportWorkflow:
    """
    Gera o relatório diário do Caio em formato TXT estruturado.
    Envia para o grupo WhatsApp às 20:30.
    Divide em múltiplas mensagens se necessário.
    """

    def __init__(
        self,
        meta_tool: MetaAdsTool,
        whatsapp_tool: WhatsAppTool,
    ) -> None:
        self.meta = meta_tool
        self.wa = whatsapp_tool
        _LOG_DIR.mkdir(exist_ok=True)

    def run(
        self,
        analysis: AnalysisResult,
        optimize_result: OptimizeResult,
        approvals_pending: list[dict] | None = None,
    ) -> DailyReport:
        """
        Gera e envia o relatório diário.

        Args:
            analysis: Resultado do ciclo de análise do dia
            optimize_result: Resultado das otimizações executadas
            approvals_pending: Aprovações ainda aguardando resposta

        Returns:
            DailyReport com todos os dados e o texto gerado
        """
        now = datetime.now()
        report = self._build_report(
            analysis=analysis,
            optimize_result=optimize_result,
            approvals_pending=approvals_pending or [],
            date_str=now.strftime("%d/%m/%Y"),
            time_str=now.strftime("%H:%M"),
        )

        report.raw_text = self._render(report)

        # Persistir relatório local
        report_file = _LOG_DIR / f"report-{now.strftime('%Y-%m-%d')}.txt"
        report_file.write_text(report.raw_text, encoding="utf-8")
        logger.info("Relatório salvo em %s", report_file)

        # Enviar para WhatsApp (dividido se necessário)
        self._send(report.raw_text)

        return report

    def _build_report(
        self,
        analysis: AnalysisResult,
        optimize_result: OptimizeResult,
        approvals_pending: list[dict],
        date_str: str,
        time_str: str,
    ) -> DailyReport:
        # Executivo
        account_data = self.meta.get_account_insights(days=1)
        spend = account_data.get("spend", analysis.total_spend)
        leads = account_data.get("leads", analysis.total_leads)
        cpl = account_data.get("cpl", analysis.account_cpl)
        roas = account_data.get("roas", 0.0)
        revenue = account_data.get("revenue_estimated", 0.0)

        exec_summary = {
            "gasto_dia": spend,
            "leads_gerados": leads,
            "cpl_medio": cpl,
            "receita_estimada": revenue,
            "roas": roas,
        }

        # Por produto (agrupando por nome do ad set)
        by_product: dict[str, dict] = {}
        for ad_analysis in analysis.ad_sets:
            m = ad_analysis.metrics
            product_key = self._infer_product(m.name)
            if product_key not in by_product:
                by_product[product_key] = {
                    "gasto": 0.0,
                    "leads": 0,
                    "ctr_total": 0.0,
                    "roas_total": 0.0,
                    "count": 0,
                    "ad_sets": [],
                    "status": ad_analysis.state.value,
                }
            p = by_product[product_key]
            p["gasto"] += m.spend
            p["leads"] += m.leads
            p["ctr_total"] += m.ctr
            p["roas_total"] += m.roas
            p["count"] += 1
            p["ad_sets"].append(m.name)

        for product_data in by_product.values():
            n = product_data["count"]
            product_data["cpl"] = round(product_data["gasto"] / product_data["leads"], 2) if product_data["leads"] > 0 else 0.0
            product_data["ctr_avg"] = round(product_data["ctr_total"] / n, 1) if n > 0 else 0.0
            product_data["roas_avg"] = round(product_data["roas_total"] / n, 1) if n > 0 else 0.0

        # Anomalias
        anomalies = self._detect_anomalies(analysis)

        # Recomendações
        recommendations = self._build_recommendations(analysis, approvals_pending)

        return DailyReport(
            date=date_str,
            report_time=time_str,
            executive_summary=exec_summary,
            by_product=by_product,
            actions_taken=optimize_result.actions_taken,
            approvals_pending=approvals_pending,
            anomalies=anomalies,
            recommendations=recommendations,
        )

    def _render(self, report: DailyReport) -> str:
        """Renderiza o relatório em TXT estruturado."""
        e = report.executive_summary
        lines: list[str] = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "📊 CAIO — RELATÓRIO RAIZ VITAL",
            f"{report.date} · {report.report_time}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "⚡ RESUMO EXECUTIVO",
            f"Gasto hoje: R${e['gasto_dia']:.2f}",
            f"Leads gerados: {e['leads_gerados']}",
            f"CPL médio: R${e['cpl_medio']:.2f}",
            f"Receita estimada: R${e['receita_estimada']:.2f}",
            f"ROAS: {e['roas']:.2f}x",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "📋 RELATÓRIO COMPLETO",
            "",
            "[DESEMPENHO POR PRODUTO]",
        ]

        for product_name, data in report.by_product.items():
            cpl_flag = " ⚠️" if data["cpl"] > 35 else (" ✅" if data["cpl"] < 20 else "")
            lines += [
                "",
                product_name,
                f"  Gasto: R${data['gasto']:.2f} | Leads: {data['leads']} | CPL: R${data['cpl']:.2f}{cpl_flag}",
                f"  CTR: {data['ctr_avg']:.1f}% | ROAS: {data['roas_avg']:.1f}x",
                f"  Ad sets: {', '.join(data['ad_sets'][:2])}{'...' if len(data['ad_sets']) > 2 else ''}",
            ]

        if report.actions_taken:
            lines += ["", "[AÇÕES TOMADAS HOJE]"]
            for action in report.actions_taken:
                time_str = action.timestamp[11:16] if len(action.timestamp) > 16 else action.timestamp
                lines += [
                    "",
                    f"{time_str} · {action.action}",
                    f"  Alvo: {action.target_name}",
                    f"  Motivo: {action.reason}",
                    f"  Dados: {action.data}",
                    f"  Resultado: {action.result}",
                ]
        else:
            lines += ["", "[AÇÕES TOMADAS HOJE]", "Nenhuma ação autônoma executada."]

        if report.approvals_pending:
            lines += ["", "[APROVAÇÕES PENDENTES]"]
            for pending in report.approvals_pending:
                sent_at = pending.get("sent_at", "?")
                lines.append(f"⏳ {pending.get('request', 'Ação')} — aguardando Kaue desde {sent_at}")
        else:
            lines += ["", "[APROVAÇÕES PENDENTES]", "Nenhuma."]

        if report.anomalies:
            lines += ["", "[ANOMALIAS]"]
            for anomaly in report.anomalias:
                lines.append(f"⚠️ {anomaly}")
        else:
            lines += ["", "[ANOMALIAS]", "Nenhuma detectada."]

        if report.recommendations:
            lines += ["", "[RECOMENDAÇÕES PARA AMANHÃ]"]
            for i, rec in enumerate(report.recommendations, 1):
                lines.append(f"{i}. {rec}")

        lines += [
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "Caio — Gestor de Tráfego Raiz Vital",
        ]

        return "\n".join(lines)

    def _send(self, text: str) -> None:
        """Envia o relatório, dividindo em partes se ultrapassar o limite."""
        if len(text) <= _MAX_WA_MESSAGE_CHARS:
            self.wa.send_message(text)
            return

        parts = self._split_message(text, _MAX_WA_MESSAGE_CHARS)
        for i, part in enumerate(parts, 1):
            header = f"[{i}/{len(parts)}] " if len(parts) > 1 else ""
            self.wa.send_message(header + part)

    @staticmethod
    def _split_message(text: str, max_chars: int) -> list[str]:
        """Divide o texto em partes respeitando quebras de linha."""
        parts: list[str] = []
        current: list[str] = []
        current_len = 0

        for line in text.split("\n"):
            line_len = len(line) + 1
            if current_len + line_len > max_chars and current:
                parts.append("\n".join(current))
                current = []
                current_len = 0
            current.append(line)
            current_len += line_len

        if current:
            parts.append("\n".join(current))
        return parts

    @staticmethod
    def _infer_product(adset_name: str) -> str:
        """Infere o produto pelo nome do ad set."""
        name_lower = adset_name.lower()
        if "new woman" in name_lower or "new_woman" in name_lower:
            return "New Woman"
        if "alpha pulse" in name_lower or "alpha_pulse" in name_lower:
            return "Alpha Pulse"
        return "Outros"

    @staticmethod
    def _detect_anomalies(analysis: AnalysisResult) -> list[str]:
        anomalies: list[str] = []
        critical_count = sum(
            1 for a in analysis.ad_sets if a.state == AdSetState.CRITICAL
        )
        total = len(analysis.ad_sets)
        if total > 0 and critical_count == total:
            anomalies.append("TODOS os ad sets estão com CPL crítico — verificação urgente")
        if analysis.account_cpl > 35:
            anomalies.append(
                f"CPL médio da conta R${analysis.account_cpl:.2f} acima do threshold de R$35"
            )
        return anomalies

    @staticmethod
    def _build_recommendations(
        analysis: AnalysisResult,
        approvals_pending: list[dict],
    ) -> list[str]:
        recs: list[str] = []

        # Aprovações pendentes urgentes
        for pending in approvals_pending:
            req = pending.get("request", "")
            if "criativo" in req.lower():
                recs.append(f"Kaue: aprovação do criativo pendente é urgente — sem ele o ad set fica sem material")

        # Ad sets campeões para duplicação
        for a in analysis.ad_sets:
            if a.state == AdSetState.CHAMPION:
                recs.append(
                    f"{a.metrics.name} com ROAS {a.metrics.roas:.1f}x — "
                    f"candidato a duplicação nos próximos 2 dias se mantiver performance"
                )

        if not recs:
            recs.append("Continuar monitoramento padrão — sem recomendações urgentes")

        return recs
