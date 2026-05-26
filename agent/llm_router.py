"""LLM Router — roteia tarefas para o modelo mais custo-eficiente.

Estratégia:
  - Groq Llama 3.1 70B: tarefas rotineiras (formatação, classificação simples, relatórios de texto)
  - Claude Sonnet 4.6: decisões complexas, aprovações, recomendações criativas

Referência: compass_artifact Zvision — "mantenha Groq como músculo de baixo custo,
promova Claude Sonnet 4.5 com prompt caching ao núcleo de raciocínio"
"""
from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Any

logger = logging.getLogger("caio.llm_router")


class TaskType(str, Enum):
    REPORT_GENERATION = "report_generation"      # Groq — gera texto de relatório
    CLASSIFICATION = "classification"            # Groq — classifica estado simples
    COMPLEX_DECISION = "complex_decision"        # Claude — decisão com trade-offs
    APPROVAL_REASONING = "approval_reasoning"    # Claude — avaliar e redigir pedido de aprovação
    CREATIVE_RECOMMENDATION = "creative_recommendation"  # Claude — recomendar novo criativo


class LLMRouter:
    """
    Roteia chamadas LLM para o modelo mais adequado por custo × qualidade.

    Groq (Llama 3.1 70B): ~$0.59/1M tokens → tarefas de formatação e texto estruturado
    Claude Sonnet 4.6: ~$3/1M tokens input → raciocínio e decisões complexas
    """

    GROQ_TASKS = {TaskType.REPORT_GENERATION, TaskType.CLASSIFICATION}
    CLAUDE_TASKS = {
        TaskType.COMPLEX_DECISION,
        TaskType.APPROVAL_REASONING,
        TaskType.CREATIVE_RECOMMENDATION,
    }

    def __init__(self) -> None:
        self._groq_available = self._check_groq()
        if not self._groq_available:
            logger.warning("GROQ_API_KEY não encontrado — todas as tarefas usarão Claude")

    def route(self, task_type: TaskType, prompt: str, system: str = "") -> str:
        """
        Executa a chamada LLM no modelo correto para o tipo de tarefa.

        Args:
            task_type: Tipo da tarefa — determina qual modelo usar
            prompt: Prompt do usuário
            system: Prompt de sistema (opcional)

        Returns:
            Texto gerado pelo modelo
        """
        if task_type in self.GROQ_TASKS and self._groq_available:
            return self._call_groq(prompt, system)
        return self._call_claude(prompt, system)

    def _call_groq(self, prompt: str, system: str = "") -> str:
        """Chama Groq Llama 3.1 70B — rápido e barato para tarefas rotineiras."""
        try:
            from groq import Groq
            client = Groq(api_key=os.environ["GROQ_API_KEY"])
            messages: list[Any] = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("Groq falhou, fallback para Claude: %s", exc)
            return self._call_claude(prompt, system)

    def _call_claude(self, prompt: str, system: str = "") -> str:
        """Chama Claude Sonnet 4.6 — raciocínio de alta qualidade."""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

            kwargs: dict[str, Any] = {
                "model": "claude-sonnet-4-6",
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
    def _check_groq() -> bool:
        return bool(os.environ.get("GROQ_API_KEY"))


# Instância singleton — importar nos workflows
router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Retorna o singleton sob demanda, evitando side effects no import."""
    global router
    if router is None:
        router = LLMRouter()
    return router
