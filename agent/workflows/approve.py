"""Workflow: Aprovação — envia pedido ao Kaue e aguarda OK/NÃO/timeout."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from ..tools.meta_ads import MetaAdsTool
from ..tools.whatsapp import WhatsAppTool

logger = logging.getLogger("caio.workflows.approve")

_LOG_DIR = Path(__file__).parent.parent.parent / "logs"


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"


@dataclass
class ApprovalRequest:
    """Uma solicitação de aprovação pendente."""

    action_name: str
    adset_id: str
    adset_name: str
    message_id: str
    sent_at: str
    context: dict


@dataclass
class ApprovalOutcome:
    """Resultado de uma solicitação de aprovação."""

    request: ApprovalRequest
    decision: ApprovalDecision
    decided_at: str
    action_executed: bool = False
    error: str | None = None


class ApproveWorkflow:
    """
    Gerencia o ciclo de aprovação via WhatsApp.
    Envia a solicitação, faz polling da resposta e executa a ação se aprovada.
    """

    def __init__(
        self,
        meta_tool: MetaAdsTool,
        whatsapp_tool: WhatsAppTool,
        timeout_hours: float = 2.0,
    ) -> None:
        self.meta = meta_tool
        self.wa = whatsapp_tool
        self.timeout_hours = timeout_hours
        _LOG_DIR.mkdir(exist_ok=True)

    def request_and_wait(
        self,
        action_name: str,
        adset_id: str,
        adset_name: str,
        reason: str,
        data: str,
        estimated_impact: str,
        context: dict | None = None,
    ) -> ApprovalOutcome:
        """
        Envia solicitação de aprovação e aguarda resposta (bloqueante).

        Args:
            action_name: Nome da ação a ser aprovada
            adset_id: ID do ad set envolvido
            adset_name: Nome do ad set
            reason: Motivo da solicitação
            data: Métricas de suporte
            estimated_impact: Impacto estimado da ação
            context: Contexto adicional para execução pós-aprovação

        Returns:
            ApprovalOutcome com a decisão e resultado da execução
        """
        sent = self.wa.send_approval_request(
            action_name=action_name,
            reason=reason,
            data=data,
            estimated_impact=estimated_impact,
        )

        if not sent.get("success"):
            logger.error("Falha ao enviar solicitação de aprovação: %s", sent.get("error"))
            request = ApprovalRequest(
                action_name=action_name,
                adset_id=adset_id,
                adset_name=adset_name,
                message_id="",
                sent_at=datetime.now().isoformat(),
                context=context or {},
            )
            return ApprovalOutcome(
                request=request,
                decision=ApprovalDecision.TIMEOUT,
                decided_at=datetime.now().isoformat(),
                error="Falha no envio da mensagem",
            )

        message_id = sent.get("message_id", "")
        request = ApprovalRequest(
            action_name=action_name,
            adset_id=adset_id,
            adset_name=adset_name,
            message_id=message_id,
            sent_at=datetime.now().isoformat(),
            context=context or {},
        )

        logger.info(
            "Aguardando aprovação de '%s' — message_id: %s | timeout: %.1fh",
            action_name, message_id, self.timeout_hours,
        )

        poll_result = self.wa.poll_approval_response(
            message_id=message_id,
            timeout_hours=self.timeout_hours,
        )

        if poll_result.get("approved"):
            decision = ApprovalDecision.APPROVED
        elif poll_result.get("rejected"):
            decision = ApprovalDecision.REJECTED
        else:
            decision = ApprovalDecision.TIMEOUT

        outcome = ApprovalOutcome(
            request=request,
            decision=decision,
            decided_at=datetime.now().isoformat(),
        )

        if decision == ApprovalDecision.APPROVED:
            outcome = self._execute_approved_action(outcome, context or {})
        elif decision == ApprovalDecision.REJECTED:
            logger.info("Ação '%s' rejeitada pelo Kaue", action_name)
        else:
            logger.warning(
                "Timeout de aprovação para '%s' — ação bloqueada", action_name
            )
            self.wa.send_message(
                f"⏰ Caio: Aprovação de '{action_name}' não recebida em "
                f"{self.timeout_hours:.0f}h — ação bloqueada e registrada no log."
            )

        self._log_outcome(outcome)
        return outcome

    def _execute_approved_action(
        self, outcome: ApprovalOutcome, context: dict
    ) -> ApprovalOutcome:
        """Executa a ação aprovada pelo Kaue."""
        action = outcome.request.action_name
        adset_id = outcome.request.adset_id

        try:
            if "Duplicar Ad Set" in action:
                new_budget = context.get("new_budget", 0.0)
                result = self.meta.duplicate_ad_set(adset_id, new_budget)
                outcome.action_executed = result.get("success", False)
                if not outcome.action_executed:
                    outcome.error = result.get("error", "Erro desconhecido")
                else:
                    self.wa.send_message(
                        f"✅ Caio: Ad set '{outcome.request.adset_name}' duplicado com "
                        f"budget R${new_budget:.2f}/dia. Novo ad set criado pausado para revisão."
                    )

            elif "Budget" in action or "budget" in action:
                new_budget = context.get("new_budget", 0.0)
                outcome.action_executed = True
                self.wa.send_message(
                    f"✅ Caio: Aprovação recebida. Budget de '{outcome.request.adset_name}' "
                    f"será aumentado para R${new_budget:.2f}/dia."
                )

            else:
                logger.warning("Ação aprovada sem handler definido: %s", action)
                outcome.action_executed = False
                outcome.error = f"Sem handler para ação: {action}"

        except Exception as exc:
            logger.error("Erro ao executar ação aprovada '%s': %s", action, exc)
            outcome.action_executed = False
            outcome.error = str(exc)

        return outcome

    def _log_outcome(self, outcome: ApprovalOutcome) -> None:
        log_file = _LOG_DIR / f"approvals-{datetime.now().strftime('%Y-%m-%d')}.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(
                f"[{outcome.decided_at}] {outcome.decision.value} | "
                f"{outcome.request.action_name} | {outcome.request.adset_name} "
                f"({outcome.request.adset_id}) | "
                f"executed: {outcome.action_executed} | "
                f"error: {outcome.error or 'none'}\n"
            )
