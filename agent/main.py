"""Entry point do Caio — inicializa tools e registra ciclos no scheduler."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "config" / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("caio.main")


def _load_inbox_settings() -> dict:
    """Lê o bloco `inbox` do settings.yaml (fail-safe com defaults seguros)."""
    import yaml

    settings_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    try:
        data = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
        return dict(data.get("inbox", {}))
    except Exception as exc:  # noqa: BLE001 — config nunca derruba o boot
        logger.warning("Não foi possível ler inbox do settings.yaml: %s", exc)
        return {}


def main() -> None:
    from .inbox_poller import poll_once
    from .tools.meta_ads import MetaAdsTool
    from .tools.whatsapp import WhatsAppTool
    from .tools.scheduler import CaioScheduler
    from .workflows.analyze import AnalyzeWorkflow
    from .workflows.calibrate import CalibrationWorkflow
    from .workflows.campaign_inbox import CampaignInboxWorkflow
    from .workflows.optimize import OptimizeWorkflow
    from .workflows.report import ReportWorkflow

    logger.info("Caio — Gestor de Tráfego Raiz Vital iniciando...")

    meta = MetaAdsTool()
    wa = WhatsAppTool()
    scheduler = CaioScheduler()

    analyze_wf = AnalyzeWorkflow(meta)
    calibration_wf = CalibrationWorkflow()
    optimize_wf = OptimizeWorkflow(meta, wa)
    report_wf = ReportWorkflow(meta, wa)

    approvals_pending: list[dict] = []

    def morning_cycle() -> None:
        logger.info("=== Ciclo Matinal 08:00 ===")
        analysis = analyze_wf.run(days=7)
        optimize_result = optimize_wf.run(analysis)
        approvals_pending.extend(optimize_result.approvals_sent)

    def afternoon_cycle() -> None:
        logger.info("=== Check da Tarde 14:00 ===")
        analysis = analyze_wf.run(days=1)
        optimize_wf.run(analysis)

    def daily_report_cycle() -> None:
        logger.info("=== Relatório Diário 20:30 ===")
        analysis = analyze_wf.run(days=1)
        optimize_result = optimize_wf.run(analysis)
        report_wf.run(analysis, optimize_result, approvals_pending[:])
        approvals_pending.clear()

    def recalibrate_thresholds() -> None:
        logger.info("=== Recalibração de Thresholds — Dia 7 ===")
        analysis = analyze_wf.run(days=7)
        proposal = calibration_wf.build_proposal(analysis)
        wa.send_message(proposal.render_message())

    inbox_cfg = _load_inbox_settings()
    inbox_wf = CampaignInboxWorkflow(meta, wa)
    inbox_root = Path(__file__).parent.parent / str(inbox_cfg.get("folder", "inbox"))
    inbox_dry_run = bool(inbox_cfg.get("dry_run", True))

    def inbox_cycle() -> None:
        logger.info("=== Campaign Inbox Poll (dry_run=%s) ===", inbox_dry_run)
        poll_once(inbox_root, inbox_wf, dry_run=inbox_dry_run)

    scheduler.register_morning_analysis(morning_cycle)
    scheduler.register_afternoon_check(afternoon_cycle)
    scheduler.register_daily_report(daily_report_cycle)
    scheduler.register_threshold_recalibration(recalibrate_thresholds, after_days=7)
    if inbox_cfg.get("enabled", True):
        scheduler.register_inbox_poll(inbox_cycle, minutes=int(inbox_cfg.get("poll_minutes", 15)))

    wa.send_message("🟢 Caio online. Monitorando campanhas Meta Ads 24/7. Raiz Vital.")

    logger.info("Scheduler iniciado. Ciclos registrados.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Caio encerrado pelo operador.")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
