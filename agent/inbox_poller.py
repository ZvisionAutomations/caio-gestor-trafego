"""Polling idempotente da pasta de handoff do Campaign Inbox (story-058).

O Caio varre uma pasta-raiz de handoff; cada subpasta com `manifest.yaml` é um
pacote de campanha. Pacotes processados com sucesso recebem um marcador durável
(`.caio_processed`) para não serem re-subidos. Erros NÃO marcam (permite retry).
Fail-safe: um pacote com erro não derruba o lote.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .workflows.campaign_inbox import CampaignInboxResult, CampaignInboxWorkflow

logger = logging.getLogger("caio.inbox_poller")

PROCESSED_MARKER = ".caio_processed"


def is_processed(folder: Path) -> bool:
    return (folder / PROCESSED_MARKER).exists()


def mark_processed(folder: Path) -> None:
    (folder / PROCESSED_MARKER).write_text("ok\n", encoding="utf-8")


def discover_packages(root: str | Path) -> list[Path]:
    """Subpastas com manifest.yaml ainda não processadas, em ordem estável."""
    root_path = Path(root)
    if not root_path.exists():
        return []
    found: list[Path] = []
    for child in sorted(root_path.iterdir()):
        if not child.is_dir():
            continue
        if not (child / "manifest.yaml").exists():
            continue
        if is_processed(child):
            continue
        found.append(child)
    return found


def poll_once(
    root: str | Path,
    workflow: "CampaignInboxWorkflow",
    dry_run: bool = False,
) -> list["CampaignInboxResult"]:
    """Processa todos os pacotes novos uma vez. Marca só sucesso (uploaded_paused)."""
    results: list[CampaignInboxResult] = []
    packages = discover_packages(root)
    if packages:
        logger.info("Inbox poll: %d pacote(s) novo(s) em %s", len(packages), root)
    for folder in packages:
        try:
            result = workflow.process_folder(folder, dry_run=dry_run)
            results.append(result)
            if result.status == "uploaded_paused":
                mark_processed(folder)
                logger.info("Inbox: pacote subido em PAUSED e marcado: %s", folder.name)
            else:
                logger.warning(
                    "Inbox: pacote NÃO marcado (status=%s) — retry no próximo poll: %s",
                    result.status,
                    folder.name,
                )
        except Exception as exc:  # noqa: BLE001 — fail-safe por pacote
            logger.error("Inbox: erro ao processar %s (não marcado): %s", folder, exc)
    return results
