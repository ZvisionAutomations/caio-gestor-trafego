"""Harness: safe threshold calibration proposals."""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.tools.meta_ads import AdSetMetrics
from agent.workflows.analyze import AdSetAnalysis, AdSetState, AnalysisResult
from agent.workflows.calibrate import CalibrationWorkflow

_SETTINGS = Path(__file__).parent.parent / "config" / "settings.yaml"


def _metrics(idx: int, clicks: int, cpl: float, ctr: float) -> AdSetMetrics:
    return AdSetMetrics(
        id=f"adset_{idx}",
        name=f"New Woman {idx}",
        status="ACTIVE",
        daily_budget=100.0,
        spend=clicks * 1.2,
        clicks=clicks,
        impressions=max(clicks * 80, 1000),
        leads=max(int((clicks * 1.2) / cpl), 1),
        cpl=cpl,
        ctr=ctr,
        frequency=2.1,
        roas=2.5,
        days_running=7,
        days_above_cpl_threshold=0,
        days_below_champion_cpl=0,
    )


def _analysis(items: list[AdSetMetrics]) -> AnalysisResult:
    return AnalysisResult(
        ad_sets=[AdSetAnalysis(metrics=item, state=AdSetState.GOOD) for item in items],
        autonomous_actions=[],
        approval_requests=[],
        critical_alerts=[],
        total_spend=sum(item.spend for item in items),
        total_leads=sum(item.leads for item in items),
        account_cpl=25.0,
    )


def test_insufficient_data() -> None:
    workflow = CalibrationWorkflow(settings_path=_SETTINGS)
    proposal = workflow.build_proposal(_analysis([_metrics(1, 40, 25.0, 2.1)]))
    assert not proposal.has_proposal
    assert "dados insuficientes" in proposal.blocked_reason


def test_builds_manual_proposal() -> None:
    workflow = CalibrationWorkflow(settings_path=_SETTINGS)
    proposal = workflow.build_proposal(_analysis([
        _metrics(1, 200, 22.0, 2.4),
        _metrics(2, 220, 28.0, 1.8),
        _metrics(3, 180, 31.0, 1.4),
    ]))
    assert proposal.has_proposal
    assert not proposal.approved_for_auto_apply
    assert proposal.proposed_thresholds["cpl_max"] <= 42.0
    assert proposal.proposed_thresholds["cpl_max"] >= 28.0
    assert "settings.yaml" in proposal.render_message()


def main() -> int:
    tests = [test_insufficient_data, test_builds_manual_proposal]
    failures: list[str] = []
    print("\n=== CAIO CALIBRATION HARNESS ===\n")
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            print(f"FAIL {test.__name__}: {exc}")
            failures.append(test.__name__)
    if failures:
        return 1
    print("\n=== RESULTADO: APROVADO ===\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
