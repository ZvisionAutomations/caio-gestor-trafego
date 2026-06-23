"""Inbound webhook for Caio conversational messages from Evolution API."""
from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterable
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from .tools.whatsapp import WhatsAppTool

logger = logging.getLogger("caio.inbound")

_DEFAULT_STUB_RESPONSE = (
    "Caio recebeu sua mensagem no grupo Raiz Vital. "
    "Inbound conversacional ativo; cerebro completo entra na proxima etapa."
)


def _normalize_event(event: Any) -> str:
    return str(event or "").replace(".", "_").replace("-", "_").upper()


def _iter_message_records(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item
        return

    if not isinstance(data, dict):
        return

    messages = data.get("messages")
    if isinstance(messages, list):
        for item in messages:
            if isinstance(item, dict):
                yield item
        return

    if isinstance(messages, dict):
        records = messages.get("records")
        if isinstance(records, list):
            for item in records:
                if isinstance(item, dict):
                    yield item
            return

    yield data


def extract_text(record: dict[str, Any]) -> str | None:
    message = record.get("message")
    if not isinstance(message, dict):
        return None

    text = message.get("conversation")
    if isinstance(text, str) and text.strip():
        return text.strip()

    extended = message.get("extendedTextMessage")
    if isinstance(extended, dict):
        extended_text = extended.get("text")
        if isinstance(extended_text, str) and extended_text.strip():
            return extended_text.strip()

    return None


def _record_key(record: dict[str, Any]) -> dict[str, Any]:
    key = record.get("key")
    return key if isinstance(key, dict) else {}


def _default_response_builder(_text: str, _record: dict[str, Any]) -> str:
    return _DEFAULT_STUB_RESPONSE


def process_inbound_payload(
    payload: dict[str, Any],
    *,
    whatsapp_tool: WhatsAppTool,
    allowed_group_id: str,
    response_builder: Callable[[str, dict[str, Any]], str] | None = None,
) -> dict[str, int]:
    """Process one Evolution webhook payload and send stub replies for valid messages."""
    stats = {"received": 0, "ignored": 0, "sent": 0}
    event = _normalize_event(payload.get("event"))
    if event and event != "MESSAGES_UPSERT":
        logger.info("Ignoring Evolution event: %s", event)
        return stats

    build_response = response_builder or _default_response_builder

    for record in _iter_message_records(payload):
        stats["received"] += 1
        key = _record_key(record)
        remote_jid = str(key.get("remoteJid") or record.get("remoteJid") or "")
        from_me = bool(key.get("fromMe", record.get("fromMe", False)))

        if remote_jid != allowed_group_id or from_me:
            stats["ignored"] += 1
            continue

        text = extract_text(record)
        if text is None:
            stats["ignored"] += 1
            continue

        response_text = build_response(text, record)
        result = whatsapp_tool.send_message(response_text, group_id=remote_jid)
        if result.get("success"):
            stats["sent"] += 1
        else:
            logger.warning("Failed to send inbound response: %s", result.get("error"))

    return stats


def create_app(
    *,
    whatsapp_tool: WhatsAppTool,
    allowed_group_id: str,
    webhook_secret: str | None = None,
    response_builder: Callable[[str, dict[str, Any]], str] | None = None,
) -> FastAPI:
    app = FastAPI(title="Caio Inbound", version="1.0.0")
    expected_secret = webhook_secret or os.getenv("CAIO_INBOUND_WEBHOOK_SECRET", "")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "caio-inbound"}

    @app.post("/inbound")
    async def inbound(
        request: Request,
        x_caio_webhook_secret: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if expected_secret and x_caio_webhook_secret != expected_secret:
            raise HTTPException(status_code=401, detail="invalid webhook secret")

        try:
            payload = await request.json()
        except Exception as exc:  # noqa: BLE001 - malformed JSON must not crash the app
            logger.warning("Ignoring malformed inbound payload: %s", type(exc).__name__)
            return {"ok": True, "received": 0, "ignored": 1, "sent": 0}

        if not isinstance(payload, dict):
            return {"ok": True, "received": 0, "ignored": 1, "sent": 0}

        stats = process_inbound_payload(
            payload,
            whatsapp_tool=whatsapp_tool,
            allowed_group_id=allowed_group_id,
            response_builder=response_builder,
        )
        return {"ok": True, **stats}

    return app
