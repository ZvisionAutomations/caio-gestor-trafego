"""
Harness: Ciclo de Análise
Testa se o Caio classifica corretamente ad sets e determina ações.
Executa com dados mock — sem conexão à Meta API real.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# Adiciona o root do package ao path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.tools.meta_ads import AdSetMetrics
from agent.workflows.analyze import AdSetState, AnalyzeWorkflow

_MOCKS_DIR = Path(__file__).parent / "mocks"
_SETTINGS = Path(__file__).parent.parent / "config" / "settings.yaml"


@dataclass
class Scenario:
    name: str
    description: str
    mock_file: str
    expected_states: dict[str, AdSetState]
    expected_actions: list[str]


SCENARIOS = [
    Scenario(
        name="all_good",
        description="Todas as campanhas saudáveis — nenhuma ação necessária",
        mock_file="campaigns_good.json",
        expected_states={
            "adset_new_woman_01": AdSetState.ALERT,       # CPL R$26.67 (zona de atenção)
            "adset_alpha_pulse_01": AdSetState.GOOD,
        },
        expected_actions=["adjust_bid:-0.10"],
    ),
    Scenario(
        name="cpl_critico",
        description="New Woman com CPL R$42 por 2 dias — deve pausar",
        mock_file="campaigns_bad.json",
        expected_states={
            "adset_new_woman_01": AdSetState.CRITICAL,
        },
        expected_actions=["pause_ad_set"],
    ),
    Scenario(
        name="mixed_com_campeao_e_fatigado",
        description="Alpha campeão + New Woman fatigado + ad set sem dados",
        mock_file="campaigns_mixed.json",
        expected_states={
            "adset_alpha_pulse_01": AdSetState.CHAMPION,
            "adset_new_woman_02": AdSetState.FATIGUED,
            "adset_new_woman_novo": AdSetState.INSUFFICIENT,
        },
        expected_actions=["duplicate_ad_set_budget_exceeded", "pause_creative", "request_new_creative"],
    ),
]


def _load_mock(filename: str) -> dict[str, Any]:
    with open(_MOCKS_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _build_mock_tool(mock_data: dict) -> MagicMock:
    """Constrói um MetaAdsTool mockado com dados de teste."""
    tool = MagicMock()
    ad_sets = mock_data["ad_sets"]

    tool.get_ad_set_insights.return_value = [
        AdSetMetrics(
            id=a["id"],
            name=a["name"],
            status=a["status"],
            daily_budget=a["daily_budget"],
            spend=a["spend"],
            clicks=a["clicks"],
            impressions=a["impressions"],
            leads=a["leads"],
            cpl=a["cpl"],
            ctr=a["ctr"],
            frequency=a["frequency"],
            roas=a["roas"],
            days_running=a["days_running"],
            days_above_cpl_threshold=a.get("days_above_cpl_threshold", 0),
            days_below_champion_cpl=a.get("days_below_champion_cpl", 0),
        )
        for a in ad_sets
    ]

    tool.get_account_insights.return_value = {
        "spend": sum(a["spend"] for a in ad_sets),
        "leads": sum(a["leads"] for a in ad_sets),
        "cpl": 0.0,
        "roas": 0.0,
        "revenue_estimated": 0.0,
    }

    return tool


def run_scenario(scenario: Scenario) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"HARNESS: {scenario.name}")
    print(f"Descrição: {scenario.description}")
    print(f"{'='*60}")

    mock_data = _load_mock(scenario.mock_file)
    mock_tool = _build_mock_tool(mock_data)

    workflow = AnalyzeWorkflow(meta_tool=mock_tool, settings_path=_SETTINGS)
    result = workflow.run(days=7)

    print(f"\nAd sets analisados: {len(result.ad_sets)}")
    print(f"Ações autônomas: {len(result.autonomous_actions)}")
    print(f"Aprovações necessárias: {len(result.approval_requests)}")
    print(f"Alertas críticos: {len(result.critical_alerts)}")

    passes: list[str] = []
    failures: list[str] = []

    for analysis in result.ad_sets:
        adset_id = analysis.metrics.id
        expected_state = scenario.expected_states.get(adset_id)

        state_indicator = "✅" if analysis.state == expected_state else "❌"
        print(f"\n  {state_indicator} {analysis.metrics.name}")
        print(f"     Estado: {analysis.state.value} (esperado: {expected_state.value if expected_state else '?'})")
        print(f"     Notas: {'; '.join(analysis.notes)}")
        print(f"     Ações: {analysis.actions_recommended}")
        print(f"     Aprovações: {analysis.requires_approval}")

        if expected_state and analysis.state == expected_state:
            passes.append(adset_id)
        elif expected_state:
            failures.append(f"{adset_id}: esperado {expected_state.value}, got {analysis.state.value}")

    actual_actions = {
        *[a["action"] for a in result.autonomous_actions],
        *[a["action"] for a in result.approval_requests],
    }
    for expected_action in scenario.expected_actions:
        if expected_action not in actual_actions:
            failures.append(f"aÃ§Ã£o esperada nÃ£o encontrada: {expected_action}")

    verdict = "PASS" if not failures else "FAIL"
    print(f"\nVeredicto: {verdict}")
    if failures:
        for f in failures:
            print(f"  FAIL: {f}")

    return {
        "scenario": scenario.name,
        "verdict": verdict,
        "passes": len(passes),
        "failures": failures,
        "analysis_result": result,
    }


if __name__ == "__main__":
    print("=" * 60)
    print("CAIO — HARNESS: ANÁLISE DE CAMPANHAS")
    print("=" * 60)

    results = [run_scenario(s) for s in SCENARIOS]

    print(f"\n{'='*60}")
    print("RESUMO FINAL")
    total = len(results)
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    print(f"Cenários: {total} | PASS: {passed} | FAIL: {total - passed}")

    if total != passed:
        sys.exit(1)
