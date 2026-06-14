"""
Harness: Carrossel multi-card no contrato de handoff (story-059).
Cobre tradução multi-card, validação (>=2 cards, asset de card faltante) e
retrocompatibilidade single-asset (image/video). Sem rede.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.campaign_inbox import load_inbox_package

TMP_ROOT = Path(__file__).parent.parent / "pytest-cache-files-story059"

_CAMPAIGN = """
campaign:
  name: "NW - Carrossel - 001"
  product: "new_woman"
  objective: "messages"
  status_on_upload: "paused"
  page_id: "123"
  whatsapp_phone_number: "5511999990000"
  version: "v1"
adset:
  name: "Mulheres 45-60 BR"
  daily_budget_brl: 50
  age_min: 45
  age_max: 60
  gender: "female"
  locations: ["BR"]
"""


def _fresh(name: str) -> Path:
    target = TMP_ROOT / name
    if target.exists():
        shutil.rmtree(target)
    (target / "assets").mkdir(parents=True, exist_ok=True)
    return target


def _write(base: Path, ads_yaml: str, assets: list[str]) -> None:
    for a in assets:
        (base / "assets" / a).write_bytes(b"fake")
    (base / "manifest.yaml").write_text(_CAMPAIGN + ads_yaml, encoding="utf-8")


def test_carousel_translates_to_multi_card():
    base = _fresh("carousel_ok")
    _write(
        base,
        """
ads:
  - name: "Carrossel 01"
    format: "carousel"
    primary_text: "Texto principal"
    headline: "Headline ad"
    cards:
      - asset: "assets/c1.jpg"
        headline: "Card 1"
        primary_text: "desc 1"
      - asset: "assets/c2.jpg"
        headline: "Card 2"
        link: "https://wa.me/5511999990000"
""",
        ["c1.jpg", "c2.jpg"],
    )
    translated = load_inbox_package(base).translate()
    ad = translated["ads"][0]
    assert ad["format"] == "carousel", ad
    assert "asset_path" not in ad, "carrossel não deve ter asset_path único"
    assert len(ad["cards"]) == 2
    assert ad["cards"][0]["headline"] == "Card 1"
    assert ad["cards"][1]["link"] == "https://wa.me/5511999990000"
    assert ad["cards"][0]["asset_path"].endswith("c1.jpg")


def test_carousel_with_one_card_is_rejected():
    base = _fresh("carousel_one")
    _write(
        base,
        """
ads:
  - name: "Carrossel ruim"
    format: "carousel"
    primary_text: "t"
    headline: "h"
    cards:
      - asset: "assets/c1.jpg"
        headline: "Card 1"
""",
        ["c1.jpg"],
    )
    try:
        load_inbox_package(base)
    except ValueError as exc:
        assert "at least 2 cards" in str(exc), exc
        return
    raise AssertionError("carrossel com 1 card deveria ser rejeitado")


def test_carousel_missing_card_asset_is_rejected():
    base = _fresh("carousel_missing")
    _write(
        base,
        """
ads:
  - name: "Carrossel"
    format: "carousel"
    primary_text: "t"
    headline: "h"
    cards:
      - asset: "assets/c1.jpg"
        headline: "Card 1"
      - asset: "assets/missing.jpg"
        headline: "Card 2"
""",
        ["c1.jpg"],  # missing.jpg não criado
    )
    try:
        load_inbox_package(base)
    except ValueError as exc:
        assert "asset not found" in str(exc) and "missing.jpg" in str(exc), exc
        return
    raise AssertionError("carrossel com asset de card faltante deveria ser rejeitado")


def test_single_asset_image_video_backcompat():
    base = _fresh("single_video")
    _write(
        base,
        """
ads:
  - name: "UGC 01"
    format: "video"
    asset: "assets/ugc.mp4"
    primary_text: "t"
    headline: "h"
""",
        ["ugc.mp4"],
    )
    ad = load_inbox_package(base).translate()["ads"][0]
    assert ad["format"] == "video"
    assert ad["asset_path"].endswith("ugc.mp4")
    assert "cards" not in ad


def run_carousel_harness() -> dict:
    print("=" * 60)
    print("HARNESS: Carrossel multi-card (story-059)")
    print("=" * 60)
    tests = (
        test_carousel_translates_to_multi_card,
        test_carousel_with_one_card_is_rejected,
        test_carousel_missing_card_asset_is_rejected,
        test_single_asset_image_video_backcompat,
    )
    failures: list[str] = []
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {t.__name__}: {exc}")
            failures.append(t.__name__)
    print(f"\nVeredicto: {'PASS' if not failures else 'FAIL'}")
    return {"verdict": "PASS" if not failures else "FAIL", "failures": failures}


if __name__ == "__main__":
    result = run_carousel_harness()
    if result["verdict"] != "PASS":
        sys.exit(1)
