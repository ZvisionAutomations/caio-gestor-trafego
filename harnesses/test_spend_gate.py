"""Harness: SpendGate async for conversational mutating commands (story-072)."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.conversation import CaioConversationResponder, GroupMemory
from agent.spend_gate import SpendGate

GROUP_ID = "120363429540176496@g.us"


class FakeMeta:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def pause_ad_set(self, adset_id: str) -> dict:
        self.calls.append(("pause_ad_set", adset_id))
        return {"success": True, "adset_id": adset_id}

    def pause_ad(self, ad_id: str) -> dict:
        self.calls.append(("pause_ad", ad_id))
        return {"success": True, "ad_id": ad_id}

    def duplicate_ad_set(self, adset_id: str) -> dict:
        self.calls.append(("duplicate_ad_set", adset_id))
        return {"success": True, "source_adset_id": adset_id}

    def adjust_bid(self, adset_id: str, pct: float) -> dict:
        self.calls.append(("adjust_bid", adset_id, pct))
        return {"success": True, "adset_id": adset_id, "pct": pct}


class FakeWhatsApp:
    def __init__(self) -> None:
        self.approvals: list[dict] = []

    def send_approval_request(self, **kwargs) -> dict:
        self.approvals.append(kwargs)
        return {"success": True, "message_id": "approval-1"}


class FakeAgent:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def run(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "Resposta read-only"


def _record() -> dict:
    return {"key": {"remoteJid": GROUP_ID, "fromMe": False}}


def _responder(meta: FakeMeta | None = None, wa: FakeWhatsApp | None = None) -> CaioConversationResponder:
    return CaioConversationResponder(
        caio_agent=FakeAgent(),
        memory=GroupMemory(max_turns=8),
        spend_gate=SpendGate(
            meta_tool=meta or FakeMeta(),
            whatsapp_tool=wa or FakeWhatsApp(),
            timeout_minutes=120,
        ),
    )


def test_read_only_goes_to_brain_without_approval():
    meta = FakeMeta()
    wa = FakeWhatsApp()
    responder = _responder(meta, wa)
    answer = responder("Como esta o CPL hoje?", _record())

    assert answer == "Resposta read-only"
    assert wa.approvals == []
    assert meta.calls == []


def test_mutating_command_creates_pending_approval_without_execution():
    meta = FakeMeta()
    wa = FakeWhatsApp()
    responder = _responder(meta, wa)
    answer = responder("Pausa adset_123 agora", _record())

    assert "Pedido de aprovacao SG-0001" in answer
    assert wa.approvals
    assert meta.calls == []


def test_ok_executes_pending_action():
    meta = FakeMeta()
    wa = FakeWhatsApp()
    responder = _responder(meta, wa)
    responder("Pausa adset_123 agora", _record())
    answer = responder("OK", _record())

    assert "executada" in answer
    assert meta.calls == [("pause_ad_set", "adset_123")]


def test_nao_cancels_pending_action():
    meta = FakeMeta()
    responder = _responder(meta, FakeWhatsApp())
    responder("Duplicar adset_777", _record())
    answer = responder("NAO", _record())

    assert "cancelada" in answer
    assert meta.calls == []


def test_timeout_cancels_without_side_effect():
    meta = FakeMeta()
    wa = FakeWhatsApp()
    gate = SpendGate(meta_tool=meta, whatsapp_tool=wa, timeout_minutes=1)
    now = datetime(2026, 6, 22, 20, 0, tzinfo=timezone.utc)
    gate.request_approval(text="Pausa adset_999", group_id=GROUP_ID, now=now)
    result = gate.handle_decision(
        text="OK",
        group_id=GROUP_ID,
        now=now + timedelta(minutes=2),
    )

    assert result is not None
    assert "expirou" in result.message
    assert meta.calls == []


def test_missing_target_blocks_before_approval():
    meta = FakeMeta()
    wa = FakeWhatsApp()
    responder = _responder(meta, wa)
    answer = responder("Pausa esse conjunto agora", _record())

    assert "faltou o ID do alvo" in answer
    assert wa.approvals == []
    assert meta.calls == []


def run_spend_gate_harness() -> dict:
    print("=" * 60)
    print("HARNESS: SpendGate async (story-072)")
    print("=" * 60)
    tests = (
        test_read_only_goes_to_brain_without_approval,
        test_mutating_command_creates_pending_approval_without_execution,
        test_ok_executes_pending_action,
        test_nao_cancels_pending_action,
        test_timeout_cancels_without_side_effect,
        test_missing_target_blocks_before_approval,
    )
    failures: list[str] = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {test.__name__}: {exc}")
            failures.append(test.__name__)
    print(f"\nVeredicto: {'PASS' if not failures else 'FAIL'}")
    return {"verdict": "PASS" if not failures else "FAIL", "failures": failures}


if __name__ == "__main__":
    result = run_spend_gate_harness()
    if result["verdict"] != "PASS":
        sys.exit(1)
