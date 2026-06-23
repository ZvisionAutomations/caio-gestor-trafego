"""Harness: inbound conversacional Evolution -> Caio (story-070)."""
from __future__ import annotations

import sys
import asyncio
from pathlib import Path

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.inbound_handler import create_app, extract_text, process_inbound_payload

GROUP_ID = "120363429540176496@g.us"
OTHER_GROUP_ID = "120363000000000000@g.us"


class FakeWhatsApp:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    def send_message(self, text: str, group_id: str | None = None) -> dict:
        self.sent.append({"text": text, "group_id": group_id or ""})
        return {"success": True, "message_id": f"fake-{len(self.sent)}"}


def _payload(
    *,
    remote_jid: str = GROUP_ID,
    from_me: bool = False,
    text: str | None = "Caio, status?",
    event: str = "MESSAGES_UPSERT",
) -> dict:
    message: dict = {}
    if text is not None:
        message["conversation"] = text
    return {
        "event": event,
        "data": {
            "key": {
                "remoteJid": remote_jid,
                "fromMe": from_me,
                "id": "MSG1",
            },
            "message": message,
        },
    }


async def _post_asgi(app, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path, **kwargs)


def test_extract_text_conversation_and_extended():
    assert extract_text({"message": {"conversation": " oi "}}) == "oi"
    assert extract_text({"message": {"extendedTextMessage": {"text": " status "}}}) == "status"
    assert extract_text({"message": {"imageMessage": {"caption": "ignorar"}}}) is None


def test_group_text_replies_once():
    wa = FakeWhatsApp()
    stats = process_inbound_payload(_payload(), whatsapp_tool=wa, allowed_group_id=GROUP_ID)
    assert stats == {"received": 1, "ignored": 0, "sent": 1}, stats
    assert len(wa.sent) == 1
    assert wa.sent[0]["group_id"] == GROUP_ID


def test_from_me_is_ignored():
    wa = FakeWhatsApp()
    stats = process_inbound_payload(
        _payload(from_me=True),
        whatsapp_tool=wa,
        allowed_group_id=GROUP_ID,
    )
    assert stats["sent"] == 0
    assert stats["ignored"] == 1
    assert wa.sent == []


def test_other_group_is_ignored():
    wa = FakeWhatsApp()
    stats = process_inbound_payload(
        _payload(remote_jid=OTHER_GROUP_ID),
        whatsapp_tool=wa,
        allowed_group_id=GROUP_ID,
    )
    assert stats["sent"] == 0
    assert stats["ignored"] == 1


def test_non_text_and_malformed_do_not_crash():
    wa = FakeWhatsApp()
    stats = process_inbound_payload(
        _payload(text=None),
        whatsapp_tool=wa,
        allowed_group_id=GROUP_ID,
    )
    assert stats["sent"] == 0
    assert stats["ignored"] == 1

    app = create_app(whatsapp_tool=wa, allowed_group_id=GROUP_ID)
    response = asyncio.run(_post_asgi(app, "/inbound", content="{bad-json"))
    assert response.status_code == 200
    assert response.json()["ignored"] == 1


def test_webhook_secret_is_enforced():
    wa = FakeWhatsApp()
    app = create_app(whatsapp_tool=wa, allowed_group_id=GROUP_ID, webhook_secret="secret")
    rejected = asyncio.run(_post_asgi(app, "/inbound", json=_payload()))
    assert rejected.status_code == 401

    accepted = asyncio.run(
        _post_asgi(
            app,
            "/inbound",
            json=_payload(),
            headers={"x-caio-webhook-secret": "secret"},
        )
    )
    assert accepted.status_code == 200
    assert accepted.json()["sent"] == 1


def run_inbound_handler_harness() -> dict:
    print("=" * 60)
    print("HARNESS: Inbound handler Evolution -> Caio (story-070)")
    print("=" * 60)
    tests = (
        test_extract_text_conversation_and_extended,
        test_group_text_replies_once,
        test_from_me_is_ignored,
        test_other_group_is_ignored,
        test_non_text_and_malformed_do_not_crash,
        test_webhook_secret_is_enforced,
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
    result = run_inbound_handler_harness()
    if result["verdict"] != "PASS":
        sys.exit(1)
