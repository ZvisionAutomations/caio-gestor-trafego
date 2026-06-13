"""CLI: process one Campaign Inbox folder."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.tools.meta_ads import MetaAdsTool
from agent.tools.whatsapp import WhatsAppTool
from agent.workflows.campaign_inbox import CampaignInboxWorkflow


class _DryRunMeta:
    def create_paused_campaign_package(self, package):
        return {"success": True, "dry_run": True, "translated": package}


class _DryRunWhatsApp:
    def send_message(self, text):
        print(text)
        return {"success": True, "message_id": "dry-run"}

    def send_approval_request(self, **kwargs):
        print(kwargs)
        return {"success": True, "message_id": "dry-run"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Process a Caio Campaign Inbox folder")
    parser.add_argument("folder", help="Folder containing manifest.yaml and assets/")
    parser.add_argument("--dry-run", action="store_true", help="Validate and translate without Meta writes")
    args = parser.parse_args()

    if args.dry_run:
        workflow = CampaignInboxWorkflow(_DryRunMeta(), _DryRunWhatsApp())  # type: ignore[arg-type]
    else:
        workflow = CampaignInboxWorkflow(MetaAdsTool(), WhatsAppTool())
    result = workflow.process_folder(args.folder, dry_run=args.dry_run)
    print(result.status)
    if result.reason:
        print(result.reason)
    return 0 if result.status in {"uploaded_paused", "rejected"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
