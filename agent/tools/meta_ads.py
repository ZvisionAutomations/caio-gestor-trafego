"""Meta Ads Tool — wrapper do SDK oficial facebook-business para o Caio."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

try:
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.adset import AdSet
    from facebook_business.adobjects.ad import Ad
    from facebook_business.adobjects.adcreative import AdCreative
    from facebook_business.adobjects.campaign import Campaign
    from facebook_business.api import FacebookAdsApi
except ModuleNotFoundError:
    AdAccount = AdSet = Ad = AdCreative = Campaign = FacebookAdsApi = None  # type: ignore[assignment]

logger = logging.getLogger("caio.tools.meta_ads")


def _require_facebook_sdk() -> None:
    if FacebookAdsApi is None:
        raise ImportError(
            "facebook-business não instalado. Execute `pip install -r requirements.txt` "
            "antes de usar a Meta Ads API real."
        )


def _sdk_to_dict(obj: Any) -> dict:
    """Converte objetos do SDK preservando compatibilidade entre versões."""
    if hasattr(obj, "export_all_data"):
        return obj.export_all_data()
    if hasattr(obj, "get_all_data"):
        return obj.get_all_data()
    return dict(obj)


_META_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)

_INSIGHT_FIELDS = [
    "spend", "clicks", "impressions", "ctr", "frequency",
    "actions", "action_values", "reach", "cost_per_action_type",
    "unique_clicks", "unique_ctr",
]

_AD_FIELDS = ["id", "name", "status", "creative", "adset_id", "campaign_id", "created_time"]
_ADSET_FIELDS = [
    "id", "name", "status", "daily_budget", "lifetime_budget",
    "campaign_id", "targeting", "bid_amount", "billing_event",
    "optimization_goal", "created_time", "start_time", "end_time",
    "bid_strategy", "attribution_spec",
]
_CAMPAIGN_FIELDS = [
    "id", "name", "status", "objective", "daily_budget", "lifetime_budget",
    "buying_type", "bid_strategy", "created_time", "start_time",
]


@dataclass
class AdSetMetrics:
    """Métricas de um ad set para um período."""

    id: str
    name: str
    status: str
    daily_budget: float         # R$
    spend: float                # R$ gasto no período
    clicks: int
    impressions: int
    leads: int
    cpl: float                  # R$ custo por lead
    ctr: float                  # %
    frequency: float
    roas: float
    days_running: int
    days_above_cpl_threshold: int = 0
    days_below_champion_cpl: int = 0
    extra: dict = field(default_factory=dict)


@dataclass
class AdMetrics:
    """Métricas de um anúncio individual."""
    id: str
    name: str
    adset_id: str
    status: str
    spend: float
    clicks: int
    impressions: int
    leads: int
    cpl: float
    ctr: float
    frequency: float
    creative_id: str = ""
    extra: dict = field(default_factory=dict)


class MetaAdsTool:
    """
    Wrapper do Meta Marketing API para o agente Caio.
    Baseado nos padrões do meta-ads-ratos e SDK facebook-business.
    """

    def __init__(
        self,
        account_id: str | None = None,
        app_id: str | None = None,
        app_secret: str | None = None,
        access_token: str | None = None,
    ) -> None:
        _require_facebook_sdk()
        self.account_id = account_id or os.environ["META_ACCOUNT_ID"]
        _app_id = app_id or os.environ["META_APP_ID"]
        _app_secret = app_secret or os.environ["META_APP_SECRET"]
        _token = access_token or os.environ["META_ACCESS_TOKEN"]

        FacebookAdsApi.init(app_id=_app_id, app_secret=_app_secret, access_token=_token)
        self._account = AdAccount(self.account_id)
        logger.info("MetaAdsTool inicializado — conta %s", self.account_id)

    # ── Leitura de Insights ────────────────────────────────────────────────

    def get_account_insights(self, days: int = 1) -> dict[str, Any]:
        """
        Retorna insights consolidados da conta para os últimos N dias.

        Args:
            days: Número de dias para o período de análise (padrão: 1 = ontem)

        Returns:
            Dicionário com métricas consolidadas da conta
        """
        date_preset = self._days_to_preset(days)
        try:
            insights = self._account.get_insights(
                fields=[
                    "spend", "clicks", "impressions",
                    "actions", "action_values", "frequency",
                ],
                params={
                    "date_preset": date_preset,
                    "level": "account",
                },
            )
            if not insights:
                return {"spend": 0.0, "clicks": 0, "impressions": 0, "leads": 0}

            row = insights[0]
            leads = self._extract_action(row, "lead")
            spend = float(row.get("spend", 0))
            revenue = self._extract_action_value(row, "purchase")

            return {
                "spend": spend,
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "leads": leads,
                "cpl": round(spend / leads, 2) if leads > 0 else 0.0,
                "ctr": float(row.get("ctr", 0)),
                "revenue_estimated": revenue,
                "roas": round(revenue / spend, 2) if spend > 0 else 0.0,
                "period_days": days,
            }
        except Exception as exc:
            logger.error("Erro ao buscar insights da conta: %s", exc)
            raise

    def get_ad_set_insights(self, days: int = 7) -> list[AdSetMetrics]:
        """
        Retorna métricas de todos os ad sets ativos e pausados.

        Args:
            days: Período em dias para as métricas

        Returns:
            Lista de AdSetMetrics ordenada por CPL (menor primeiro)
        """
        date_preset = self._days_to_preset(days)
        try:
            ad_sets = self._account.get_ad_sets(fields=_ADSET_FIELDS)

            results: list[AdSetMetrics] = []
            for ads in ad_sets:
                insights = self._fetch_adset_insights_raw(ads["id"], date_preset)
                if insights is None:
                    continue

                spend = float(insights.get("spend", 0))
                clicks = int(insights.get("clicks", 0))
                impressions = int(insights.get("impressions", 0))
                leads = self._extract_action(insights, "lead")
                revenue = self._extract_action_value(insights, "purchase")
                cpl = round(spend / leads, 2) if leads > 0 else 0.0
                ctr = float(insights.get("ctr", 0))
                frequency = float(insights.get("frequency", 0))
                roas = round(revenue / spend, 2) if spend > 0 else 0.0

                days_running = self._calc_days_running(ads.get("start_time", ""))
                daily_budget = float(ads.get("daily_budget", 0)) / 100  # centavos → R$

                results.append(AdSetMetrics(
                    id=ads["id"],
                    name=ads["name"],
                    status=ads.get("status", "UNKNOWN"),
                    daily_budget=daily_budget,
                    spend=spend,
                    clicks=clicks,
                    impressions=impressions,
                    leads=leads,
                    cpl=cpl,
                    ctr=ctr,
                    frequency=frequency,
                    roas=roas,
                    days_running=days_running,
                ))

            results.sort(key=lambda x: x.cpl if x.cpl > 0 else float("inf"))
            return results

        except Exception as exc:
            logger.error("Erro ao buscar ad sets: %s", exc)
            raise

    def get_adset_insights(self, adset_id: str, days: int = 7) -> dict[str, Any]:
        """
        Retorna insights de um ad set específico.

        Args:
            adset_id: ID do ad set
            days: Período em dias para as métricas

        Returns:
            Dicionário com métricas normalizadas do ad set
        """
        date_preset = self._days_to_preset(days)
        try:
            raw = self._fetch_adset_insights_raw(adset_id, date_preset)
            if raw is None:
                return {"spend": 0.0, "clicks": 0, "impressions": 0, "leads": 0}
            return self._normalize_insight_row(raw, days)
        except Exception as exc:
            logger.error("Erro ao buscar insights do ad set %s: %s", adset_id, exc)
            raise

    # ── Campanhas ──────────────────────────────────────────────────────────

    def get_campaigns(self, status_filter: str | None = None) -> list[dict]:
        """
        Lista campanhas da conta.

        Args:
            status_filter: Filtro de status (ex: "ACTIVE", "PAUSED") — None retorna todos

        Returns:
            Lista de dicts com dados das campanhas
        """
        try:
            params = {}
            if status_filter:
                params["filtering"] = [{"field": "status", "operator": "IN", "value": [status_filter]}]
            campaigns = self._account.get_campaigns(fields=_CAMPAIGN_FIELDS, params=params)
            return [_sdk_to_dict(c) for c in campaigns]
        except Exception as exc:
            logger.error("Erro ao listar campanhas: %s", exc)
            raise

    def get_campaign(self, campaign_id: str) -> dict:
        """
        Retorna dados de uma campanha específica.

        Args:
            campaign_id: ID da campanha

        Returns:
            Dict com dados da campanha
        """
        try:
            campaign = Campaign(campaign_id)
            return _sdk_to_dict(campaign.api_get(fields=_CAMPAIGN_FIELDS))
        except Exception as exc:
            logger.error("Erro ao buscar campanha %s: %s", campaign_id, exc)
            raise

    def get_campaign_insights(self, campaign_id: str, days: int = 7) -> dict[str, Any]:
        """
        Retorna insights de uma campanha específica.

        Args:
            campaign_id: ID da campanha
            days: Período em dias para as métricas

        Returns:
            Dicionário com métricas normalizadas da campanha
        """
        date_preset = self._days_to_preset(days)
        try:
            campaign = Campaign(campaign_id)
            insights = campaign.get_insights(
                fields=_INSIGHT_FIELDS,
                params={"date_preset": date_preset},
            )
            if not insights:
                return {"spend": 0.0, "clicks": 0, "impressions": 0, "leads": 0}
            return self._normalize_insight_row(dict(insights[0]), days)
        except Exception as exc:
            logger.error("Erro ao buscar insights da campanha %s: %s", campaign_id, exc)
            raise

    # ── Ad Sets Expandido ─────────────────────────────────────────────────

    def get_adsets_by_campaign(self, campaign_id: str) -> list[dict]:
        """
        Lista ad sets de uma campanha específica.

        Args:
            campaign_id: ID da campanha

        Returns:
            Lista de dicts com dados dos ad sets
        """
        try:
            campaign = Campaign(campaign_id)
            ad_sets = campaign.get_ad_sets(fields=_ADSET_FIELDS)
            return [_sdk_to_dict(a) for a in ad_sets]
        except Exception as exc:
            logger.error("Erro ao listar ad sets da campanha %s: %s", campaign_id, exc)
            raise

    # ── Anúncios ──────────────────────────────────────────────────────────

    def get_ads(self, status_filter: str | None = None) -> list[dict]:
        """
        Lista anúncios da conta.

        Args:
            status_filter: Filtro de status (ex: "ACTIVE", "PAUSED") — None retorna todos

        Returns:
            Lista de dicts com dados dos anúncios
        """
        try:
            params = {}
            if status_filter:
                params["filtering"] = [{"field": "status", "operator": "IN", "value": [status_filter]}]
            ads = self._account.get_ads(fields=_AD_FIELDS, params=params)
            return [_sdk_to_dict(a) for a in ads]
        except Exception as exc:
            logger.error("Erro ao listar anúncios: %s", exc)
            raise

    def get_ad(self, ad_id: str) -> dict:
        """
        Retorna dados de um anúncio específico.

        Args:
            ad_id: ID do anúncio

        Returns:
            Dict com dados do anúncio incluindo status efetivo e bid
        """
        try:
            ad = Ad(ad_id)
            return _sdk_to_dict(ad.api_get(fields=_AD_FIELDS + ["effective_status", "bid_amount"]))
        except Exception as exc:
            logger.error("Erro ao buscar anúncio %s: %s", ad_id, exc)
            raise

    def get_ads_by_adset(self, adset_id: str) -> list[dict]:
        """
        Lista anúncios de um ad set específico.

        Args:
            adset_id: ID do ad set

        Returns:
            Lista de dicts com dados dos anúncios
        """
        try:
            adset = AdSet(adset_id)
            ads = adset.get_ads(fields=_AD_FIELDS + ["effective_status"])
            return [_sdk_to_dict(a) for a in ads]
        except Exception as exc:
            logger.error("Erro ao listar anúncios do ad set %s: %s", adset_id, exc)
            raise

    def get_ads_by_campaign(self, campaign_id: str) -> list[dict]:
        """
        Lista anúncios de uma campanha específica.

        Args:
            campaign_id: ID da campanha

        Returns:
            Lista de dicts com dados dos anúncios
        """
        try:
            campaign = Campaign(campaign_id)
            ads = campaign.get_ads(fields=_AD_FIELDS + ["effective_status"])
            return [_sdk_to_dict(a) for a in ads]
        except Exception as exc:
            logger.error("Erro ao listar anúncios da campanha %s: %s", campaign_id, exc)
            raise

    def get_ad_insights(self, ad_id: str, days: int = 7) -> dict[str, Any]:
        """
        Retorna insights de um anúncio específico.

        Args:
            ad_id: ID do anúncio
            days: Período em dias para as métricas

        Returns:
            Dicionário com métricas normalizadas do anúncio
        """
        date_preset = self._days_to_preset(days)
        try:
            raw = self._fetch_ad_insights_raw(ad_id, date_preset)
            if raw is None:
                return {"spend": 0.0, "clicks": 0, "impressions": 0, "leads": 0}
            return self._normalize_insight_row(raw, days)
        except Exception as exc:
            logger.error("Erro ao buscar insights do anúncio %s: %s", ad_id, exc)
            raise

    # ── Criativos ─────────────────────────────────────────────────────────

    def get_creative(self, creative_id: str) -> dict:
        """
        Retorna dados de um criativo específico.

        Args:
            creative_id: ID do criativo

        Returns:
            Dict com dados do criativo
        """
        _CREATIVE_FIELDS = [
            "id", "name", "title", "body", "object_type",
            "image_url", "thumbnail_url", "video_id", "call_to_action_type",
        ]
        try:
            creative = AdCreative(creative_id)
            return _sdk_to_dict(creative.api_get(fields=_CREATIVE_FIELDS))
        except Exception as exc:
            logger.error("Erro ao buscar criativo %s: %s", creative_id, exc)
            raise

    def get_creatives_by_ad(self, ad_id: str) -> list[dict]:
        """
        Retorna criativos associados a um anúncio.

        Args:
            ad_id: ID do anúncio

        Returns:
            Lista de dicts com dados dos criativos
        """
        try:
            ad_data = self.get_ad(ad_id)
            creative_info = ad_data.get("creative", {})
            creative_id = creative_info.get("id") if isinstance(creative_info, dict) else creative_info
            if not creative_id:
                return []
            return [self.get_creative(str(creative_id))]
        except Exception as exc:
            logger.error("Erro ao buscar criativos do anúncio %s: %s", ad_id, exc)
            raise

    def get_images(self) -> list[dict]:
        """
        Lista imagens de anúncio da conta.

        Returns:
            Lista de dicts com dados das imagens
        """
        try:
            if not hasattr(self._account, "get_ad_images"):
                # TODO: verificar disponibilidade na versão de Marketing API em produção.
                logger.warning("get_ad_images indisponível no SDK atual")
                return []
            images = self._account.get_ad_images(
                fields=["id", "name", "hash", "url", "url_128", "created_time", "status"]
            )
            return [_sdk_to_dict(img) for img in images]
        except Exception as exc:
            logger.error("Erro ao listar imagens: %s", exc)
            raise

    def get_videos(self) -> list[dict]:
        """
        Lista vídeos de anúncio da conta.

        Returns:
            Lista de dicts com dados dos vídeos
        """
        try:
            if not hasattr(self._account, "get_ad_videos"):
                # TODO: verificar disponibilidade na versão de Marketing API em produção.
                logger.warning("get_ad_videos indisponível no SDK atual")
                return []
            videos = self._account.get_ad_videos(
                fields=["id", "title", "description", "thumbnail", "created_time", "length"]
            )
            return [_sdk_to_dict(v) for v in videos]
        except Exception as exc:
            logger.error("Erro ao listar vídeos: %s", exc)
            raise

    # ── Audiências ────────────────────────────────────────────────────────

    def get_custom_audiences(self) -> list[dict]:
        """
        Lista audiências customizadas da conta.

        Returns:
            Lista de dicts com dados das audiências
        """
        _AUDIENCE_FIELDS = [
            "id", "name", "description", "subtype",
            "approximate_count", "data_source", "created_time",
        ]
        try:
            audiences = self._account.get_custom_audiences(fields=_AUDIENCE_FIELDS)
            return [_sdk_to_dict(a) for a in audiences]
        except Exception as exc:
            logger.error("Erro ao listar audiências customizadas: %s", exc)
            raise

    def get_lookalike_audiences(self) -> list[dict]:
        """
        Lista audiências lookalike da conta.

        Returns:
            Lista de dicts com dados das audiências lookalike
        """
        try:
            all_audiences = self.get_custom_audiences()
            return [a for a in all_audiences if a.get("subtype") == "LOOKALIKE"]
        except Exception as exc:
            logger.error("Erro ao listar lookalike audiences: %s", exc)
            raise

    # ── Atividades ────────────────────────────────────────────────────────

    def get_activities(self, limit: int = 50) -> list[dict]:
        """
        Lista atividades recentes da conta.

        Args:
            limit: Número máximo de registros a retornar

        Returns:
            Lista de dicts com dados de atividades
        """
        _ACTIVITY_FIELDS = [
            "actor_name", "event_type", "object_id", "object_name",
            "event_time", "translated_event_type",
        ]
        try:
            activities = self._account.get_activities(
                fields=_ACTIVITY_FIELDS,
                params={"limit": limit},
            )
            return [_sdk_to_dict(a) for a in activities]
        except Exception as exc:
            logger.error("Erro ao listar atividades da conta: %s", exc)
            raise

    def get_activities_by_adset(self, adset_id: str, limit: int = 20) -> list[dict]:
        """
        Lista atividades de um ad set específico.

        Args:
            adset_id: ID do ad set
            limit: Número máximo de registros a retornar

        Returns:
            Lista de dicts com dados de atividades do ad set
        """
        _ACTIVITY_FIELDS = [
            "actor_name", "event_type", "object_id", "object_name",
            "event_time", "translated_event_type",
        ]
        try:
            adset = AdSet(adset_id)
            activities = adset.get_activities(
                fields=_ACTIVITY_FIELDS,
                params={"limit": limit},
            )
            return [_sdk_to_dict(a) for a in activities]
        except Exception as exc:
            logger.error("Erro ao listar atividades do ad set %s: %s", adset_id, exc)
            raise

    # ── Detecção de Fadiga ────────────────────────────────────────────────

    def get_fatigued_ads_in_adset(
        self,
        adset_id: str,
        frequency_threshold: float = 3.5,
        days: int = 3,
    ) -> list[dict]:
        """
        Identifica anúncios fatigados dentro de um ad set — frequência > threshold.
        Essencial para pausar criativos específicos sem parar o ad set inteiro.

        Args:
            adset_id: ID do ad set a analisar
            frequency_threshold: Frequência mínima para classificar como fatigado
            days: Período em dias para os insights

        Returns:
            Lista de dicts com anúncios fatigados, ordenada por frequency decrescente
        """
        date_preset = self._days_to_preset(days)
        fatigued: list[dict] = []
        try:
            ads = self.get_ads_by_adset(adset_id)
            for ad in ads:
                if ad.get("status") != "ACTIVE":
                    continue
                raw = self._fetch_ad_insights_raw(ad["id"], date_preset)
                if raw is None:
                    continue
                frequency = float(raw.get("frequency", 0))
                if frequency >= frequency_threshold:
                    fatigued.append({
                        "ad_id": ad["id"],
                        "ad_name": ad.get("name", ""),
                        "adset_id": adset_id,
                        "frequency": frequency,
                        "clicks": int(raw.get("clicks", 0)),
                        "ctr": float(raw.get("ctr", 0)),
                        "spend": float(raw.get("spend", 0)),
                    })
            fatigued.sort(key=lambda x: x["frequency"], reverse=True)
            return fatigued
        except Exception as exc:
            logger.error("Erro ao detectar fadiga no ad set %s: %s", adset_id, exc)
            raise

    # ── Ações Autônomas ────────────────────────────────────────────────────

    @_META_RETRY
    def _update_ad_status(self, ad_id: str, status: str) -> None:
        ad = Ad(ad_id)
        ad.api_update(params={"status": status})

    @_META_RETRY
    def _update_adset_status(self, adset_id: str, status: str) -> None:
        ads = AdSet(adset_id)
        ads.api_update(params={"status": status})

    @_META_RETRY
    def _update_adset_bid(self, adset_id: str, adjustment_pct: float) -> dict[str, float]:
        ads = AdSet(adset_id)
        current = ads.api_get(fields=["bid_amount"])
        current_bid = float(current.get("bid_amount", 0))

        if current_bid == 0:
            raise ValueError("Bid atual não encontrado")

        new_bid = int(current_bid * (1 + adjustment_pct))
        ads.api_update(params={"bid_amount": new_bid})
        return {"bid_before": current_bid / 100, "bid_after": new_bid / 100}

    def pause_ad(self, ad_id: str, reason: str = "") -> dict[str, Any]:
        """
        Pausa um anúncio específico.

        Args:
            ad_id: ID do anúncio a pausar
            reason: Motivo da pausa (para log)

        Returns:
            Dicionário com resultado da operação
        """
        try:
            self._update_ad_status(ad_id, Ad.Status.paused)
            logger.info("Anúncio %s pausado — motivo: %s", ad_id, reason or "não informado")
            return {"success": True, "ad_id": ad_id, "action": "paused", "reason": reason}
        except Exception as exc:
            logger.error("Erro ao pausar anúncio %s: %s", ad_id, exc)
            return {"success": False, "ad_id": ad_id, "error": str(exc)}

    def pause_ad_set(self, adset_id: str, reason: str = "") -> dict[str, Any]:
        """
        Pausa um ad set inteiro.

        Args:
            adset_id: ID do ad set a pausar
            reason: Motivo da pausa (para log)

        Returns:
            Dicionário com resultado da operação
        """
        try:
            self._update_adset_status(adset_id, AdSet.Status.paused)
            logger.info("Ad set %s pausado — motivo: %s", adset_id, reason or "não informado")
            return {"success": True, "adset_id": adset_id, "action": "paused", "reason": reason}
        except Exception as exc:
            logger.error("Erro ao pausar ad set %s: %s", adset_id, exc)
            return {"success": False, "adset_id": adset_id, "error": str(exc)}

    def resume_ad(self, ad_id: str, reason: str = "") -> dict[str, Any]:
        """
        Reativa um anúncio pausado.

        Args:
            ad_id: ID do anúncio a reativar
            reason: Motivo da reativação (para log)

        Returns:
            Dicionário com resultado da operação
        """
        try:
            self._update_ad_status(ad_id, Ad.Status.active)
            logger.info("Anúncio %s reativado — motivo: %s", ad_id, reason or "não informado")
            return {"success": True, "ad_id": ad_id, "action": "resumed", "reason": reason}
        except Exception as exc:
            logger.error("Erro ao reativar anúncio %s: %s", ad_id, exc)
            return {"success": False, "ad_id": ad_id, "error": str(exc)}

    def adjust_bid(self, adset_id: str, adjustment_pct: float) -> dict[str, Any]:
        """
        Ajusta o bid de um ad set dentro do limite de ±20%.

        Args:
            adset_id: ID do ad set
            adjustment_pct: Ajuste em percentual (ex: -0.10 para -10%, +0.10 para +10%)

        Returns:
            Dicionário com resultado da operação
        """
        if abs(adjustment_pct) > 0.20:
            return {
                "success": False,
                "adset_id": adset_id,
                "error": f"Ajuste {adjustment_pct:.0%} excede o limite de ±20%",
            }
        try:
            bid = self._update_adset_bid(adset_id, adjustment_pct)
            current_bid = bid["bid_before"] * 100
            if current_bid == 0:
                return {"success": False, "adset_id": adset_id, "error": "Bid atual não encontrado"}

            logger.info(
                "Bid ajustado em %s — %.0f → %d (%+.0f%%)",
                adset_id, bid["bid_before"] * 100, bid["bid_after"] * 100, adjustment_pct * 100,
            )
            return {
                "success": True,
                "adset_id": adset_id,
                "bid_before": current_bid / 100,  # centavos → R$
                "bid_after": bid["bid_after"],
                "adjustment_pct": adjustment_pct,
            }
        except Exception as exc:
            logger.error("Erro ao ajustar bid %s: %s", adset_id, exc)
            return {"success": False, "adset_id": adset_id, "error": str(exc)}

    def duplicate_ad_set(
        self,
        adset_id: str,
        new_daily_budget: float,
        new_name_suffix: str = "COPY",
    ) -> dict[str, Any]:
        """
        Duplica um ad set com novo budget.
        APENAS chamar após confirmação de que o budget cabe no total aprovado.

        Args:
            adset_id: ID do ad set a duplicar
            new_daily_budget: Novo budget diário em R$ para o ad set duplicado
            new_name_suffix: Sufixo para o nome do novo ad set

        Returns:
            Dicionário com resultado da operação e ID do novo ad set
        """
        try:
            ads = AdSet(adset_id)
            current = ads.api_get(fields=["name", "campaign_id", "targeting", "bid_amount"])

            new_name = f"{current['name']} — {new_name_suffix}"
            budget_centavos = int(new_daily_budget * 100)

            new_adset = self._account.create_ad_set(
                fields=[],
                params={
                    "name": new_name,
                    "campaign_id": current["campaign_id"],
                    "daily_budget": budget_centavos,
                    "targeting": current.get("targeting", {}),
                    "bid_amount": current.get("bid_amount", 0),
                    "billing_event": "IMPRESSIONS",
                    "optimization_goal": "LEAD_GENERATION",
                    "status": "PAUSED",  # Começa pausado para revisão manual
                },
            )

            logger.info(
                "Ad set duplicado: %s → %s (budget R$%.2f)",
                adset_id, new_adset["id"], new_daily_budget,
            )
            return {
                "success": True,
                "source_adset_id": adset_id,
                "new_adset_id": new_adset["id"],
                "new_name": new_name,
                "daily_budget": new_daily_budget,
                "status": "PAUSED",
                "note": "Ad set criado pausado — reativar após verificação",
            }
        except Exception as exc:
            logger.error("Erro ao duplicar ad set %s: %s", adset_id, exc)
            return {"success": False, "adset_id": adset_id, "error": str(exc)}

    def resume_ad_set(self, adset_id: str, reason: str = "") -> dict[str, Any]:
        """
        Reativa um ad set pausado.

        Args:
            adset_id: ID do ad set a reativar
            reason: Motivo da reativação (para log)

        Returns:
            Dicionário com resultado da operação
        """
        try:
            self._update_adset_status(adset_id, AdSet.Status.active)
            logger.info("Ad set %s reativado — motivo: %s", adset_id, reason or "não informado")
            return {"success": True, "adset_id": adset_id, "action": "resumed", "reason": reason}
        except Exception as exc:
            logger.error("Erro ao reativar ad set %s: %s", adset_id, exc)
            return {"success": False, "adset_id": adset_id, "error": str(exc)}

    def update_ad_set_budget(
        self,
        adset_id: str,
        new_daily_budget: float,
        reason: str = "",
    ) -> dict[str, Any]:
        """
        Atualiza o budget diário de um ad set.
        Uso autônomo limitado a ±20% via adjust_bid — para mudanças maiores, requer aprovação.

        Args:
            adset_id: ID do ad set
            new_daily_budget: Novo budget diário em R$
            reason: Motivo da alteração (para log)

        Returns:
            Dicionário com resultado da operação
        """
        try:
            budget_centavos = int(new_daily_budget * 100)
            ads = AdSet(adset_id)
            ads.api_update(params={"daily_budget": budget_centavos})
            logger.info(
                "Budget do ad set %s atualizado para R$%.2f — motivo: %s",
                adset_id, new_daily_budget, reason or "não informado",
            )
            return {
                "success": True,
                "adset_id": adset_id,
                "new_daily_budget": new_daily_budget,
                "reason": reason,
            }
        except Exception as exc:
            logger.error("Erro ao atualizar budget do ad set %s: %s", adset_id, exc)
            return {"success": False, "adset_id": adset_id, "error": str(exc)}

    # ── Helpers ────────────────────────────────────────────────────────────

    def _fetch_adset_insights_raw(self, adset_id: str, date_preset: str) -> dict | None:
        try:
            ads = AdSet(adset_id)
            insights = ads.get_insights(
                fields=_INSIGHT_FIELDS,
                params={"date_preset": date_preset},
            )
            return dict(insights[0]) if insights else None
        except Exception as exc:
            logger.warning("Insights não disponíveis para %s: %s", adset_id, exc)
            return None

    def _fetch_ad_insights_raw(self, ad_id: str, date_preset: str) -> dict | None:
        try:
            ad = Ad(ad_id)
            insights = ad.get_insights(fields=_INSIGHT_FIELDS, params={"date_preset": date_preset})
            return dict(insights[0]) if insights else None
        except Exception as exc:
            logger.warning("Insights não disponíveis para anúncio %s: %s", ad_id, exc)
            return None

    def _normalize_insight_row(self, row: dict, days: int) -> dict[str, Any]:
        spend = float(row.get("spend", 0))
        leads = self._extract_action(row, "lead")
        revenue = self._extract_action_value(row, "purchase")
        return {
            "spend": spend,
            "clicks": int(row.get("clicks", 0)),
            "impressions": int(row.get("impressions", 0)),
            "reach": int(row.get("reach", 0)),
            "leads": leads,
            "cpl": round(spend / leads, 2) if leads > 0 else 0.0,
            "ctr": float(row.get("ctr", 0)),
            "unique_ctr": float(row.get("unique_ctr", 0)),
            "frequency": float(row.get("frequency", 0)),
            "revenue_estimated": revenue,
            "roas": round(revenue / spend, 2) if spend > 0 else 0.0,
            "period_days": days,
        }

    @staticmethod
    def _days_to_preset(days: int) -> str:
        presets = {
            1: "yesterday",
            3: "last_3d",
            7: "last_7d",
            14: "last_14d",
            28: "last_28d",
            30: "last_30d",
            90: "last_90d",
        }
        return presets.get(days, "last_7d")

    @staticmethod
    def _extract_action(row: dict, action_type: str) -> int:
        for action in row.get("actions", []):
            if action.get("action_type") == action_type:
                return int(float(action.get("value", 0)))
        return 0

    @staticmethod
    def _extract_action_value(row: dict, action_type: str) -> float:
        for av in row.get("action_values", []):
            if av.get("action_type") == action_type:
                return float(av.get("value", 0))
        return 0.0

    @staticmethod
    def _calc_days_running(start_time: str) -> int:
        if not start_time:
            return 0
        try:
            start = date.fromisoformat(start_time[:10])
            return (date.today() - start).days
        except (ValueError, TypeError):
            return 0
