"""
Harness: Fluxo de Aprovação via WhatsApp
Testa aprovação (OK), rejeição (NÃO) e timeout (sem resposta em 2h).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.workflows.approve import ApprovalDecision, ApproveWorkflow


SCENARIOS = [
    {
        "name": "kaue_aprova",
        "description": "Kaue responde OK — agente executa a ação",
        "poll_result": {"approved": True, "rejected": False, "timeout": False},
        "expected_decision": ApprovalDecision.APPROVED,
        "expected_executed": True,
    },
    {
        "name": "kaue_rejeita",
        "description": "Kaue responde NÃO — agente cancela e registra",
        "poll_result": {"approved": False, "rejected": True, "timeout": False},
        "expected_decision": ApprovalDecision.REJECTED,
        "expected_executed": False,
    },
    {
        "name": "timeout_sem_resposta",
        "description": "Kaue não responde em 2h — ação bloqueada + notificação",
        "poll_result": {"approved": False, "rejected": False, "timeout": True},
        "expected_decision": ApprovalDecision.TIMEOUT,
        "expected_executed": False,
    },
]


def _build_mock_tools():
    meta = MagicMock()
    meta.duplicate_ad_set.return_value = {
        "success": True,
        "new_adset_id": "MOCK_NEW_ADSET",
        "new_name": "Alpha Pulse | COPY",
        "daily_budget": 50.0,
    }

    wa = MagicMock()
    wa.send_approval_request.return_value = {
        "success": True,
        "message_id": "MOCK_MSG_ID",
    }
    wa.send_message.return_value = {"success": True}
    return meta, wa


def run_scenario(scenario: dict) -> dict:
    print(f"\n{'='*60}")
    print(f"HARNESS APROVAÇÃO: {scenario['name']}")
    print(f"Descrição: {scenario['description']}")
    print(f"{'='*60}")

    meta, wa = _build_mock_tools()
    wa.poll_approval_response.return_value = scenario["poll_result"]

    workflow = ApproveWorkflow(
        meta_tool=meta,
        whatsapp_tool=wa,
        timeout_hours=0.001,  # Timeout mínimo para testes
    )

    with patch.object(workflow, "_log_outcome"):
        outcome = workflow.request_and_wait(
            action_name="Duplicar Ad Set Alpha Pulse",
            adset_id="adset_alpha_pulse_01",
            adset_name="Alpha Pulse | Homens 40-65",
            reason="5 dias consecutivos com CPL R$18 e ROAS 3.2x",
            data="Leads: 45 | CTR: 2% | Frequência: 2.0",
            estimated_impact="+R$50/dia | Projeção +8 leads/dia",
            context={"new_budget": 50.0},
        )

    failures: list[str] = []

    expected_decision = scenario["expected_decision"]
    if outcome.decision != expected_decision:
        failures.append(
            f"Decisão: esperado {expected_decision.value}, got {outcome.decision.value}"
        )

    print(f"  Decisão: {outcome.decision.value} (esperado: {expected_decision.value})")
    print(f"  Executada: {outcome.action_executed}")
    print(f"  Erro: {outcome.error or 'nenhum'}")

    verdict = "PASS" if not failures else "FAIL"
    print(f"  Veredicto: {verdict}")

    return {
        "scenario": scenario["name"],
        "verdict": verdict,
        "failures": failures,
        "outcome": outcome,
    }


if __name__ == "__main__":
    print("=" * 60)
    print("CAIO — HARNESS: FLUXO DE APROVAÇÃO")
    print("=" * 60)

    results = [run_scenario(s) for s in SCENARIOS]

    print(f"\n{'='*60}")
    print("RESUMO FINAL")
    total = len(results)
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    print(f"Cenários: {total} | PASS: {passed} | FAIL: {total - passed}")

    if total != passed:
        sys.exit(1)
