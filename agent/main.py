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


def main() -> None:
    from .tools.meta_ads import MetaAdsTool
    from .tools.whatsapp import WhatsAppTool
    from .tools.scheduler import CaioScheduler
    from .workflows.analyze import AnalyzeWorkflow
    from .workflows.optimize import OptimizeWorkflow
    from .workflows.approve import ApproveWorkflow
    from .workflows.report import ReportWorkflow

    logger.info("Caio — Gestor de Tráfego Raiz Vital iniciando...")

    meta = MetaAdsTool()
    wa = WhatsAppTool()
    scheduler = CaioScheduler()

    analyze_wf = AnalyzeWorkflow(meta)
    optimize_wf = OptimizeWorkflow(meta, wa)
    approve_wf = ApproveWorkflow(meta, wa)
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
        wa.send_message(
            "📊 Caio: Período de 7 dias completo. "
            "Dados insuficientes para recalibração automática neste ciclo "
            "(mínimo 500 cliques necessário). Thresholds mantidos."
        )

    scheduler.register_morning_analysis(morning_cycle)
    scheduler.register_afternoon_check(afternoon_cycle)
    scheduler.register_daily_report(daily_report_cycle)
    scheduler.register_threshold_recalibration(recalibrate_thresholds, after_days=7)

    wa.send_message("🟢 Caio online. Monitorando campanhas Meta Ads 24/7. Raiz Vital.")

    logger.info("Scheduler iniciado. Ciclos registrados.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Caio encerrado pelo operador.")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
