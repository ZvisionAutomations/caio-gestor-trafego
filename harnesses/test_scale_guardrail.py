"""
Harness: Trava de escala conectada ao optimize (story-060).
Duplicação autônoma só ocorre com venda paga atribuída + tetos > 0.
Sem reader / sem sinal / tetos 0 / erro do reader → BLOQUEIA (lado seguro).
Sem rede.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.business_signal import BusinessSignal
from agent.tools.meta_ads import AdSetMetrics
from agent.workflows.analyze import AdSetAnalysis, AdSetState, AnalysisResult
from agent.workflows.optimize import OptimizeWorkflow


class _FakeReader:
    def __init__(self, signal: BusinessSignal) -> None:
        self._signal = signal

    async def get_adset_signal(self, tenant_id: str, adset_id: str, days: int = 7) -> BusinessSignal:
        return self._signal


class _RaisingReader:
    async def get_adset_signal(self, *a, **k) -> BusinessSignal:
        raise RuntimeError("sem DB")


def _champion_analysis() -> AnalysisResult:
    metrics = AdSetMetrics(
        id="adset_champ",
        name="NW Campeão",
        status="ACTIVE",
        daily_budget=50.0,
        spend=300.0,
        clicks=600,
        impressions=20000,
        leads=30,
        cpl=10.0,
        ctr=3.2,
        frequency=2.0,
        roas=3.5,
        days_running=5,
    )
    analysis = AdSetAnalysis(
        metrics=metrics,
        state=AdSetState.CHAMPION,
        actions_recommended=["duplicate_ad_set"],  # ação AUTÔNOMA
        notes=["Campeão"],
    )
    return AnalysisResult(
        ad_sets=[analysis],
        autonomous_actions=[],
        approval_requests=[],
        critical_alerts=[],
        total_spend=300.0,
        total_leads=30,
        account_cpl=10.0,
    )


def _meta() -> MagicMock:
    m = MagicMock()
    m.duplicate_ad_set.return_value = {"success": True, "new_adset_id": "as_2"}
    return m


def _wa() -> MagicMock:
    w = MagicMock()
    w.send_message.return_value = {"success": True}
    return w


_PAID = BusinessSignal("ad_1", "adset_champ", "cmp_1", paid_orders=1, revenue_cents=16590)
_EMPTY = BusinessSignal("", "adset_champ", "", 0, 0)


def _blocked(wf: OptimizeWorkflow, meta: MagicMock) -> bool:
    result = wf.run(_champion_analysis())
    meta.duplicate_ad_set.assert_not_called()
    return any(a.action.startswith("DUPLICAÇÃO BLOQUEADA") for a in result.actions_taken)


def test_allowed_with_paid_sale_and_limits():
    meta = _meta()
    wf = OptimizeWorkflow(
        meta, _wa(), business_signal_reader=_FakeReader(_PAID),
        max_new_adsets_per_day=1, max_duplications_per_adset_per_day=1, tenant_id="t",
    )
    wf.run(_champion_analysis())
    meta.duplicate_ad_set.assert_called_once()


def test_blocked_without_paid_sale():
    meta = _meta()
    wf = OptimizeWorkflow(
        meta, _wa(), business_signal_reader=_FakeReader(_EMPTY),
        max_new_adsets_per_day=1, max_duplications_per_adset_per_day=1, tenant_id="t",
    )
    assert _blocked(wf, meta)


def test_blocked_with_zero_limits_even_if_paid():
    meta = _meta()
    wf = OptimizeWorkflow(
        meta, _wa(), business_signal_reader=_FakeReader(_PAID),
        max_new_adsets_per_day=0, max_duplications_per_adset_per_day=0, tenant_id="t",
    )
    assert _blocked(wf, meta)


def test_blocked_by_default_no_reader():
    meta = _meta()
    wf = OptimizeWorkflow(meta, _wa())  # sem reader, tetos default 0
    assert _blocked(wf, meta)


def test_fail_safe_reader_error_blocks():
    meta = _meta()
    wf = OptimizeWorkflow(
        meta, _wa(), business_signal_reader=_RaisingReader(),
        max_new_adsets_per_day=1, max_duplications_per_adset_per_day=1, tenant_id="t",
    )
    assert _blocked(wf, meta)


def run_scale_guardrail_harness() -> dict:
    print("=" * 60)
    print("HARNESS: Trava de escala no optimize (story-060)")
    print("=" * 60)
    tests = (
        test_allowed_with_paid_sale_and_limits,
        test_blocked_without_paid_sale,
        test_blocked_with_zero_limits_even_if_paid,
        test_blocked_by_default_no_reader,
        test_fail_safe_reader_error_blocks,
    )
    failures: list[str] = []
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {t.__name__}: {exc}")
            failures.append(t.__name__)
    print(f"\nVeredicto: {'PASS' if not failures else 'FAIL'}")
    return {"verdict": "PASS" if not failures else "FAIL", "failures": failures}


if __name__ == "__main__":
    result = run_scale_guardrail_harness()
    if result["verdict"] != "PASS":
        sys.exit(1)
