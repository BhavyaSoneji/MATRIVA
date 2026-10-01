"""The care rules file (app/data/care_rules.yaml): one place for every threshold, schedule and screening question."""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

import yaml

_DATA = Path(__file__).resolve().parents[2] / "data"


@functools.lru_cache(maxsize=1)
def rules() -> dict[str, Any]:
    return yaml.safe_load((_DATA / "care_rules.yaml").read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def foods() -> dict[str, dict[str, Any]]:
    data = json.loads((_DATA / "foods_nutrients.json").read_text(encoding="utf-8"))
    return {f["id"]: f for f in data["foods"]}
