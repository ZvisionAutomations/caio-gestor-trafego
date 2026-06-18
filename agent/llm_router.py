"""LLM Router — roteia tarefas para o modelo mais custo-eficiente via OpenRouter.

Stack (pós story-057, migrado para OpenRouter):
  - Músculo (MUSCLE): tarefas rotineiras de texto puro — classificação simples
    e geração de texto de relatório (sem tool-calling).
    Default: google/gemini-2.5-flash-lite ($0.10/$0.40/M — upgrade vs 2.0, mesmo preço)
  - Cérebro (BRAIN): decisões com trade-offs, aprovações, recomendações.
    Default: deepseek/deepseek-v3.2 ($0.23/$0.34/M — thinking integrado no tool-use)

Ambos roteados via OpenRouter (openai SDK) — uma única OPENROUTER_API_KEY.
Modelos configuráveis em settings.yaml (agent.llm_model / agent.muscle_model)
ou via env CAIO_BRAIN_MODEL / CAIO_MUSCLE_MODEL.

Fail-safe: sem OPENROUTER_API_KEY, todas as chamadas logam erro e retornam
string vazia — o boot NUNCA quebra por ausência de chave.
"""
from __future__ import annotations

import logging
import os
from enum import Enum

logger = logging.getLogger("caio.llm_router")

# URL base do OpenRouter (compatível com OpenAI SDK)
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# IDs padrão no formato OpenRouter "provider/model"
# Alterar via settings.yaml ou vars de ambiente após pesquisa com Fernando.
DEFAULT_BRAIN_MODEL = os.environ.get("CAIO_BRAIN_MODEL", "deepseek/deepseek-v3.2")
DEFAULT_MUSCLE_MODEL = os.environ.get("CAIO_MUSCLE_MODEL", "google/gemini-2.5-flash-lite")


class TaskType(str, Enum):
    REPORT_GENERATION = "report_generation"          # músculo — gera texto de relatório
    CLASSIFICATION = "classification"                # músculo — classifica estado simples
    COMPLEX_DECISION = "complex_decision"            # cérebro — decisão com trade-offs
    APPROVAL_REASONING = "approval_reasoning"        # cérebro — avaliar/redigir aprovação
    CREATIVE_RECOMMENDATION = "creative_recommendation"  # cérebro — recomendar criativo


class LLMRouter:
    """
    Roteia chamadas LLM por custo × qualidade via OpenRouter.

    Uma única OPENROUTER_API_KEY acessa qualquer modelo do catálogo.
    Músculo → modelo barato/rápido (texto puro).
    Cérebro → modelo de raciocínio (decisões, tool-calling implícito).
    """

    MUSCLE_TASKS = {TaskType.REPORT_GENERATION, TaskType.CLASSIFICATION}
    BRAIN_TASKS = {
        TaskType.COMPLEX_DECISION,
        TaskType.APPROVAL_REASONING,
        TaskType.CREATIVE_RECOMMENDATION,
    }

    def __init__(
        self,
        brain_model: str = DEFAULT_BRAIN_MODEL,
        muscle_model: str = DEFAULT_MUSCLE_MODEL,
    ) -> None:
        self._brain_model = brain_model
        self._muscle_model = muscle_model
        self._api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not self._api_key:
            logger.warning(
                "OPENROUTER_API_KEY ausente — chamadas LLM vão falhar. "
                "Setar em .env.caio via nano na VPS."
            )
        else:
            logger.info(
                "LLMRouter OpenRouter inicializado — cérebro=%s | músculo=%s",
                self._brain_model,
                self._muscle_model,
            )

    def route(self, task_type: TaskType, prompt: str, system: str = "") -> str:
        """Executa a chamada LLM no modelo correto para o tipo de tarefa."""
        model = (
            self._muscle_model
            if task_type in self.MUSCLE_TASKS
            else self._brain_model
        )
        return self._call_openrouter(model, prompt, system)

    def _call_openrouter(self, model: str, prompt: str, system: str = "") -> str:
        """Chama OpenRouter via SDK openai — compatível com qualquer modelo do catálogo."""
        if not self._api_key:
            logger.error("OPENROUTER_API_KEY não configurada — retornando vazio")
            return ""
        try:
            from openai import OpenAI

            client = OpenAI(
                base_url=_OPENROUTER_BASE_URL,
                api_key=self._api_key,
            )
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=4096,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("OpenRouter (%s) falhou: %s", model, exc)
            raise


# Instância singleton — importar nos workflows
router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Retorna o singleton sob demanda, evitando side effects no import."""
    global router
    if router is None:
        router = LLMRouter()
    return router
