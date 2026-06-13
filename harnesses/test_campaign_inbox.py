"""Harness: Campaign Inbox validation, translation and approval request."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

import json

from agent import creative_tasks
from agent.business_signal import BusinessSignal, evaluate_scale_guardrails
from agent.campaign_inbox import load_inbox_package
from agent.creative_tasks import TASK_FATIGUE, record_creative_task
from agent.tools.meta_ads import AdSetMetrics
from agent.workflows import campaign_inbox as inbox_module
from agent.workflows.analyze import AdSetAnalysis, AdSetState, AnalysisResult
from agent.workflows.campaign_inbox import CampaignInboxWorkflow
from agent.workflows.optimize import OptimizeWorkflow

TMP_ROOT = Path(__file__).parent.parent / "pytest-cache-files-story039"


def _write_valid_package(base: Path, version: str = "v1", with_asset: bool = True) -> None:
    (base / "assets").mkdir(exist_ok=True)
    if with_asset:
        (base / "assets" / "ugc.mp4").write_bytes(b"fake")
    (base / "manifest.yaml").write_text(
        f"""
campaign:
  name: "NW - UGC - Ondas de calor - 001"
  product: "new_woman"
  objective: "messages"
  status_on_upload: "paused"
  page_id: "123"
  whatsapp_phone_number: "5511999990000"
  version: "{version}"
adset:
  name: "Mulheres 45-60 BR"
  daily_budget_brl: 50
  age_min: 45
  age_max: 60
  gender: "female"
  locations: ["BR"]
ads:
  - name: "UGC Hook 01"
    format: "video"
    asset: "assets/ugc.mp4"
    primary_text: "Texto principal"
    headline: "Mensagem no WhatsApp"
    cta: "SEND_MESSAGE"
""",
        encoding="utf-8",
    )


def test_manifest_translates_to_meta_objects():
    TMP_ROOT.mkdir(exist_ok=True)
    base = TMP_ROOT / "valid_translate"
    base.mkdir(exist_ok=True)
    _write_valid_package(base)
    package = load_inbox_package(base)
    translated = package.translate()

    assert translated["campaign"]["objective"] == "OUTCOME_ENGAGEMENT"
    assert translated["campaign"]["status"] == "PAUSED"
    assert translated["adset"]["targeting"]["geo_locations"]["countries"] == ["BR"]
    assert translated["adset"]["targeting"]["genders"] == [2]
    assert translated["adset"]["optimization_goal"] == "CONVERSATIONS"
    assert translated["ads"][0]["status"] == "PAUSED"


def test_workflow_uploads_paused_and_requests_package_approval():
    TMP_ROOT.mkdir(exist_ok=True)
    base = TMP_ROOT / "valid_workflow"
    base.mkdir(exist_ok=True)
    _write_valid_package(base)
    meta = MagicMock()
    meta.create_paused_campaign_package.return_value = {
        "success": True,
        "campaign_id": "cmp_1",
        "adset_id": "as_1",
        "ads": [{"ad_id": "ad_1"}],
    }
    wa = MagicMock()
    wa.send_approval_request.return_value = {"success": True, "message_id": "msg_1"}
    wa.send_message.return_value = {"success": True}

    result = CampaignInboxWorkflow(meta, wa).process_folder(base)

    assert result.status == "uploaded_paused"
    meta.create_paused_campaign_package.assert_called_once()
    wa.send_approval_request.assert_called_once()


def test_invalid_package_is_rejected_without_meta_call():
    TMP_ROOT.mkdir(exist_ok=True)
    base = TMP_ROOT / "invalid"
    base.mkdir(exist_ok=True)
    (base / "manifest.yaml").write_text("campaign: {}\n", encoding="utf-8")
    meta = MagicMock()
    wa = MagicMock()
    wa.send_message.return_value = {"success": True}

    result = CampaignInboxWorkflow(meta, wa).process_folder(base)

    assert result.status == "rejected"
    meta.create_paused_campaign_package.assert_not_called()
    wa.send_message.assert_called_once()


def test_business_signal_blocks_scale_without_guardrails_or_paid_sale():
    signal = BusinessSignal("", "adset_1", "", 0, 0)
    locked = evaluate_scale_guardrails(
        business_signal=signal,
        max_new_adsets_per_day=0,
        max_duplications_per_adset_per_day=0,
    )
    no_sale = evaluate_scale_guardrails(
        business_signal=signal,
        max_new_adsets_per_day=1,
        max_duplications_per_adset_per_day=1,
    )
    paid = evaluate_scale_guardrails(
        business_signal=BusinessSignal("ad_1", "adset_1", "cmp_1", 1, 16590),
        max_new_adsets_per_day=1,
        max_duplications_per_adset_per_day=1,
    )

    assert locked.allowed is False
    assert no_sale.allowed is False
    assert paid.allowed is True


import shutil


def _fresh_dir(name: str) -> Path:
    target = TMP_ROOT / name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _fatigued_analysis() -> AnalysisResult:
    metrics = AdSetMetrics(
        id="adset_fatigued",
        name="NW Fatigado",
        status="ACTIVE",
        daily_budget=50.0,
        spend=200.0,
        clicks=120,
        impressions=40000,
        leads=10,
        cpl=20.0,
        ctr=1.2,
        frequency=4.2,
        roas=2.5,
        days_running=6,
    )
    analysis = AdSetAnalysis(
        metrics=metrics,
        state=AdSetState.FATIGUED,
        actions_recommended=["pause_creative"],
        requires_approval=["request_new_creative"],
        notes=["Frequência 4.2 > 3.5 — criativo fatigado"],
    )
    return AnalysisResult(
        ad_sets=[analysis],
        autonomous_actions=[],
        approval_requests=[],
        critical_alerts=[],
        total_spend=200.0,
        total_leads=10,
        account_cpl=20.0,
    )


def test_valid_manifest_missing_asset_is_rejected():
    base = _fresh_dir("missing_asset")
    _write_valid_package(base, with_asset=False)
    meta = MagicMock()
    wa = MagicMock()
    wa.send_message.return_value = {"success": True}

    result = CampaignInboxWorkflow(meta, wa).process_folder(base)

    assert result.status == "rejected"
    assert "asset not found" in result.reason
    meta.create_paused_campaign_package.assert_not_called()


def test_package_rejection_with_comment_is_saved():
    log_dir = _fresh_dir("history_reject")
    original = inbox_module._LOG_DIR
    inbox_module._LOG_DIR = log_dir
    try:
        wf = CampaignInboxWorkflow(MagicMock(), MagicMock())
        res = wf.record_decision(
            "NW UGC 001", "rejected", version="v1", comment="hook fraco, refazer abertura"
        )
    finally:
        inbox_module._LOG_DIR = original

    assert res.status == "rejected"
    assert res.comment == "hook fraco, refazer abertura"
    records = _read_jsonl(log_dir / "campaign-inbox-history.jsonl")
    assert records[-1]["status"] == "rejected"
    assert records[-1]["comment"] == "hook fraco, refazer abertura"


def test_versioning_is_append_only():
    log_dir = _fresh_dir("history_versions")
    original = inbox_module._LOG_DIR
    inbox_module._LOG_DIR = log_dir
    try:
        wf = CampaignInboxWorkflow(MagicMock(), MagicMock())
        wf.record_decision("NW UGC 001", "rejected", version="v1", comment="refazer hook")
        wf.record_decision("NW UGC 001", "approved", version="v2")
    finally:
        inbox_module._LOG_DIR = original

    records = _read_jsonl(log_dir / "campaign-inbox-history.jsonl")
    versions = [(r["version"], r["status"]) for r in records]
    assert ("v1", "rejected") in versions
    assert ("v2", "approved") in versions
    # v1 preservada — nova versao nao sobrescreve o historico
    assert sum(1 for r in records if r["version"] == "v1") == 1


def test_record_creative_task_is_append_only():
    log_dir = _fresh_dir("tasks_unit")
    record_creative_task(task_type=TASK_FATIGUE, target_id="a1", target_name="A", reason="r1", log_dir=log_dir)
    record_creative_task(task_type=TASK_FATIGUE, target_id="a2", target_name="B", reason="r2", log_dir=log_dir)
    records = _read_jsonl(log_dir / "creative-tasks.jsonl")
    assert len(records) == 2
    assert records[0]["assignee"] == "Miguel"


def test_fatigue_creates_miguel_task_not_kaue_approval():
    log_dir = _fresh_dir("miguel_tasks")
    original = creative_tasks._DEFAULT_LOG_DIR
    creative_tasks._DEFAULT_LOG_DIR = log_dir
    try:
        meta = MagicMock()
        wa = MagicMock()
        wa.send_message.return_value = {"success": True}
        result = OptimizeWorkflow(meta, wa).run(_fatigued_analysis())
    finally:
        creative_tasks._DEFAULT_LOG_DIR = original

    assert len(result.creative_tasks) == 1
    assert result.creative_tasks[0]["task_type"] == TASK_FATIGUE
    assert result.creative_tasks[0]["assignee"] == "Miguel"
    # fadiga NAO pede aprovacao do Kaue
    wa.send_approval_request.assert_not_called()
    records = _read_jsonl(log_dir / "creative-tasks.jsonl")
    assert records[-1]["task_type"] == TASK_FATIGUE


if __name__ == "__main__":
    tests = (
        test_manifest_translates_to_meta_objects,
        test_workflow_uploads_paused_and_requests_package_approval,
        test_invalid_package_is_rejected_without_meta_call,
        test_business_signal_blocks_scale_without_guardrails_or_paid_sale,
        test_valid_manifest_missing_asset_is_rejected,
        test_package_rejection_with_comment_is_saved,
        test_versioning_is_append_only,
        test_record_creative_task_is_append_only,
        test_fatigue_creates_miguel_task_not_kaue_approval,
    )
    failures = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:
            print(f"FAIL {test.__name__}: {exc}")
            failures.append(str(exc))
    if failures:
        raise SystemExit(1)
