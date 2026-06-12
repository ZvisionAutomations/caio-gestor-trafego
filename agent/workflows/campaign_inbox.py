"""Workflow for Campaign Inbox upload and package approval."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..campaign_inbox import load_inbox_package
from ..tools.meta_ads import MetaAdsTool
from ..tools.whatsapp import WhatsAppTool

_LOG_DIR = Path(__file__).parent.parent.parent / "logs"


@dataclass(frozen=True)
class CampaignInboxResult:
    status: str
    folder: str
    campaign_name: str = ""
    version: str = "v1"
    meta_result: dict[str, Any] | None = None
    approval_message_id: str = ""
    reason: str = ""
    comment: str = ""


class CampaignInboxWorkflow:
    def __init__(self, meta_tool: MetaAdsTool, whatsapp_tool: WhatsAppTool) -> None:
        self.meta = meta_tool
        self.wa = whatsapp_tool
        _LOG_DIR.mkdir(exist_ok=True)

    def process_folder(self, folder: str | Path, dry_run: bool = False) -> CampaignInboxResult:
        folder_path = Path(folder)
        try:
            package = load_inbox_package(folder_path)
        except ValueError as exc:
            reason = str(exc)
            self.wa.send_message(
                f"Caio - Campaign Inbox rejeitada\nPasta: {folder_path}\nMotivo: {reason}"
            )
            result = CampaignInboxResult(status="rejected", folder=str(folder_path), reason=reason)
            self._append_history(result)
            return result

        translated = package.translate()
        if dry_run:
            meta_result: dict[str, Any] = {"success": True, "dry_run": True, "translated": translated}
        else:
            meta_result = self.meta.create_paused_campaign_package(translated)

        if not meta_result.get("success"):
            reason = str(meta_result.get("error") or "Meta upload failed")
            self.wa.send_message(
                f"Caio - Campaign Inbox bloqueada\nCampanha: {package.manifest.campaign.name}\nMotivo: {reason}"
            )
            result = CampaignInboxResult(
                status="blocked",
                folder=str(folder_path),
                campaign_name=package.manifest.campaign.name,
                version=package.manifest.campaign.version,
                meta_result=meta_result,
                reason=reason,
            )
            self._append_history(result)
            return result

        approval = self.wa.send_approval_request(
            action_name=f"Ativar pacote de campanha: {package.manifest.campaign.name}",
            reason="Campanha validada e subida no Meta em PAUSED.",
            data=(
                f"Produto: {package.manifest.campaign.product} | "
                f"Ads: {len(package.manifest.ads)} | "
                f"Budget: R${package.manifest.adset.daily_budget_brl:.2f}/dia"
            ),
            estimated_impact="Nenhum objeto nasce ativo; ativacao depende de aprovacao do pacote.",
        )
        result = CampaignInboxResult(
            status="uploaded_paused",
            folder=str(folder_path),
            campaign_name=package.manifest.campaign.name,
            version=package.manifest.campaign.version,
            meta_result=meta_result,
            approval_message_id=str(approval.get("message_id") or ""),
        )
        self._append_history(result)
        return result

    def record_decision(
        self,
        campaign_name: str,
        decision: str,
        version: str = "v1",
        comment: str = "",
        folder: str = "",
    ) -> CampaignInboxResult:
        """Record Caue's package-level decision (approved/rejected).

        Story 039 #7/#9: approval/rejection is per package; rejection may carry
        a free-text comment, saved for future creative learning. Append-only —
        a new version never overwrites the prior decision (#10/#11).
        """
        normalized = decision.strip().lower()
        if normalized not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        result = CampaignInboxResult(
            status=normalized,
            folder=folder,
            campaign_name=campaign_name,
            version=version,
            comment=comment if normalized == "rejected" else "",
        )
        self._append_history(result)
        return result

    @staticmethod
    def _append_history(result: CampaignInboxResult) -> None:
        payload = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "status": result.status,
            "folder": result.folder,
            "campaign_name": result.campaign_name,
            "version": result.version,
            "approval_message_id": result.approval_message_id,
            "reason": result.reason,
            "comment": result.comment,
            "meta_result": result.meta_result or {},
        }
        with open(_LOG_DIR / "campaign-inbox-history.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")
