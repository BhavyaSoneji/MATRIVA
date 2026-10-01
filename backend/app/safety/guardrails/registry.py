"""Loads and validates the guard-rail rule files in ``app/data/guardrails``.

Every rule has an id, a kind, an action, trigger terms (any language) or a profile condition, and sources that
exist in ``sources.yaml``. A rule file that breaks that contract fails at load time (and in the tests), not in
front of a patient.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.safety.guardrails.text import normalize

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "guardrails"
ACTIONS = ("escalate", "block", "caution")
KINDS = ("medication", "substance", "request", "symptom", "condition", "watch", "output")
# Order matters: when two files describe the same rule id, the first one wins and the later one only adds terms.
RULE_FILES = {
    "medicines_prescription.yaml": "medication",
    "medicines_specialist.yaml": "medication",
    "medicines_common.yaml": "medication",
    "vaccines.yaml": "medication",
    "medications.yaml": "medication",
    "herbs.yaml": "substance",
    "foods.yaml": "substance",
    "exposures.yaml": "substance",
    "substances.yaml": "substance",
    "requests.yaml": "request",
    "symptoms.yaml": "symptom",
    "condition_rules.yaml": "condition",
    "watch.yaml": "watch",
    "output.yaml": "output",
}


class RegistryError(ValueError):
    pass


@dataclass(frozen=True)
class Rule:
    id: str
    kind: str
    action: str
    title: str
    terms: tuple[str, ...] = ()
    cls: str | None = None
    message: str = ""
    why: str = ""
    sources: tuple[str, ...] = ()
    when: dict[str, Any] = field(default_factory=dict)
    localized: dict[str, str] = field(default_factory=dict)
    fuzzy: bool = False
    shared: str | None = None  # key of the shared line appended to this rule's message, e.g. "emergency"
    lead: str = ""  # the rule's own sentence, without any shared line such as "call 112"
    lead_localized: dict[str, str] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)  # kind-specific extras (output rules)


@dataclass(frozen=True)
class Registry:
    rules: tuple[Rule, ...]
    sources: dict[str, dict[str, str]]
    classes: dict[str, dict[str, Any]]
    conditions: dict[str, dict[str, Any]]
    risk_factors: dict[str, dict[str, Any]]
    messages: dict[str, dict[str, str]]
    by_id: dict[str, Rule]


def _read(name: str) -> dict[str, Any]:
    with (DATA_DIR / name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _expand_groups(data: dict[str, Any]) -> list[dict[str, Any]]:
    """A file may list `groups`: shared class / reason / sources and an `items` list where each item becomes its
    own rule. An item is "name" or "name|brand|brand" (brands and local names after the first bar), or a mapping
    with its own `why`. Every item gets its own id, so each one can be reviewed, disabled or sourced separately."""
    rules: list[dict[str, Any]] = list(data.get("rules", []))
    for group in data.get("groups", []):
        base = {k: v for k, v in group.items() if k != "items"}
        for item in group["items"]:
            if isinstance(item, str):
                name, *aka = [part.strip() for part in item.split("|")]
                entry = {**base, "name": name, "aka": aka}
            else:
                entry = {**base, **item}
            rules.append(entry)
    return rules


def _render(template: str, name: str, why: str) -> str:
    if template.startswith("{name}"):
        name = name[:1].upper() + name[1:]
    return template.replace("{name}", name).replace("{why}", why)


def _build(raw: dict[str, Any], kind: str, classes: dict[str, dict[str, Any]], messages: dict[str, dict[str, str]]) -> Rule:
    cls = raw.get("cls")
    if kind == "medication" and not cls:
        raise RegistryError(f"{raw.get('id', raw.get('name'))}: a medication rule needs a class")
    if cls and cls not in classes:
        raise RegistryError(f"{raw.get('id', raw.get('name'))}: unknown class {cls!r}")
    template = classes[cls] if cls else {}
    name = raw.get("name") or raw.get("title") or raw["id"]
    if "id" not in raw:
        raw = {**raw, "id": ("med-" if kind == "medication" else "sub-") + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")}
    why = raw.get("why", template.get("default_why", ""))
    raw_terms = [*raw.get("terms", []), *([name, *raw.get("aka", [])] if raw.get("name") else [])]
    terms = tuple(dict.fromkeys(normalize(t) for t in raw_terms if normalize(t)))
    message = raw.get("message") or _render(template.get("message", ""), name, why)
    localized = {lang: _render(text, name, why) for lang, text in (template.get("localized") or {}).items()}
    localized.update(raw.get("localized") or {})
    lead = message
    lead_localized = dict(localized)
    ref = raw.get("use")
    if ref:  # shared message, e.g. "emergency" or "mental-health"
        if ref not in messages:
            raise RegistryError(f"{raw['id']}: unknown shared message {ref!r}")
        message = (message + " " if message else "") + messages[ref]["en"]
        for lang in ("hi", "gu"):
            if lang in messages[ref]:
                localized[lang] = ((localized.get(lang, "") + " ") if localized.get(lang) else "") + messages[ref][lang]
    extras = {k: v for k, v in raw.items() if k in {"check", "patterns", "allow", "with", "unless", "strict", "regex"}}
    for key in ("with", "unless"):
        if key in extras:
            extras[key] = [normalize(x) for x in extras[key]]
    if raw.get("allergy"):
        extras["allergy"] = raw["allergy"]
    return Rule(
        id=raw["id"], kind=kind, action=raw.get("action") or template.get("action", ""), cls=cls,
        title=raw.get("title") or name.title(), terms=terms, message=message, why=why,
        sources=tuple(raw.get("src", [])), when=raw.get("when", {}), localized=localized,
        fuzzy=bool(raw.get("fuzzy", kind in {"medication", "substance"})), data=extras,
        lead=lead, lead_localized=lead_localized, shared=ref,
    )


def _specific_terms_win(rules: list[Rule]) -> list[Rule]:
    """When the same phrase triggers several rules of one kind (a broad group rule and a rule for one drug), keep it
    only on the narrowest rule, so one question never produces two overlapping notices."""
    owners: dict[tuple[str, str], list[int]] = {}
    for i, rule in enumerate(rules):
        if rule.kind not in {"medication", "substance"} or rule.when:
            continue
        for term in rule.terms:
            owners.setdefault((rule.kind, term), []).append(i)
    drop: dict[int, set[str]] = {}
    for (_kind, term), idxs in owners.items():
        if len(idxs) > 1:
            winner = min(idxs, key=lambda i: (len(rules[i].terms), i))
            for i in idxs:
                if i != winner:
                    drop.setdefault(i, set()).add(term)
    result: list[Rule] = []
    for i, rule in enumerate(rules):
        if i in drop:
            rule = replace(rule, terms=tuple(t for t in rule.terms if t not in drop[i]))
        if rule.terms or rule.data.get("regex") or rule.kind in {"watch", "output", "condition"}:
            result.append(rule)
    return result


@lru_cache(maxsize=1)
def load_registry() -> Registry:
    sources = _read("sources.yaml")["sources"]
    classes = _read("classes.yaml")["classes"]
    cond = _read("conditions.yaml")
    messages = _read("messages.yaml")["messages"]
    by_id: dict[str, Rule] = {}
    rules: list[Rule] = []
    for filename, kind in RULE_FILES.items():
        if not (DATA_DIR / filename).exists():
            continue
        for raw in _expand_groups(_read(filename)):
            try:
                built = _build(raw, kind, classes, messages)
                earlier = by_id.get(built.id)
                if earlier is not None:  # same medicine described twice: keep the first, add the other's spellings
                    merged = replace(earlier, terms=tuple(dict.fromkeys([*earlier.terms, *built.terms])))
                    rules[rules.index(earlier)] = merged
                    by_id[built.id] = merged
                    continue
                by_id[built.id] = built
                rules.append(built)
            except KeyError as exc:
                raise RegistryError(f"{filename}: rule {raw.get('id', raw.get('name', raw))!r} is missing {exc}") from exc
    rules = _specific_terms_win(rules)
    registry = Registry(
        rules=tuple(rules), sources=sources, classes=classes, conditions=cond["conditions"],
        risk_factors=cond["risk_factors"], messages=messages, by_id={r.id: r for r in rules},
    )
    problems = validate(registry)
    if problems:
        raise RegistryError("guard-rail registry is invalid:\n" + "\n".join(problems[:20]))
    return registry


def validate(registry: Registry) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for rule in registry.rules:
        if rule.id in seen:
            problems.append(f"duplicate id {rule.id}")
        seen.add(rule.id)
        if rule.kind not in KINDS:
            problems.append(f"{rule.id}: bad kind {rule.kind}")
        if rule.action not in ACTIONS and rule.kind != "output":
            problems.append(f"{rule.id}: bad action {rule.action}")
        if rule.kind not in {"watch", "output", "condition"} and not rule.terms and not rule.data.get("regex"):
            problems.append(f"{rule.id}: no trigger terms")
        if rule.kind != "output" and not rule.message:
            problems.append(f"{rule.id}: no message")
        if rule.kind != "output" and not rule.sources:
            problems.append(f"{rule.id}: no sources")
        for key in rule.sources:
            if key not in registry.sources:
                problems.append(f"{rule.id}: unknown source {key}")
        for code in rule.when.get("conditions", []):
            if code not in registry.conditions:
                problems.append(f"{rule.id}: unknown condition {code}")
        for code in rule.when.get("risk_factors", []):
            if code not in registry.risk_factors:
                problems.append(f"{rule.id}: unknown risk factor {code}")
    return problems


def registry_stats() -> dict[str, Any]:
    registry = load_registry()
    by_kind: dict[str, int] = {}
    for rule in registry.rules:
        by_kind[rule.kind] = by_kind.get(rule.kind, 0) + 1
    return {
        "rules": len(registry.rules),
        "by_kind": by_kind,
        "trigger_terms": sum(len(r.terms) for r in registry.rules),
        "sources": len(registry.sources),
    }
