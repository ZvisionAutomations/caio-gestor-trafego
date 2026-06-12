"""Read-only Business Signal access and scale guardrails for Caio."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class BusinessSignal:
    ad_id: str
    adset_id: str
    campaign_id: str
    paid_orders: int
    revenue_cents: int
    strongest_confidence: str = "low"

    @property
    def has_paid_sale(self) -> bool:
        return self.paid_orders > 0


class BusinessSignalReader:
    """Reads only the PII-safe caio_attribution_signal view."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = (database_url or os.getenv("CAIO_DATABASE_URL") or "").replace(
            "+asyncpg", ""
        )

    async def get_adset_signal(self, tenant_id: str, adset_id: str, days: int = 7) -> BusinessSignal:
        if not self.database_url:
            return BusinessSignal("", adset_id, "", 0, 0)
        import asyncpg

        conn = await asyncpg.connect(self.database_url)
        try:
            row = await conn.fetchrow(
                """
                SELECT
                    COALESCE(MAX(ad_id), '') AS ad_id,
                    COALESCE(MAX(campaign_id), '') AS campaign_id,
                    COUNT(*) FILTER (WHERE is_paid) AS paid_orders,
                    COALESCE(SUM(revenue_cents) FILTER (WHERE is_paid), 0) AS revenue_cents,
                    CASE
                        WHEN BOOL_OR(attribution_confidence = 'high') THEN 'high'
                        WHEN BOOL_OR(attribution_confidence = 'medium') THEN 'medium'
                        ELSE 'low'
                    END AS strongest_confidence
                FROM caio_attribution_signal
                WHERE tenant_id = $1
                  AND adset_id = $2
                  AND COALESCE(paid_at, order_created_at, captured_at) >= NOW() - ($3::TEXT || ' days')::INTERVAL
                """,
                tenant_id,
                adset_id,
                days,
            )
        finally:
            await conn.close()

        data = dict(row or {})
        return BusinessSignal(
            ad_id=str(data.get("ad_id") or ""),
            adset_id=adset_id,
            campaign_id=str(data.get("campaign_id") or ""),
            paid_orders=int(data.get("paid_orders") or 0),
            revenue_cents=int(data.get("revenue_cents") or 0),
            strongest_confidence=str(data.get("strongest_confidence") or "low"),
        )


@dataclass(frozen=True)
class ScaleDecision:
    allowed: bool
    reason: str
    checked_at: str


def evaluate_scale_guardrails(
    *,
    business_signal: BusinessSignal,
    max_new_adsets_per_day: int,
    max_duplications_per_adset_per_day: int,
) -> ScaleDecision:
    now = datetime.now(timezone.utc).isoformat()
    if max_new_adsets_per_day <= 0 or max_duplications_per_adset_per_day <= 0:
        return ScaleDecision(False, "financial guardrails missing: autonomous scale locked", now)
    if not business_signal.has_paid_sale:
        return ScaleDecision(False, "business signal missing: no paid attributed sale in window", now)
    return ScaleDecision(True, "business signal and financial guardrails satisfied", now)


def row_to_signal(row: dict[str, Any]) -> BusinessSignal:
    return BusinessSignal(
        ad_id=str(row.get("ad_id") or ""),
        adset_id=str(row.get("adset_id") or ""),
        campaign_id=str(row.get("campaign_id") or ""),
        paid_orders=int(row.get("paid_orders") or 0),
        revenue_cents=int(row.get("revenue_cents") or 0),
        strongest_confidence=str(row.get("strongest_confidence") or "low"),
    )
