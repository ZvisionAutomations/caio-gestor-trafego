"""Scheduler — cron jobs do Caio via APScheduler (08:00/14:00/20:30 BRT)."""
from __future__ import annotations

import logging
from typing import Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("caio.tools.scheduler")

_TIMEZONE = "America/Sao_Paulo"


class CaioScheduler:
    """Gerencia os ciclos de operação do Caio via APScheduler."""

    def __init__(self, timezone: str = _TIMEZONE) -> None:
        self._scheduler = BlockingScheduler(timezone=timezone)
        self._timezone = timezone
        logger.info("CaioScheduler inicializado — timezone: %s", timezone)

    def register_morning_analysis(self, func: Callable) -> None:
        """Registra o ciclo de análise matinal às 08:00 BRT."""
        self._scheduler.add_job(
            func,
            CronTrigger(hour=8, minute=0, timezone=self._timezone),
            id="morning_analysis",
            name="Análise Matinal Caio",
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info("Ciclo matinal registrado — 08:00 %s", self._timezone)

    def register_afternoon_check(self, func: Callable) -> None:
        """Registra o check da tarde às 14:00 BRT."""
        self._scheduler.add_job(
            func,
            CronTrigger(hour=14, minute=0, timezone=self._timezone),
            id="afternoon_check",
            name="Check da Tarde Caio",
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info("Ciclo da tarde registrado — 14:00 %s", self._timezone)

    def register_daily_report(self, func: Callable) -> None:
        """Registra o relatório diário às 20:30 BRT."""
        self._scheduler.add_job(
            func,
            CronTrigger(hour=20, minute=30, timezone=self._timezone),
            id="daily_report",
            name="Relatório Diário Caio",
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info("Relatório diário registrado — 20:30 %s", self._timezone)

    def register_inbox_poll(self, func: Callable, minutes: int = 15) -> None:
        """Registra o polling da pasta de handoff do Campaign Inbox (story-058)."""
        self._scheduler.add_job(
            func,
            IntervalTrigger(minutes=minutes, timezone=self._timezone),
            id="inbox_poll",
            name="Campaign Inbox Poll",
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1,
        )
        logger.info("Ciclo de inbox registrado — a cada %d min", minutes)

    def register_threshold_recalibration(self, func: Callable, after_days: int = 7) -> None:
        """
        Registra recalibração de thresholds após N dias de operação.
        Executa uma vez às 09:00 do dia calculado.
        """
        from datetime import datetime, timedelta
        run_date = datetime.now() + timedelta(days=after_days)
        run_date = run_date.replace(hour=9, minute=0, second=0, microsecond=0)

        self._scheduler.add_job(
            func,
            "date",
            run_date=run_date,
            id="threshold_recalibration",
            name="Recalibração de Thresholds",
            replace_existing=True,
        )
        logger.info("Recalibração agendada para %s", run_date.isoformat())

    def start(self) -> None:
        """Inicia o scheduler. Bloqueia o processo principal."""
        logger.info(
            "CaioScheduler iniciando — jobs registrados: %d",
            len(self._scheduler.get_jobs()),
        )
        for job in self._scheduler.get_jobs():
            next_run = getattr(job, "next_run_time", None) or "(pendente — antes do start)"
            logger.info("  Job: %s | Próxima execução: %s", job.name, next_run)
        self._scheduler.start()

    def shutdown(self) -> None:
        """Para o scheduler graciosamente."""
        self._scheduler.shutdown(wait=False)
        logger.info("CaioScheduler encerrado")
