"""LLM Router — roteia tarefas para o modelo mais custo-eficiente.

Stack (story-057):
  - Gemini 2.5 Flash-Lite (músculo): tarefas rotineiras de TEXTO PURO —
    classificação simples e geração de texto de relatório (sem tool-calling).
  - Claude Haiku 4.5 (cérebro): decisões com trade-offs, aprovações, recomendações.

O cérebro de tool-calling do agente Agno vive em `caio.py`
(`Agent(model=Claude(id=...))`). Este router é um helper de baixo custo para
tarefas de texto puro nos workflows (ex.: narrativa executiva do relatório).

Fail-safe: sem GOOGLE_API_KEY, as tarefas de músculo caem graciosamente no
cérebro Claude. O boot NUNCA quebra por ausência de chave.

SDK: google-genai (unificado). O legado google-generativeai foi descontinuado
em 2025-11-30 e não deve ser usado.
"""
from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Any

logger = logging.getLogger("caio.llm_router")

# IDs de modelo (story-057 / gate de research D9)
MUSCLE_MODEL = "gemini-2.5-flash-lite"
BRAIN_MODEL = "claude-haiku-4-5-20251001"


class TaskType(str, Enum):
    REPORT_GENERATION = "report_generation"      # músculo — gera texto de relatório
    CLASSIFICATION = "classification"            # músculo — classifica estado simples
    COMPLEX_DECISION = "complex_decision"        # cérebro — decisão com trade-offs
    APPROVAL_REASONING = "approval_reasoning"    # cérebro — avaliar/redigir aprovação
    CREATIVE_RECOMMENDATION = "creative_recommendation"  # cérebro — recomendar criativo


class LLMRouter:
    """
    Roteia chamadas LLM por custo × qualidade.

    Gemini 2.5 Flash-Lite (~$0,10/$0,40 por 1M tok in/out): texto rotineiro.
    Claude Haiku 4.5: raciocínio, decisões e tool-calling.
    """

    MUSCLE_TASKS = {TaskType.REPORT_GENERATION, TaskType.CLASSIFICATION}
    BRAIN_TASKS = {
        TaskType.COMPLEX_DECISION,
        TaskType.APPROVAL_REASONING,
        TaskType.CREATIVE_RECOMMENDATION,
    }

    def __init__(self) -> None:
        self._gemini_available = self._check_gemini()
        if not self._gemini_available:
            logger.warning(
                "GOOGLE_API_KEY/GEMINI_API_KEY ausente — tarefas de músculo "
                "usarão o cérebro Claude (fallback gracioso)"
            )

    def route(self, task_type: TaskType, prompt: str, system: str = "") -> str:
        """Executa a chamada LLM no modelo correto para o tipo de tarefa."""
        if task_type in self.MUSCLE_TASKS and self._gemini_available:
            return self._call_gemini(prompt, system)
        return self._call_claude(prompt, system)

    def _call_gemini(self, prompt: str, system: str = "") -> str:
        """Chama Gemini 2.5 Flash-Lite via SDK google-genai — barato p/ texto puro."""
        try:
            from google import genai
            from google.genai import types

            # Client() lê GOOGLE_API_KEY (ou GEMINI_API_KEY) do ambiente.
            client = genai.Client()
            config = (
                types.GenerateContentConfig(system_instruction=system) if system else None
            )
            response = client.models.generate_content(
                model=MUSCLE_MODEL,
                contents=prompt,
                config=config,
            )
            return response.text or ""
        except Exception as exc:
            logger.warning("Gemini falhou, fallback para Claude: %s", exc)
            return self._call_claude(prompt, system)

    def _call_claude(self, prompt: str, system: str = "") -> str:
        """Chama Claude Haiku 4.5 — raciocínio de alta qualidade e baixo custo."""
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

            kwargs: dict[str, Any] = {
                "model": BRAIN_MODEL,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system

            response = client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as exc:
            logger.error("Claude falhou: %s", exc)
            raise

    @staticmethod
    def _check_gemini() -> bool:
        return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))


# Instância singleton — importar nos workflows
router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Retorna o singleton sob demanda, evitando side effects no import."""
    global router
    if router is None:
        router = LLMRouter()
    return router
