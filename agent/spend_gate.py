"""Async spend gate for conversational mutating Meta Ads commands."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

_REJECT_WORDS = {"NAO", "NÃO", "NO", "N"}
_APPROVE_WORDS = {"OK", "SIM", "YES", "Y"}


@dataclass
class PendingAction:
    approval_id: str
    group_id: str
    action: str
    target_id: str
    original_text: str
    requested_at: datetime
    expires_at: datetime
    status: str = "pending"


@dataclass
class SpendGateResult:
    handled: bool
    message: str


def _normalize(text: str) -> str:
    return text.strip().upper()


def _first_id(text: str, prefixes: tuple[str, ...]) -> str | None:
    for raw in text.replace(",", " ").split():
        token = raw.strip(" .;:()[]{}")
        if token.lower().startswith(prefixes):
            return token
    return None


def plan_mutating_action(text: str) -> tuple[str, str] | None:
    lowered = text.lower()
    if any(word in lowered for word in ("pausa", "pause", "pausar")):
        adset_id = _first_id(text, ("adset_", "as_"))
        if adset_id:
            return ("pause_ad_set", adset_id)
        ad_id = _first_id(text, ("ad_",))
        if ad_id:
            return ("pause_ad", ad_id)
        return ("pause_ad_set", "unknown")

    if "duplic" in lowered:
        return ("duplicate_ad_set", _first_id(text, ("adset_", "as_")) or "unknown")

    if "bid" in lowered and any(word in lowered for word in ("ajust", "reduz", "aument")):
        return ("adjust_bid", _first_id(text, ("adset_", "as_")) or "unknown")

    return None


class SpendGate:
    """Non-blocking approval gate for mutating actions requested in chat."""

    def __init__(
        self,
        *,
        meta_tool: Any,
        whatsapp_tool: Any,
        timeout_minutes: int = 120,
        max_pending: int = 20,
    ) -> None:
        self._meta_tool = meta_tool
        self._whatsapp_tool = whatsapp_tool
        self._timeout = timedelta(minutes=max(1, timeout_minutes))
        self._max_pending = max(1, max_pending)
        self._sequence = 0
        self._pending: dict[str, PendingAction] = {}

    def pending_count(self) -> int:
        return sum(1 for action in self._pending.values() if action.status == "pending")

    def request_approval(
        self,
        *,
        text: str,
        group_id: str,
        now: datetime | None = None,
    ) -> SpendGateResult | None:
        plan = plan_mutating_action(text)
        if plan is None:
            return None

        action, target_id = plan
        if target_id == "unknown":
            return SpendGateResult(
                handled=True,
                message=(
                    "Comando mutating detectado, mas faltou o ID do alvo "
                    "(ex.: adset_123 ou ad_123). Nada foi executado."
                ),
            )

        if self.pending_count() >= self._max_pending:
            return SpendGateResult(
                handled=True,
                message="SpendGate esta com muitas aprovacoes pendentes. Resolva as atuais antes de abrir outra.",
            )

        current = now or datetime.now(timezone.utc)
        self._sequence += 1
        approval_id = f"SG-{self._sequence:04d}"
        pending = PendingAction(
            approval_id=approval_id,
            group_id=group_id,
            action=action,
            target_id=target_id,
            original_text=text,
            requested_at=current,
            expires_at=current + self._timeout,
        )
        self._pending[approval_id] = pending

        self._whatsapp_tool.send_approval_request(
            action_name=f"{approval_id} {action}",
            reason="Comando livre recebido no grupo Raiz Vital",
            data=f"target={target_id}",
            estimated_impact="Sem aumento de budget automatico nesta etapa",
        )
        return SpendGateResult(
            handled=True,
            message=(
                f"Pedido de aprovacao {approval_id} criado para {action} em {target_id}. "
                "Responda OK para executar ou NAO para cancelar."
            ),
        )

    def handle_decision(
        self,
        *,
        text: str,
        group_id: str,
        now: datetime | None = None,
    ) -> SpendGateResult | None:
        decision = _normalize(text)
        if decision not in _APPROVE_WORDS and decision not in _REJECT_WORDS:
            return None

        pending = self._latest_pending(group_id)
        if pending is None:
            return SpendGateResult(handled=True, message="Nao ha aprovacao pendente para este grupo.")

        current = now or datetime.now(timezone.utc)
        if current > pending.expires_at:
            pending.status = "timeout"
            return SpendGateResult(
                handled=True,
                message=f"Aprovacao {pending.approval_id} expirou. Nenhuma acao foi executada.",
            )

        if decision in _REJECT_WORDS:
            pending.status = "rejected"
            return SpendGateResult(
                handled=True,
                message=f"Aprovacao {pending.approval_id} cancelada. Nenhuma acao foi executada.",
            )

        result = self._execute(pending)
        pending.status = "approved"
        return SpendGateResult(
            handled=True,
            message=f"Aprovacao {pending.approval_id} executada: {pending.action} em {pending.target_id}. Resultado: {result}",
        )

    def expire_pending(self, *, now: datetime | None = None) -> int:
        current = now or datetime.now(timezone.utc)
        expired = 0
        for pending in self._pending.values():
            if pending.status == "pending" and current > pending.expires_at:
                pending.status = "timeout"
                expired += 1
        return expired

    def _latest_pending(self, group_id: str) -> PendingAction | None:
        pending = [
            action
            for action in self._pending.values()
            if action.group_id == group_id and action.status == "pending"
        ]
        if not pending:
            return None
        return max(pending, key=lambda action: action.requested_at)

    def _execute(self, pending: PendingAction) -> str:
        if pending.action == "pause_ad_set":
            return str(self._meta_tool.pause_ad_set(pending.target_id))
        if pending.action == "pause_ad":
            return str(self._meta_tool.pause_ad(pending.target_id))
        if pending.action == "duplicate_ad_set":
            return str(self._meta_tool.duplicate_ad_set(pending.target_id))
        if pending.action == "adjust_bid":
            return str(self._meta_tool.adjust_bid(pending.target_id, -0.10))
        return "unsupported_action"
