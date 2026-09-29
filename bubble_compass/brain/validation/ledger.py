"""JSONL trial ledger so trial counts exist from day one."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TrialLedger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    def count(self) -> int:
        if not self.path.exists():
            return 0
        return sum(1 for _ in self.path.open("r", encoding="utf-8"))
