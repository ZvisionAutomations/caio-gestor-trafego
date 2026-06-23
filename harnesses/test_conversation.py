"""Harness: Caio conversational brain + short group memory (story-071)."""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.conversation import CaioConversationResponder, GroupMemory, is_mutating_command

GROUP_ID = "120363429540176496@g.us"


class FakeAgent:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def run(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "Resumo Caio: campanhas estaveis, sem acao mutating executada."


class FailingAgent:
    def run(self, prompt: str) -> str:
        raise RuntimeError("llm down")


def _record() -> dict:
    return {"key": {"remoteJid": GROUP_ID, "fromMe": False}}


def test_read_only_question_calls_brain():
    agent = FakeAgent()
    responder = CaioConversationResponder(caio_agent=agent, memory=GroupMemory(max_turns=8))
    answer = responder("Como estao as campanhas hoje?", _record())

    assert "Resumo Caio" in answer
    assert len(agent.prompts) == 1
    assert "Como estao as campanhas hoje?" in agent.prompts[0]


def test_short_memory_is_preserved_between_messages():
    agent = FakeAgent()
    responder = CaioConversationResponder(caio_agent=agent, memory=GroupMemory(max_turns=8))
    responder("Como esta New Woman?", _record())
    responder("E Alpha Pulse?", _record())

    assert len(agent.prompts) == 2
    assert "Como esta New Woman?" in agent.prompts[1]
    assert "E Alpha Pulse?" in agent.prompts[1]
    assert responder.memory.count(GROUP_ID) == 4


def test_mutating_command_is_blocked_before_brain():
    agent = FakeAgent()
    responder = CaioConversationResponder(caio_agent=agent, memory=GroupMemory(max_turns=8))
    answer = responder("Pausa o adset campeao agora", _record())

    assert "SpendGate async" in answer
    assert agent.prompts == []
    assert is_mutating_command("duplicar adset vencedor")


def test_llm_failure_returns_operational_message():
    responder = CaioConversationResponder(caio_agent=FailingAgent(), memory=GroupMemory(max_turns=8))
    answer = responder("Me da um diagnostico", _record())

    assert "cerebro LLM falhou" in answer
    assert responder.memory.count(GROUP_ID) == 2


def run_conversation_harness() -> dict:
    print("=" * 60)
    print("HARNESS: Caio conversation + group memory (story-071)")
    print("=" * 60)
    tests = (
        test_read_only_question_calls_brain,
        test_short_memory_is_preserved_between_messages,
        test_mutating_command_is_blocked_before_brain,
        test_llm_failure_returns_operational_message,
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
    result = run_conversation_harness()
    if result["verdict"] != "PASS":
        sys.exit(1)
