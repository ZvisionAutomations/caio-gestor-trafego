"""
Harness: Story 019 - Caio traffic skills adaptation.

Valida presenca das novas tools e knowledge sem conectar na Meta API real.
"""
from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.tools import meta_ads as meta_ads_module
from agent.tools.meta_ads import MetaAdsTool

_ROOT = Path(__file__).parent.parent
_CAIO = _ROOT / "agent" / "caio.py"
_KNOWLEDGE = _ROOT / "agent" / "knowledge" / "marketing-skills.md"

EXPECTED_META_METHODS = {
    "get_creative_preview",
    "get_insights_breakdowns",
    "search_targeting",
    "validate_targeting",
    "describe_targeting",
    "estimate_targeting_reach",
    "estimate_targeting_delivery",
    "get_pixels",
    "diagnose_pixels",
}

EXPECTED_CAIO_TOOLS = EXPECTED_META_METHODS
FORBIDDEN_AUTONOMOUS_TOOLS = {"resume_ad", "resume_ad_set"}


def _meta_tool_refs_in_build_caio() -> set[str]:
    tree = ast.parse(_CAIO.read_text(encoding="utf-8"))
    refs: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "meta_tool"
        ):
            refs.add(node.attr)
    return refs


def test_meta_ads_methods_present() -> None:
    methods = {
        name
        for name, member in inspect.getmembers(MetaAdsTool, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    missing = EXPECTED_META_METHODS - methods
    assert not missing, f"MetaAdsTool sem metodos esperados: {sorted(missing)}"


def test_build_caio_exposes_story_019_tools() -> None:
    refs = _meta_tool_refs_in_build_caio()
    missing = EXPECTED_CAIO_TOOLS - refs
    assert not missing, f"build_caio nao expoe tools da Story 019: {sorted(missing)}"
    forbidden = FORBIDDEN_AUTONOMOUS_TOOLS & refs
    assert not forbidden, f"build_caio expoe ativacao/reativacao sem aprovacao: {sorted(forbidden)}"


def test_marketing_skills_knowledge_loaded_by_rglob() -> None:
    assert _KNOWLEDGE.exists(), "marketing-skills.md precisa estar em agent/knowledge/"
    content = _KNOWLEDGE.read_text(encoding="utf-8")
    assert "Ratos de IA" in content
    assert "InsightfulPipe" in content
    assert "preview" in content
    assert "pixels/datasets" in content


def _tool_with_account(account: object) -> MetaAdsTool:
    tool = object.__new__(MetaAdsTool)
    tool.account_id = "act_test"
    tool._account = account
    return tool


def test_get_pixels_uses_sdk_ads_pixels_method() -> None:
    class FakeAccount:
        def __init__(self) -> None:
            self.called = False

        def get_ads_pixels(self, fields: list[str]) -> list[dict[str, str]]:
            self.called = True
            assert "last_fired_time" in fields
            return [{"id": "pixel_1", "name": "Raiz Vital Pixel", "last_fired_time": "2026-05-28"}]

    account = FakeAccount()
    result = _tool_with_account(account).get_pixels()

    assert account.called
    assert result[0]["id"] == "pixel_1"


def test_get_pixels_falls_back_to_legacy_ad_pixels_method() -> None:
    class FakeAccount:
        def __init__(self) -> None:
            self.called = False

        def get_ad_pixels(self, fields: list[str]) -> list[dict[str, str]]:
            self.called = True
            assert "last_fired_time" in fields
            return [{"id": "legacy_pixel", "name": "Legacy Pixel"}]

    account = FakeAccount()
    result = _tool_with_account(account).get_pixels()

    assert account.called
    assert result[0]["id"] == "legacy_pixel"


def test_get_pixels_returns_empty_when_sdk_has_no_pixel_method() -> None:
    result = _tool_with_account(object()).get_pixels()

    assert result == []


def test_get_insights_breakdowns_passes_breakdowns_params() -> None:
    class FakeAccount:
        def get_insights(self, fields: list[str], params: dict) -> list[dict[str, str]]:
            assert "spend" in fields
            assert params["level"] == "ad"
            assert params["date_preset"] == "last_7d"
            assert params["breakdowns"] == ["age", "gender"]
            return [{"age": "45-54", "gender": "female", "spend": "100.00"}]

    result = _tool_with_account(FakeAccount()).get_insights_breakdowns(
        level="ad",
        days=7,
        breakdowns=["age", "gender"],
    )

    assert result[0]["age"] == "45-54"


def test_get_creative_preview_calls_sdk_previews() -> None:
    original = meta_ads_module.AdCreative

    class FakeCreative:
        def __init__(self, creative_id: str) -> None:
            assert creative_id == "creative_1"

        def get_previews(self, params: dict) -> list[dict[str, str]]:
            assert params["ad_format"] == "MOBILE_FEED_STANDARD"
            return [{"body": "<iframe>preview</iframe>"}]

    try:
        meta_ads_module.AdCreative = FakeCreative
        result = _tool_with_account(object()).get_creative_preview(
            "creative_1",
            "MOBILE_FEED_STANDARD",
        )
    finally:
        meta_ads_module.AdCreative = original

    assert result == [{"body": "<iframe>preview</iframe>", "_format": "MOBILE_FEED_STANDARD"}]


def test_search_targeting_calls_targeting_search() -> None:
    original = meta_ads_module.TargetingSearch

    class FakeTargetingSearch:
        @staticmethod
        def search(params: dict) -> list[dict[str, str | int]]:
            assert params == {
                "type": "adinterest",
                "limit": 10,
                "locale": "pt_BR",
                "q": "menopausa",
            }
            return [{"id": "6001", "name": "Menopausa"}]

    try:
        meta_ads_module.TargetingSearch = FakeTargetingSearch
        result = _tool_with_account(object()).search_targeting("menopausa", limit=10)
    finally:
        meta_ads_module.TargetingSearch = original

    assert result[0]["name"] == "Menopausa"


if __name__ == "__main__":
    print("=" * 60)
    print("CAIO - HARNESS: TRAFFIC SKILLS ADAPTATION")
    print("=" * 60)

    tests = [
        test_meta_ads_methods_present,
        test_build_caio_exposes_story_019_tools,
        test_marketing_skills_knowledge_loaded_by_rglob,
        test_get_pixels_uses_sdk_ads_pixels_method,
        test_get_pixels_falls_back_to_legacy_ad_pixels_method,
        test_get_pixels_returns_empty_when_sdk_has_no_pixel_method,
        test_get_insights_breakdowns_passes_breakdowns_params,
        test_get_creative_preview_calls_sdk_previews,
        test_search_targeting_calls_targeting_search,
    ]

    failures: list[str] = []
    for test in tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
        except AssertionError as exc:
            failures.append(f"{test.__name__}: {exc}")
            print(f"FAIL: {test.__name__}: {exc}")

    if failures:
        print("\nFalhas:")
        for failure in failures:
            print(f"- {failure}")
        sys.exit(1)

    print("\nVeredicto: PASS")
