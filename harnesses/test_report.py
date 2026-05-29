"""
Harness: Geração de Relatório Diário
Testa se o Caio gera o relatório no formato correto (TXT, duas seções).
Executa sem conexão real à API.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.tools.meta_ads import AdSetMetrics
from agent.workflows.analyze import AdSetAnalysis, AdSetState, AnalysisResult
from agent.workflows.optimize import ActionLog, OptimizeResult
from agent.workflows.report import ReportWorkflow


def _build_mock_analysis() -> AnalysisResult:
    """Constrói um AnalysisResult de exemplo com dados realistas."""
    new_woman = AdSetMetrics(
        id="adset_new_woman_01",
        name="New Woman | Mulheres 45-60",
        status="ACTIVE",
        daily_budget=50.0,
        spend=102.0,
        clicks=420,
        impressions=7000,
        leads=18,
        cpl=56.67,
        ctr=1.8,
        frequency=4.1,
        roas=2.2,
        days_running=8,
    )
    alpha = AdSetMetrics(
        id="adset_alpha_pulse_01",
        name="Alpha Pulse | Homens 40-65",
        status="ACTIVE",
        daily_budget=50.0,
        spend=82.0,
        clicks=500,
        impressions=25000,
        leads=13,
        cpl=63.08,
        ctr=2.1,
        frequency=2.0,
        roas=2.9,
        days_running=5,
    )

    return AnalysisResult(
        ad_sets=[
            AdSetAnalysis(
                metrics=new_woman,
                state=AdSetState.FATIGUED,
                actions_recommended=["pause_creative"],
                requires_approval=["request_new_creative"],
                notes=["Frequência 4.1 — criativo fatigado"],
            ),
            AdSetAnalysis(
                metrics=alpha,
                state=AdSetState.ALERT,
                actions_recommended=["adjust_bid:-0.10"],
                notes=["CPL em zona de atenção"],
            ),
        ],
        autonomous_actions=[],
        approval_requests=[],
        critical_alerts=[],
        total_spend=184.0,
        total_leads=31,
        account_cpl=59.35,
    )


def _build_mock_optimize_result() -> OptimizeResult:
    result = OptimizeResult()
    result.actions_taken = [
        ActionLog(
            timestamp="2026-05-25T09:15:00",
            action="PAUSA AUTÔNOMA — Criativo Fatigado",
            target_id="adset_new_woman_01",
            target_name="New Woman | Criativo Depoimento | Mulheres 50+",
            reason="Frequência 4.1 — criativo fatigado",
            data="Frequência: 4.1 | CTR caiu 2.1% → 1.2%",
            result="REGISTRADO",
            autonomous=True,
        ),
        ActionLog(
            timestamp="2026-05-25T11:30:00",
            action="AJUSTE DE BID -10%",
            target_id="adset_alpha_pulse_01",
            target_name="Alpha Pulse | Homens 40-65",
            reason="CPL em zona de atenção",
            data="CPL: R$63.08 | Bid R$0.85 → R$0.77",
            result="OK",
            autonomous=True,
        ),
    ]
    return result


def _build_mock_tools() -> tuple:
    meta = MagicMock()
    meta.get_account_insights.return_value = {
        "spend": 184.0,
        "leads": 31,
        "cpl": 59.35,
        "roas": 2.53,
        "revenue_estimated": 4650.0,
    }

    wa = MagicMock()
    wa.send_message.return_value = {"success": True, "message_id": "MOCK_ID"}
    return meta, wa


def run_report_harness() -> dict:
    print("=" * 60)
    print("HARNESS: Geração de Relatório Diário")
    print("=" * 60)

    analysis = _build_mock_analysis()
    optimize_result = _build_mock_optimize_result()
    meta_tool, wa_tool = _build_mock_tools()

    workflow = ReportWorkflow(meta_tool=meta_tool, whatsapp_tool=wa_tool)

    approvals_pending = [
        {"request": "Criativo novo New Woman", "sent_at": "09:16"}
    ]

    report = workflow.run(
        analysis=analysis,
        optimize_result=optimize_result,
        approvals_pending=approvals_pending,
    )

    print(f"\nRelatório gerado — {len(report.raw_text)} caracteres")
    print(f"Data: {report.date} | Hora: {report.report_time}")
    print(f"Ações registradas: {len(report.actions_taken)}")
    print(f"Aprovações pendentes: {len(report.approvals_pending)}")
    print(f"Anomalias: {len(report.anomalies)}")
    print(f"Recomendações: {len(report.recommendations)}")

    # Verificações
    failures: list[str] = []

    if "RESUMO EXECUTIVO" not in report.raw_text:
        failures.append("Seção 'RESUMO EXECUTIVO' não encontrada")
    if "RELATÓRIO COMPLETO" not in report.raw_text:
        failures.append("Seção 'RELATÓRIO COMPLETO' não encontrada")
    if "R$184.00" not in report.raw_text and "R$184,00" not in report.raw_text:
        failures.append("Gasto total R$184.00 não encontrado no relatório")
    if "31" not in report.raw_text:
        failures.append("Total de leads (31) não encontrado")
    if not wa_tool.send_message.called:
        failures.append("send_message não foi chamado — relatório não enviado")

    verdict = "PASS" if not failures else "FAIL"

    print(f"\nVeredicto: {verdict}")
    if failures:
        for f in failures:
            print(f"  FAIL: {f}")

    print("\n--- Prévia do relatório ---")
    print(report.raw_text[:800] + "..." if len(report.raw_text) > 800 else report.raw_text)

    return {"verdict": verdict, "failures": failures, "report": report}


if __name__ == "__main__":
    result = run_report_harness()
    if result["verdict"] != "PASS":
        sys.exit(1)
