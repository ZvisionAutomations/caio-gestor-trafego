"""Conversational brain adapter for Caio inbound messages."""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Deque

logger = logging.getLogger("caio.conversation")

_MUTATING_KEYWORDS = (
    "pausa",
    "pause",
    "pausar",
    "reativar",
    "ativa ",
    "ativar",
    "duplicar",
    "duplica",
    "aumentar budget",
    "aumenta budget",
    "reduzir budget",
    "mudar budget",
    "alterar budget",
    "subir campanha",
    "criar campanha",
    "criar adset",
    "criar ad set",
    "ajustar bid",
    "ajusta bid",
)

_MUTATION_BLOCK_MESSAGE = (
    "Isso parece um comando de alteracao em Meta Ads. "
    "Por seguranca, comandos mutating ficam bloqueados ate a Story 072 ativar o SpendGate async."
)

_LLM_FAILURE_MESSAGE = (
    "Caio recebeu a pergunta, mas o cerebro LLM falhou agora. "
    "O inbound segue ativo; tente de novo em instantes ou confira OPENROUTER_API_KEY."
)


@dataclass(frozen=True)
class ChatTurn:
    role: str
    text: str


class GroupMemory:
    """In-memory short history per WhatsApp group."""

    def __init__(self, max_turns: int = 8) -> None:
        self._max_turns = max(2, max_turns)
        self._turns: dict[str, Deque[ChatTurn]] = defaultdict(lambda: deque(maxlen=self._max_turns))

    def add(self, group_id: str, role: str, text: str) -> None:
        self._turns[group_id].append(ChatTurn(role=role, text=text.strip()))

    def render(self, group_id: str) -> str:
        turns = self._turns.get(group_id)
        if not turns:
            return "Sem historico anterior neste grupo."
        return "\n".join(f"{turn.role}: {turn.text}" for turn in turns)

    def count(self, group_id: str) -> int:
        return len(self._turns.get(group_id, ()))


def is_mutating_command(text: str) -> bool:
    normalized = f" {text.strip().lower()} "
    return any(keyword in normalized for keyword in _MUTATING_KEYWORDS)


def _extract_agent_text(response: Any) -> str:
    if isinstance(response, str):
        return response.strip()
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content.strip()
    messages = getattr(response, "messages", None)
    if isinstance(messages, list) and messages:
        last = messages[-1]
        last_content = getattr(last, "content", None)
        if isinstance(last_content, str):
            return last_content.strip()
    return str(response).strip()


class CaioConversationResponder:
    """Callable response builder used by the inbound handler."""

    def __init__(
        self,
        *,
        caio_agent: Any,
        memory: GroupMemory | None = None,
        spend_gate: Any | None = None,
    ) -> None:
        self._caio_agent = caio_agent
        self._memory = memory or GroupMemory()
        self._spend_gate = spend_gate

    @property
    def memory(self) -> GroupMemory:
        return self._memory

    def __call__(self, text: str, record: dict[str, Any]) -> str:
        maybe_key = record.get("key")
        key = maybe_key if isinstance(maybe_key, dict) else {}
        group_id = str(key.get("remoteJid") or record.get("remoteJid") or "default")

        self._memory.add(group_id, "usuario", text)

        if self._spend_gate is not None:
            decision = self._spend_gate.handle_decision(text=text, group_id=group_id)
            if decision is not None and decision.handled:
                self._memory.add(group_id, "caio", decision.message)
                return decision.message

        if is_mutating_command(text):
            if self._spend_gate is not None:
                approval = self._spend_gate.request_approval(text=text, group_id=group_id)
                if approval is not None and approval.handled:
                    self._memory.add(group_id, "caio", approval.message)
                    return approval.message
            self._memory.add(group_id, "caio", _MUTATION_BLOCK_MESSAGE)
            return _MUTATION_BLOCK_MESSAGE

        prompt = (
            "Voce esta respondendo no grupo interno da Raiz Vital.\n"
            "Use o historico curto abaixo para manter contexto, mas seja conciso.\n\n"
            f"Historico recente:\n{self._memory.render(group_id)}\n\n"
            f"Mensagem atual: {text}\n\n"
            "Responda como Caio, gestor de trafego. Nao execute acoes mutating."
        )

        try:
            response = self._caio_agent.run(prompt)
            answer = _extract_agent_text(response)
        except Exception as exc:  # noqa: BLE001 - inbound must fail closed
            logger.warning("Caio brain failed for inbound message: %s", type(exc).__name__)
            answer = _LLM_FAILURE_MESSAGE

        if not answer:
            answer = _LLM_FAILURE_MESSAGE

        self._memory.add(group_id, "caio", answer)
        return answer
