"""
Harness: Inbox poller idempotente (story-058).
Cobre descoberta de pacotes, processamento dry-run com marcação, idempotência
(pasta marcada não reprocessa) e fail-safe (pacote inválido não derruba o lote
nem é marcado). Sem rede (dry-run + mocks).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.inbox_poller import (
    PROCESSED_MARKER,
    discover_packages,
    is_processed,
    poll_once,
)
from agent.workflows.campaign_inbox import CampaignInboxWorkflow

TMP_ROOT = Path(__file__).parent.parent / "pytest-cache-files-story058"

_VALID_MANIFEST = """
campaign:
  name: "NW - UGC - 001"
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
ads:
  - name: "UGC Hook 01"
    format: "video"
    asset: "assets/ugc.mp4"
    primary_text: "Texto"
    headline: "Mensagem"
    cta: "SEND_MESSAGE"
"""


def _fresh_root(name: str) -> Path:
    root = TMP_ROOT / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _valid_pkg(root: Path, name: str) -> Path:
    folder = root / name
    (folder / "assets").mkdir(parents=True, exist_ok=True)
    (folder / "assets" / "ugc.mp4").write_bytes(b"fake")
    (folder / "manifest.yaml").write_text(_VALID_MANIFEST, encoding="utf-8")
    return folder


def _invalid_pkg(root: Path, name: str) -> Path:
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "manifest.yaml").write_text("campaign: {}\n", encoding="utf-8")
    return folder


def _workflow() -> CampaignInboxWorkflow:
    wa = MagicMock()
    wa.send_message.return_value = {"success": True}
    wa.send_approval_request.return_value = {"success": True, "message_id": "m1"}
    return CampaignInboxWorkflow(MagicMock(), wa)


def test_discover_skips_non_packages_and_marked():
    root = _fresh_root("discover")
    _valid_pkg(root, "pkg_a")
    _valid_pkg(root, "pkg_b")
    (root / "not_a_pkg").mkdir()  # sem manifest
    marked = _valid_pkg(root, "pkg_done")
    (marked / PROCESSED_MARKER).write_text("ok", encoding="utf-8")

    found = {p.name for p in discover_packages(root)}
    assert found == {"pkg_a", "pkg_b"}, found


def test_poll_dry_run_processes_and_marks():
    root = _fresh_root("poll")
    _valid_pkg(root, "pkg_a")
    results = poll_once(root, _workflow(), dry_run=True)
    assert len(results) == 1
    assert results[0].status == "uploaded_paused"
    assert is_processed(root / "pkg_a")


def test_idempotent_second_poll_skips():
    root = _fresh_root("idem")
    _valid_pkg(root, "pkg_a")
    first = poll_once(root, _workflow(), dry_run=True)
    second = poll_once(root, _workflow(), dry_run=True)
    assert len(first) == 1
    assert len(second) == 0, "pasta já processada não deve reprocessar"


def test_fail_safe_invalid_not_marked_others_processed():
    root = _fresh_root("failsafe")
    _invalid_pkg(root, "pkg_bad")
    _valid_pkg(root, "pkg_good")
    results = poll_once(root, _workflow(), dry_run=True)
    by_status = {r.status for r in results}
    assert "rejected" in by_status and "uploaded_paused" in by_status, results
    # inválido NÃO marcado (permite retry); válido marcado
    assert not is_processed(root / "pkg_bad")
    assert is_processed(root / "pkg_good")


def run_inbox_poller_harness() -> dict:
    print("=" * 60)
    print("HARNESS: Inbox poller idempotente (story-058)")
    print("=" * 60)
    tests = (
        test_discover_skips_non_packages_and_marked,
        test_poll_dry_run_processes_and_marks,
        test_idempotent_second_poll_skips,
        test_fail_safe_invalid_not_marked_others_processed,
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
    result = run_inbox_poller_harness()
    if result["verdict"] != "PASS":
        sys.exit(1)
