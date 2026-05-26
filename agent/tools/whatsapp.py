"""WhatsApp Tool — Evolution API para comunicação do Caio com o grupo Raiz Vital."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger("caio.tools.whatsapp")

_DEFAULT_TIMEOUT_HOURS = 2
_POLL_INTERVAL_SECONDS = 300   # 5 minutos entre checks de resposta
_HTTP_TIMEOUT = 15.0


class WhatsAppTool:
    """
    Wrapper da Evolution API para envio de mensagens e polling de aprovação.
    Reutiliza padrões de retry do ZWAF.
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        instance: str | None = None,
        group_id: str | None = None,
    ) -> None:
        self.api_url = (api_url or os.environ["EVOLUTION_API_URL"]).rstrip("/")
        self.api_key = api_key or os.environ["EVOLUTION_API_KEY"]
        self.instance = instance or os.environ["EVOLUTION_INSTANCE"]
        self.group_id = group_id or os.environ["WHATSAPP_GROUP_ID"]

        self._headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }
        logger.info(
            "WhatsAppTool inicializado — instância: %s | grupo: %s",
            self.instance, self.group_id,
        )

    # ── Envio de Mensagens ─────────────────────────────────────────────────

    def send_message(self, text: str, group_id: str | None = None) -> dict[str, Any]:
        """
        Envia mensagem de texto para o grupo WhatsApp da Raiz Vital.

        Args:
            text: Texto da mensagem a enviar
            group_id: ID do grupo (usa o padrão se não informado)

        Returns:
            Dicionário com resultado do envio e message_id
        """
        target = group_id or self.group_id
        payload = {
            "number": target,
            "text": text,
        }
        url = f"{self.api_url}/message/sendText/{self.instance}"

        try:
            with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
                resp = client.post(url, json=payload, headers=self._headers)
                resp.raise_for_status()
                data = resp.json()
                message_id = data.get("key", {}).get("id", "")
                logger.info("Mensagem enviada ao grupo %s — id: %s", target, message_id)
                return {"success": True, "message_id": message_id, "group_id": target}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.warning("Rate limit da Evolution API — mensagem não enviada")
                return {"success": False, "error": "rate_limited", "retry": True}
            logger.error("Erro HTTP ao enviar mensagem: %s", exc)
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            logger.error("Erro ao enviar mensagem: %s", exc)
            return {"success": False, "error": str(exc)}

    def send_approval_request(
        self,
        action_name: str,
        reason: str,
        data: str,
        estimated_impact: str,
    ) -> dict[str, Any]:
        """
        Envia solicitação de aprovação formatada para o Kaue via WhatsApp.

        Args:
            action_name: Nome da ação que requer aprovação
            reason: Por que está sugerindo esta ação
            data: Métricas que embasam a decisão
            estimated_impact: Budget adicional / resultado esperado

        Returns:
            Dicionário com message_id para polling posterior
        """
        text = (
            "🤖 Caio — Aprovação Necessária\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"AÇÃO: {action_name}\n"
            f"MOTIVO: {reason}\n"
            f"DADOS: {data}\n"
            f"IMPACTO ESTIMADO: {estimated_impact}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Kaue, responda OK para aprovar ou NÃO para rejeitar.\n"
            "Timeout: 2 horas. Sem resposta = ação bloqueada."
        )
        result = self.send_message(text)
        if result["success"]:
            logger.info(
                "Solicitação de aprovação enviada — ação: %s | message_id: %s",
                action_name, result.get("message_id"),
            )
        return result

    def send_critical_alert(
        self,
        problem: str,
        campaign: str,
        data: str,
        action_taken: str,
        next_step: str,
    ) -> dict[str, Any]:
        """
        Envia alerta crítico imediato para o grupo.

        Args:
            problem: Descrição do problema
            campaign: Nome/ID afetado
            data: Métrica que acionou o alerta
            action_taken: O que o agente já fez ou não pôde fazer
            next_step: O que precisa de ação humana

        Returns:
            Dicionário com resultado do envio
        """
        text = (
            "🚨 Caio — ALERTA CRÍTICO\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"PROBLEMA: {problem}\n"
            f"CAMPANHA: {campaign}\n"
            f"DADO: {data}\n"
            f"AÇÃO TOMADA: {action_taken}\n"
            f"PRÓXIMO PASSO: {next_step}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━"
        )
        result = self.send_message(text)
        logger.warning("Alerta crítico enviado — problema: %s", problem)
        return result

    # ── Polling de Resposta ────────────────────────────────────────────────

    def poll_approval_response(
        self,
        message_id: str,
        timeout_hours: float = _DEFAULT_TIMEOUT_HOURS,
        poll_interval_seconds: int = _POLL_INTERVAL_SECONDS,
    ) -> dict[str, Any]:
        """
        Polling síncrono da resposta do Kaue para uma solicitação de aprovação.
        Verifica mensagens recentes no grupo até encontrar OK/NÃO ou timeout.

        Args:
            message_id: ID da mensagem de solicitação enviada
            timeout_hours: Horas até timeout (padrão: 2h)
            poll_interval_seconds: Intervalo entre checks (padrão: 5min)

        Returns:
            Dicionário com resultado: approved/rejected/timeout
        """
        deadline = time.time() + (timeout_hours * 3600)
        logger.info(
            "Aguardando aprovação — message_id: %s | timeout: %.1fh",
            message_id, timeout_hours,
        )

        while time.time() < deadline:
            try:
                response = self._fetch_recent_messages()
                decision = self._parse_approval_response(response, message_id)
                if decision is not None:
                    return decision
            except Exception as exc:
                logger.warning("Erro ao checar resposta: %s", exc)

            remaining = deadline - time.time()
            if remaining <= 0:
                break
            sleep_time = min(poll_interval_seconds, remaining)
            time.sleep(sleep_time)

        logger.warning(
            "Timeout de aprovação após %.1fh — message_id: %s",
            timeout_hours, message_id,
        )
        return {
            "approved": False,
            "rejected": False,
            "timeout": True,
            "message_id": message_id,
        }

    def _fetch_recent_messages(self) -> list[dict]:
        """Busca mensagens recentes do grupo via Evolution API."""
        url = f"{self.api_url}/chat/findMessages/{self.instance}"
        payload = {
            "where": {"key": {"remoteJid": self.group_id}},
            "limit": 20,
        }
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.post(url, json=payload, headers=self._headers)
            resp.raise_for_status()
            data = resp.json()
            return data.get("messages", {}).get("records", [])

    @staticmethod
    def _parse_approval_response(
        messages: list[dict],
        original_message_id: str,
    ) -> dict[str, Any] | None:
        """
        Procura por respostas 'OK' ou 'NÃO' posteriores à mensagem de solicitação.
        Retorna None se ainda não houver resposta.
        """
        approval_message_ts: int | None = None

        for msg in messages:
            msg_id = msg.get("key", {}).get("id", "")
            if msg_id == original_message_id:
                approval_message_ts = msg.get("messageTimestamp", 0)
                break

        if approval_message_ts is None:
            return None

        for msg in messages:
            msg_ts = msg.get("messageTimestamp", 0)
            if msg_ts <= approval_message_ts:
                continue

            from_me = msg.get("key", {}).get("fromMe", False)
            if from_me:
                continue

            body = (
                msg.get("message", {}).get("conversation", "")
                or msg.get("message", {}).get("extendedTextMessage", {}).get("text", "")
            ).strip().upper()

            if body == "OK":
                logger.info("Aprovação recebida — message_id: %s", original_message_id)
                return {"approved": True, "rejected": False, "timeout": False}
            if body in ("NÃO", "NAO", "NO", "N"):
                logger.info("Rejeição recebida — message_id: %s", original_message_id)
                return {"approved": False, "rejected": True, "timeout": False}

        return None
