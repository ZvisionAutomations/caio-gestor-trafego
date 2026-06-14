"""Campaign Inbox parser, validator and Meta object translator."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


class CampaignSpec(BaseModel):
    name: str
    product: str
    objective: str = "OUTCOME_ENGAGEMENT"
    status_on_upload: str = "paused"
    page_id: str
    whatsapp_phone_number: str
    version: str = "v1"

    @field_validator("version")
    @classmethod
    def normalize_version(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if not normalized.startswith("v") or not normalized[1:].isdigit():
            raise ValueError("version must look like v1, v2, v3...")
        return normalized

    @field_validator("objective")
    @classmethod
    def normalize_objective(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized == "MESSAGES":
            return "OUTCOME_ENGAGEMENT"
        if normalized not in {"OUTCOME_ENGAGEMENT", "OUTCOME_SALES"}:
            raise ValueError("objective must be OUTCOME_ENGAGEMENT or OUTCOME_SALES")
        return normalized

    @field_validator("status_on_upload")
    @classmethod
    def require_paused(cls, value: str) -> str:
        if value.strip().lower() != "paused":
            raise ValueError("status_on_upload must be paused")
        return "PAUSED"


class TargetingSpec(BaseModel):
    geo_locations: dict[str, Any]
    age_min: int | None = None
    age_max: int | None = None
    genders: list[int] | None = None


class AdSetSpec(BaseModel):
    name: str
    daily_budget_brl: float = Field(gt=0)
    targeting: TargetingSpec | None = None
    age_min: int | None = None
    age_max: int | None = None
    gender: str | None = None
    locations: list[str] | None = None
    optimization_goal: str = "CONVERSATIONS"
    billing_event: str = "IMPRESSIONS"

    def meta_targeting(self) -> dict[str, Any]:
        if self.targeting:
            return self.targeting.model_dump(exclude_none=True)
        if not self.locations:
            raise ValueError("adset.targeting or adset.locations is required")
        targeting: dict[str, Any] = {"geo_locations": {"countries": self.locations}}
        if self.age_min is not None:
            targeting["age_min"] = self.age_min
        if self.age_max is not None:
            targeting["age_max"] = self.age_max
        if self.gender:
            genders = {"male": 1, "female": 2}
            gender = self.gender.strip().lower()
            if gender not in genders:
                raise ValueError("adset.gender must be male or female")
            targeting["genders"] = [genders[gender]]
        return targeting


class CardSpec(BaseModel):
    """Um card de um anúncio em carrossel (story-059)."""

    asset: str
    headline: str
    primary_text: str = ""
    link: str = ""


class AdSpec(BaseModel):
    name: str
    format: str
    # `asset` é exigido p/ image/video; carrossel usa `cards` (>=2). Ver model_validator.
    asset: str = ""
    cards: list[CardSpec] | None = None
    primary_text: str
    headline: str
    cta: str = "SEND_MESSAGE"

    @field_validator("format")
    @classmethod
    def normalize_format(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"video", "image", "static", "carousel"}:
            raise ValueError("ad.format must be video, image/static or carousel")
        return "image" if normalized == "static" else normalized

    @model_validator(mode="after")
    def validate_format_shape(self) -> "AdSpec":
        if self.format == "carousel":
            if not self.cards or len(self.cards) < 2:
                raise ValueError("carousel ad requires at least 2 cards")
        else:
            if not self.asset:
                raise ValueError(f"{self.format} ad requires 'asset'")
        return self


class CampaignManifest(BaseModel):
    campaign: CampaignSpec
    adset: AdSetSpec
    ads: list[AdSpec] = Field(min_length=1)


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str


@dataclass(frozen=True)
class InboxPackage:
    folder: Path
    manifest_path: Path
    manifest: CampaignManifest

    def translate(self) -> dict[str, Any]:
        campaign = self.manifest.campaign
        adset = self.manifest.adset
        promoted_object = {
            "page_id": campaign.page_id,
            "whatsapp_phone_number": campaign.whatsapp_phone_number,
        }
        return {
            "campaign": {
                "name": campaign.name,
                "objective": campaign.objective,
                "status": "PAUSED",
                "special_ad_categories": [],
                "version": campaign.version,
            },
            "adset": {
                "name": adset.name,
                "daily_budget": int(round(adset.daily_budget_brl * 100)),
                "billing_event": adset.billing_event,
                "optimization_goal": adset.optimization_goal,
                "destination_type": "WHATSAPP",
                "targeting": adset.meta_targeting(),
                "promoted_object": promoted_object,
                "status": "PAUSED",
            },
            "ads": [self._translate_ad(ad, campaign) for ad in self.manifest.ads],
        }

    def _translate_ad(self, ad: "AdSpec", campaign: "CampaignSpec") -> dict[str, Any]:
        base: dict[str, Any] = {
            "name": ad.name,
            "format": ad.format,
            "primary_text": ad.primary_text,
            "headline": ad.headline,
            "cta": ad.cta,
            "page_id": campaign.page_id,
            "whatsapp_phone_number": campaign.whatsapp_phone_number,
            "status": "PAUSED",
        }
        if ad.format == "carousel":
            base["cards"] = [
                {
                    "asset_path": str((self.folder / card.asset).resolve()),
                    "headline": card.headline,
                    "primary_text": card.primary_text,
                    "link": card.link,
                }
                for card in (ad.cards or [])
            ]
        else:
            base["asset_path"] = str((self.folder / ad.asset).resolve())
        return base


def load_inbox_package(folder: str | Path) -> InboxPackage:
    base = Path(folder)
    manifest_path = base / "manifest.yaml"
    if not manifest_path.exists():
        raise ValueError("manifest.yaml not found")

    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    try:
        manifest = CampaignManifest.model_validate(raw)
    except ValidationError as exc:
        reasons = "; ".join(
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        )
        raise ValueError(reasons) from exc

    package = InboxPackage(folder=base, manifest_path=manifest_path, manifest=manifest)
    issues = validate_assets(package)
    if issues:
        raise ValueError("; ".join(f"{i.field}: {i.message}" for i in issues))
    return package


def validate_assets(package: InboxPackage) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for idx, ad in enumerate(package.manifest.ads):
        if ad.format == "carousel":
            for cidx, card in enumerate(ad.cards or []):
                issues.extend(
                    _check_asset(package.folder, card.asset, f"ads[{idx}].cards[{cidx}].asset")
                )
        else:
            issues.extend(_check_asset(package.folder, ad.asset, f"ads[{idx}].asset"))
    return issues


def _check_asset(folder: Path, asset: str, field: str) -> list[ValidationIssue]:
    asset_path = folder / asset
    if not asset_path.exists():
        return [ValidationIssue(field, f"asset not found: {asset}")]
    if asset_path.is_dir():
        return [ValidationIssue(field, f"asset is a directory: {asset}")]
    return []
