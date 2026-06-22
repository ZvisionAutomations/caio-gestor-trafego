"""Entry point do Caio — inicializa tools e registra ciclos no scheduler."""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "config" / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("caio.main")


def _load_settings_section(section: str) -> dict:
    """Lê uma seção do settings.yaml (fail-safe com defaults seguros)."""
    import yaml

    settings_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    try:
        data = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
        return dict(data.get(section, {}))
    except Exception as exc:  # noqa: BLE001 — config nunca derruba o boot
        logger.warning("Não foi possível ler '%s' do settings.yaml: %s", section, exc)
        return {}


def _start_scheduler_background(scheduler) -> threading.Thread:
    thread = threading.Thread(
        target=scheduler.start,
        name="caio-scheduler",
        daemon=True,
    )
    thread.start()
    logger.info("Scheduler iniciado em thread de background.")
    return thread


def main() -> None:
    from .inbound_handler import create_app
    from .business_signal import BusinessSignalReader
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

    # Trava de escala (story-060): injeta business signal + tetos do settings.
    # Sem CAIO_DATABASE_URL ou tetos=0 → duplicação autônoma bloqueada (seguro).
    budget_cfg = _load_settings_section("budget")
    optimize_wf = OptimizeWorkflow(
        meta,
        wa,
        business_signal_reader=BusinessSignalReader(),
        max_new_adsets_per_day=int(budget_cfg.get("max_new_adsets_per_day", 0)),
        max_duplications_per_adset_per_day=int(budget_cfg.get("max_duplications_per_adset_per_day", 0)),
        tenant_id=os.getenv("CAIO_SIGNAL_TENANT_ID", ""),
    )

    analyze_wf = AnalyzeWorkflow(meta)
    calibration_wf = CalibrationWorkflow()
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

    inbox_cfg = _load_settings_section("inbox")
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

    inbound_cfg = _load_settings_section("inbound")
    inbound_enabled = bool(inbound_cfg.get("enabled", False))
    logger.info("Scheduler configurado. Ciclos registrados. inbound_enabled=%s", inbound_enabled)
    try:
        if inbound_enabled:
            import uvicorn

            from .caio import build_caio
            from .conversation import CaioConversationResponder, GroupMemory
            from .spend_gate import SpendGate

            group_id = str(inbound_cfg.get("group_id") or wa.group_id)
            host = str(inbound_cfg.get("host", "0.0.0.0"))
            port = int(inbound_cfg.get("port", 8010))
            secret_env = str(inbound_cfg.get("webhook_secret_env", "CAIO_INBOUND_WEBHOOK_SECRET"))
            memory_turns = int(inbound_cfg.get("memory_turns", 8))
            approval_cfg = _load_settings_section("approval")
            responder = CaioConversationResponder(
                caio_agent=build_caio(meta, wa),
                memory=GroupMemory(max_turns=memory_turns),
                spend_gate=SpendGate(
                    meta_tool=meta,
                    whatsapp_tool=wa,
                    timeout_minutes=int(approval_cfg.get("timeout_hours", 2) * 60),
                ),
            )
            app = create_app(
                whatsapp_tool=wa,
                allowed_group_id=group_id,
                webhook_secret=os.getenv(secret_env, ""),
                response_builder=responder,
            )
            _start_scheduler_background(scheduler)
            logger.info("Inbound HTTP iniciando em %s:%s para grupo %s", host, port, group_id)
            uvicorn.run(app, host=host, port=port, log_level=os.getenv("LOG_LEVEL", "info").lower())
        else:
            scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Caio encerrado pelo operador.")
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
