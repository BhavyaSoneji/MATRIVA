"""Checks what the bot is about to say, whatever produced it (the offline composer quotes approved passages, the
optional external model writes new text). The answer is replaced, never trimmed, when it:

* gives a dose, frequency or duration for a medicine that is not a programme supplement (iron, folic acid, calcium...);
* calls a medicine "safe" or tells the user they "can take" it, or mentions a medicine pregnant women are told to avoid
  without saying so;
* explains how to start labour, a period or an abortion at home;
* diagnoses ("you have preeclampsia"), predicts the baby's sex, or promises a cure or no risk;
* offers false reassurance.

These are rules, not model judgement, so they behave the same way every time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.safety.guardrails.engine import scan
from app.safety.guardrails.registry import load_registry
from app.safety.guardrails.text import normalize

_SENTENCES = re.compile(r"(?<=[.!?\n])\s+")
_MEDICINE_WORDS = re.compile(r"\b(tablet|tablets|capsule|capsules|syrup|injection|injections|dose|doses|dosage|medicine|medicines|medication|medications|drug|drugs|pill|pills)\b")
_AVOID_WORDS = re.compile(
    r"\b(avoid\w*|against|not|never|dont|do not|unsafe|harm\w*|risks?|contraindicated|caution\w*|warn\w*|advis\w*|discourag\w*|only if|only on|only when|"
    r"doctors?|physicians?|obstetricians?|clinicians?|pharmacists?|prescrib\w*|consult\w*|should not|shouldn t)\b"
)


@dataclass
class OutputVerdict:
    ok: bool
    rule_ids: list[str] = field(default_factory=list)
    safe_answer: str | None = None


def _sentences(text: str) -> list[str]:
    return [s for s in _SENTENCES.split(text) if s.strip()]


def _compile(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def check_output(text: str, language: str | None = None) -> OutputVerdict:
    registry = load_registry()
    failed: list[str] = []
    for rule in (r for r in registry.rules if r.kind == "output"):
        patterns = _compile(rule.data.get("patterns", []))
        allow = [normalize(a) for a in rule.data.get("allow", [])]
        check = rule.data.get("check")
        for sentence in _sentences(text):
            lowered = sentence.lower()
            norm = normalize(sentence)
            if not patterns or not any(p.search(lowered) for p in patterns):
                continue
            if check == "dose":
                named = [r for r, _ in scan(norm).values() if r.kind == "medication" and r.cls != "supplement"]
                if (named or _MEDICINE_WORDS.search(norm)) and not any(a in norm for a in allow):
                    failed.append(rule.id)
            elif check == "safe_claim":
                if any(r.kind == "medication" and r.cls != "supplement" for r, _ in scan(norm).values()):
                    failed.append(rule.id)
            elif check == "avoided_medicine":
                pass  # handled below (needs no pattern)
            else:  # induce, diagnosis, gender, guarantee, reassurance: the pattern alone is the violation
                failed.append(rule.id)
    for sentence in _sentences(text):
        norm = normalize(sentence)
        named = [r for r, _ in scan(norm).values() if r.kind == "medication" and r.cls in {"contraindicated", "avoid"}]
        if named and not _AVOID_WORDS.search(norm):
            failed.append("out-avoided-medicine-unqualified")
    failed = list(dict.fromkeys(failed))
    if not failed:
        return OutputVerdict(True)
    messages = registry.messages["output_blocked"]
    return OutputVerdict(False, failed, messages.get(language or "en") or messages["en"])
