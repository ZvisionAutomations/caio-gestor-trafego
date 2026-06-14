"""
Harness: LLM Router (story-057)
Verifica roteamento músculo (Gemini 2.5 Flash-Lite) vs cérebro (Claude Haiku 4.5)
por TaskType, o fallback gracioso sem GOOGLE_API_KEY e os IDs de modelo.
Executa SEM rede e SEM chaves reais (mocka as chamadas de provider).
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.llm_router import (
    BRAIN_MODEL,
    MUSCLE_MODEL,
    LLMRouter,
    TaskType,
    get_router,
)


def _router(gemini_available: bool) -> LLMRouter:
    """Constrói um router e força o estado de disponibilidade do Gemini + mocks."""
    r = LLMRouter()
    r._gemini_available = gemini_available
    r._call_gemini = lambda prompt, system="": "MUSCLE:gemini"  # type: ignore[assignment]
    r._call_claude = lambda prompt, system="": "BRAIN:claude"  # type: ignore[assignment]
    return r


def run_llm_router_harness() -> dict:
    print("=" * 60)
    print("HARNESS: LLM Router (músculo vs cérebro + fallback)")
    print("=" * 60)

    failures: list[str] = []

    # 1) IDs de modelo corretos (story-057)
    if MUSCLE_MODEL != "gemini-2.5-flash-lite":
        failures.append(f"MUSCLE_MODEL inesperado: {MUSCLE_MODEL}")
    if BRAIN_MODEL != "claude-haiku-4-5-20251001":
        failures.append(f"BRAIN_MODEL inesperado: {BRAIN_MODEL}")

    # 2) Sem modelo morto (regressão llama/groq/sonnet)
    import agent.llm_router as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    for dead in ("llama-3.1-70b-versatile", "from groq", "claude-sonnet-4-6"):
        if dead in src:
            failures.append(f"referência morta ainda presente: {dead}")

    # 3) Com Gemini disponível: tarefas de músculo vão p/ Gemini
    r_on = _router(gemini_available=True)
    if r_on.route(TaskType.REPORT_GENERATION, "x") != "MUSCLE:gemini":
        failures.append("REPORT_GENERATION deveria usar o músculo (Gemini)")
    if r_on.route(TaskType.CLASSIFICATION, "x") != "MUSCLE:gemini":
        failures.append("CLASSIFICATION deveria usar o músculo (Gemini)")

    # 4) Tarefas de cérebro sempre vão p/ Claude (mesmo com Gemini disponível)
    for brain_task in (
        TaskType.COMPLEX_DECISION,
        TaskType.APPROVAL_REASONING,
        TaskType.CREATIVE_RECOMMENDATION,
    ):
        if r_on.route(brain_task, "x") != "BRAIN:claude":
            failures.append(f"{brain_task} deveria usar o cérebro (Claude)")

    # 5) Fallback gracioso: SEM Gemini, músculo cai no cérebro Claude
    r_off = _router(gemini_available=False)
    if r_off.route(TaskType.REPORT_GENERATION, "x") != "BRAIN:claude":
        failures.append("Sem GOOGLE_API_KEY, músculo deveria cair no cérebro Claude (fallback)")

    # 6) _check_gemini reflete env (não pode quebrar boot)
    import os

    saved_g = os.environ.pop("GOOGLE_API_KEY", None)
    saved_gm = os.environ.pop("GEMINI_API_KEY", None)
    try:
        if LLMRouter._check_gemini() is not False:
            failures.append("_check_gemini deveria ser False sem nenhuma chave")
        os.environ["GOOGLE_API_KEY"] = "x"
        if LLMRouter._check_gemini() is not True:
            failures.append("_check_gemini deveria ser True com GOOGLE_API_KEY")
    finally:
        os.environ.pop("GOOGLE_API_KEY", None)
        if saved_g is not None:
            os.environ["GOOGLE_API_KEY"] = saved_g
        if saved_gm is not None:
            os.environ["GEMINI_API_KEY"] = saved_gm

    # 7) get_router() é singleton
    if get_router() is not get_router():
        failures.append("get_router() deveria retornar singleton")

    verdict = "PASS" if not failures else "FAIL"
    print(f"\nVeredicto: {verdict}")
    for f in failures:
        print(f"  FAIL: {f}")

    return {"verdict": verdict, "failures": failures}


if __name__ == "__main__":
    result = run_llm_router_harness()
    if result["verdict"] != "PASS":
        sys.exit(1)
