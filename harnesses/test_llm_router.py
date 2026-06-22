"""
Harness: LLM Router (story-057 + OpenRouter migration).
Verifica roteamento musculo vs cerebro por TaskType, fallback sem OPENROUTER_API_KEY
e IDs de modelo atuais. Executa SEM rede e SEM chaves reais.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.llm_router import (
    DEFAULT_BRAIN_MODEL,
    DEFAULT_MUSCLE_MODEL,
    LLMRouter,
    TaskType,
    get_router,
)


def _router() -> LLMRouter:
    """Build a router and mock the OpenRouter call."""
    router = LLMRouter(
        brain_model="deepseek/deepseek-v3.2",
        muscle_model="google/gemini-2.5-flash-lite",
    )
    router._call_openrouter = lambda model, prompt, system="": f"{model}:{prompt}"  # type: ignore[method-assign]
    return router


def run_llm_router_harness() -> dict:
    print("=" * 60)
    print("HARNESS: LLM Router (musculo vs cerebro + OpenRouter fallback)")
    print("=" * 60)

    failures: list[str] = []

    if DEFAULT_MUSCLE_MODEL != "google/gemini-2.5-flash-lite":
        failures.append(f"DEFAULT_MUSCLE_MODEL inesperado: {DEFAULT_MUSCLE_MODEL}")
    if DEFAULT_BRAIN_MODEL != "deepseek/deepseek-v3.2":
        failures.append(f"DEFAULT_BRAIN_MODEL inesperado: {DEFAULT_BRAIN_MODEL}")

    import agent.llm_router as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    for dead in ("llama-3.1-70b-versatile", "from groq", "claude-sonnet-4-6"):
        if dead in src:
            failures.append(f"referencia morta ainda presente: {dead}")

    router = _router()
    if router.route(TaskType.REPORT_GENERATION, "x") != "google/gemini-2.5-flash-lite:x":
        failures.append("REPORT_GENERATION deveria usar o musculo Gemini via OpenRouter")
    if router.route(TaskType.CLASSIFICATION, "x") != "google/gemini-2.5-flash-lite:x":
        failures.append("CLASSIFICATION deveria usar o musculo Gemini via OpenRouter")

    for brain_task in (
        TaskType.COMPLEX_DECISION,
        TaskType.APPROVAL_REASONING,
        TaskType.CREATIVE_RECOMMENDATION,
    ):
        if router.route(brain_task, "x") != "deepseek/deepseek-v3.2:x":
            failures.append(f"{brain_task} deveria usar o cerebro DeepSeek via OpenRouter")

    saved_key = os.environ.pop("OPENROUTER_API_KEY", None)
    try:
        if LLMRouter().route(TaskType.REPORT_GENERATION, "x") != "":
            failures.append("Sem OPENROUTER_API_KEY, route deveria retornar string vazia")
    finally:
        if saved_key is not None:
            os.environ["OPENROUTER_API_KEY"] = saved_key

    if get_router() is not get_router():
        failures.append("get_router() deveria retornar singleton")

    verdict = "PASS" if not failures else "FAIL"
    print(f"\nVeredicto: {verdict}")
    for failure in failures:
        print(f"  FAIL: {failure}")

    return {"verdict": verdict, "failures": failures}


if __name__ == "__main__":
    result = run_llm_router_harness()
    if result["verdict"] != "PASS":
        sys.exit(1)
