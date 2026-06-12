"""Run Caio harnesses in a cross-platform way."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HARNESSES = [
    ("test_analyze", ROOT / "harnesses" / "test_analyze.py"),
    ("test_report", ROOT / "harnesses" / "test_report.py"),
    ("test_approve", ROOT / "harnesses" / "test_approve.py"),
    ("test_traffic_skills", ROOT / "harnesses" / "test_traffic_skills.py"),
    ("test_calibration", ROOT / "harnesses" / "test_calibration.py"),
    ("test_campaign_inbox", ROOT / "harnesses" / "test_campaign_inbox.py"),
]


def main() -> int:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    for name, path in HARNESSES:
        print("", flush=True)
        print(f"=== {name} ===", flush=True)
        result = subprocess.run([sys.executable, str(path)], cwd=ROOT, check=False, env=env)
        if result.returncode != 0:
            print("")
            print(f"FAIL: {name} exited with {result.returncode}")
            return result.returncode

    print("", flush=True)
    print("Todos os harnesses concluidos.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
