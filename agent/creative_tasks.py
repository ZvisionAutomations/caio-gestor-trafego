"""Append-only registry of trackable creative tasks routed to Miguel.

Per Story 039 decision #12, when a creative fatigues (or a campaign is recused,
a hook is weak, CTR is bad, or an opportunity appears), Caio does NOT create the
creative himself and does NOT ask Caue for approval. Instead he records a
trackable task for Miguel to produce a new variation. Nothing here overwrites
history: every call appends a new record.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_LOG_DIR = Path(__file__).parent.parent / "logs"
_TASKS_FILE = "creative-tasks.jsonl"

# Trackable task types (Story 039 decision #13: solicitacao, recusa, fadiga,
# oportunidade e decisao devem ser rastreaveis).
TASK_FATIGUE = "new_variation_fatigue"
TASK_RECUSED_CAMPAIGN = "recused_campaign"
TASK_WEAK_HOOK = "weak_hook"
TASK_BAD_CTR = "bad_ctr"
TASK_OPPORTUNITY = "opportunity"

_VALID_TASK_TYPES = {
    TASK_FATIGUE,
    TASK_RECUSED_CAMPAIGN,
    TASK_WEAK_HOOK,
    TASK_BAD_CTR,
    TASK_OPPORTUNITY,
}


@dataclass(frozen=True)
class CreativeTask:
    task_type: str
    target_id: str
    target_name: str
    reason: str
    data: str = ""
    assignee: str = "Miguel"
    status: str = "open"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def record_creative_task(
    *,
    task_type: str,
    target_id: str,
    target_name: str,
    reason: str,
    data: str = "",
    assignee: str = "Miguel",
    log_dir: str | Path | None = None,
) -> CreativeTask:
    """Append a trackable creative task. Never overwrites existing history."""
    if task_type not in _VALID_TASK_TYPES:
        raise ValueError(f"unknown creative task_type: {task_type}")

    task = CreativeTask(
        task_type=task_type,
        target_id=target_id,
        target_name=target_name,
        reason=reason,
        data=data,
        assignee=assignee,
    )

    target_dir = Path(log_dir) if log_dir else _DEFAULT_LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    with open(target_dir / _TASKS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(task.to_record(), ensure_ascii=True, sort_keys=True) + "\n")
    return task
