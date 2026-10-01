"""Matches a question against the guard-rail registry and decides what happens.

Precedence is fixed: escalate (emergency) > block (do not answer, send to a doctor) > caution (answer, with a
notice in front). A rule that names a medicine always blocks, unless the user says their doctor prescribed it,
in which case it becomes a caution ("take it exactly as prescribed; do not change it yourself").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.safety.guardrails.context import GuardContext
from app.safety.guardrails.registry import Registry, Rule, load_registry
from app.safety.guardrails.text import edit_distance_at_most_one, is_latin, normalize, script_language

_PRESCRIBED = re.compile(
    r"\b(my doctor|doctor|dr|gynae\w*|gynec\w*|obgyn|midwife|nurse)\b.{0,25}\b(prescribed|advised|told|recommended|gave|suggested|started)\b"
    r"|\bprescribed (to|for) me\b|\bas prescribed\b|\bmy prescription\b|डॉक्टर ने|डॉक्टर साहब ने|ડૉક્ટરે|ડોક્ટરે|doctor ne (bataya|di|likhi|diya|kaha)"
)
_DOWNGRADE_WHEN_PRESCRIBED = {"doctor_only", "otc_ask"}
_RANK = {"escalate": 3, "block": 2, "caution": 1}
# When several rules agree on the action, the one that names the thing asked about comes first.
_KIND_ORDER = {"request": 0, "medication": 1, "substance": 2, "symptom": 3, "condition": 4, "watch": 5}
# A general "what are the warning signs of..." question is answered with information plus a short pointer to help.
# A first-person report ("I have", "my baby is", "since this morning") is never treated as general.
_INFORMATIONAL = re.compile(
    r"\b(warning signs?|danger signs?|signs? of|symptoms? of|what is|what are|what causes|causes of|how to prevent|how can i prevent|how do i prevent|"
    r"when should i (call|go|see|contact)|when to (call|go|see|contact)|what happens (if|when)|tell me about|explain|information (about|on)|meaning of|"
    r"kya hota hai|kya hai|lakshan|कारण|लक्षण|क्या होता है|શું છે|લક્ષણો)\b"
)
_PERSONAL = re.compile(
    r"\b(i have|i am|i m|im|i feel|i ve|ive|i had|i got|i just|my baby (is|has|was|hasn t|isn t|stopped)|my waters?|my water|since|today|yesterday|"
    r"right now|just now|this morning|last night|started|mujhe|mera|meri|main|मुझे|मेरा|मेरी|मैं|મને|મારું|મારી|હું)\b"
)


@dataclass(frozen=True)
class GuardMatch:
    rule_id: str
    kind: str
    action: str
    title: str
    message: str
    matched: str
    sources: tuple[dict[str, str], ...] = ()
    lead: str = ""  # the rule's own sentence(s), without the shared "call 112" style line
    shared: str = ""  # that shared line, in the reply language


@dataclass
class GuardResult:
    matches: list[GuardMatch] = field(default_factory=list)
    action: str | None = None
    response: str | None = None  # full answer for escalate / block
    notices: list[str] = field(default_factory=list)  # prefixed to an ordinary answer for caution

    @property
    def triggered(self) -> bool:
        return self.action is not None

    def public(self) -> list[dict[str, Any]]:
        return [
            {"id": m.rule_id, "kind": m.kind, "action": m.action, "title": m.title, "matched": m.matched,
             "sources": list(m.sources)}
            for m in self.matches
        ]


@dataclass
class _Index:
    exact: dict[str, list[Rule]]
    fuzzy: dict[tuple[str, int], list[tuple[str, Rule]]]
    indic_prefix: list[tuple[str, Rule]]
    regex: list[tuple[re.Pattern[str], Rule]]
    max_n: int


@lru_cache(maxsize=1)
def _index() -> _Index:
    registry = load_registry()
    exact: dict[str, list[Rule]] = {}
    fuzzy: dict[tuple[str, int], list[tuple[str, Rule]]] = {}
    indic: list[tuple[str, Rule]] = []
    regexes: list[tuple[re.Pattern[str], Rule]] = []
    max_n = 1
    for rule in registry.rules:
        for pattern in rule.data.get("regex", ()) if rule.kind != "output" else ():
            regexes.append((re.compile(pattern), rule))
        for term in rule.terms:
            exact.setdefault(term, []).append(rule)
            max_n = max(max_n, len(term.split()))
            if rule.fuzzy and is_latin(term) and " " not in term and len(term) >= 6:
                fuzzy.setdefault((term[0], len(term)), []).append((term, rule))
            if not is_latin(term) and " " not in term and len(term) >= 4:
                indic.append((term, rule))
    return _Index(exact, fuzzy, indic, regexes, min(max_n, 7))


def _when_ok(when: dict[str, Any], ctx: GuardContext) -> bool:
    if not when:
        return True
    if "conditions" in when or "risk_factors" in when:  # either list matching is enough
        if not (set(when.get("conditions", ())) & ctx.conditions or set(when.get("risk_factors", ())) & ctx.risk_factors):
            return False
    if "medications_any" in when and not any(
        normalize(m) in med for m in when["medications_any"] for med in ctx.medications
    ):
        return False
    if "allergies_any" in when and not any(
        normalize(a) in al for a in when["allergies_any"] for al in ctx.allergies
    ):
        return False
    if ctx.week is not None:  # an unknown week never hides a warning
        if "min_week" in when and ctx.week < when["min_week"]:
            return False
        if "max_week" in when and ctx.week > when["max_week"]:
            return False
    if ctx.age is not None:
        if "age_min" in when and ctx.age < when["age_min"]:
            return False
        if "age_max" in when and ctx.age > when["age_max"]:
            return False
    return True


def scan(text: str) -> dict[str, tuple[Rule, str]]:
    """Every rule whose trigger appears in `text` (already normalised), with the phrase that matched."""
    idx = _index()
    toks = text.split()
    hits: dict[str, tuple[Rule, str]] = {}
    for n in range(1, idx.max_n + 1):
        for i in range(len(toks) - n + 1):
            gram = " ".join(toks[i : i + n])
            variants = {gram}
            if len(gram) > 4 and gram.endswith("s"):
                variants.add(gram[:-1])
            for variant in variants:
                for rule in idx.exact.get(variant, ()):
                    hits.setdefault(rule.id, (rule, gram))
    for pattern, rule in idx.regex:
        found = pattern.search(text)
        if found and rule.id not in hits:
            hits[rule.id] = (rule, found.group(0))
    for tok in toks:
        if tok in idx.exact:
            continue
        if tok.isascii() and len(tok) >= 7:
            for delta in (-1, 0, 1):
                for term, rule in idx.fuzzy.get((tok[0], len(tok) + delta), ()):
                    if rule.id not in hits and edit_distance_at_most_one(tok, term):
                        hits[rule.id] = (rule, tok)
        elif not tok.isascii() and len(tok) >= 4:
            for term, rule in idx.indic_prefix:
                if rule.id not in hits and tok.startswith(term):
                    hits[rule.id] = (rule, tok)
    return hits


def _pick(rule: Rule, lang: str | None) -> str:
    return (rule.localized.get(lang) if lang else None) or rule.message


def _sources(registry: Registry, rule: Rule) -> tuple[dict[str, str], ...]:
    return tuple({"key": k, **registry.sources[k]} for k in rule.sources)


def _allergy_note(rule: Rule, ctx: GuardContext) -> str:
    allergy = rule.data.get("allergy")
    if allergy and any(allergy in a for a in ctx.allergies):
        return f" You have listed an allergy to {allergy}; do not take this."
    return ""


def _dedupe_shared(text: str) -> str:
    """Several matched rules can each carry the same shared line (for example 'call 112'); show it once."""
    for variants in load_registry().messages.values():
        for line in variants.values():
            if text.count(line) > 1:
                head, _, tail = text.partition(line)
                text = head + line + tail.replace(line, "")
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"  +", " ", text)).strip()


def evaluate(query: str, ctx: GuardContext | None = None, language: str | None = None) -> GuardResult:
    registry = load_registry()
    ctx = ctx or GuardContext()
    lang = script_language(query) or (language if language in {"hi", "gu"} else None)
    text = normalize(query)
    informational = bool(_INFORMATIONAL.search(text)) and not _PERSONAL.search(text)
    prescribed = bool(_PRESCRIBED.search(text)) or bool(_PRESCRIBED.search(query.lower()))
    result = GuardResult()
    for rule, matched in scan(text).values():
        if not _when_ok(rule.when, ctx):
            continue
        padded = f" {text} "
        needed = rule.data.get("with")
        if needed and not any(f" {w} " in padded for w in needed):
            continue
        if any(f" {w} " in padded for w in rule.data.get("unless", ())):
            continue
        action = rule.action
        downgraded = False
        if rule.kind == "symptom" and action in {"escalate", "block"} and informational and not rule.data.get("strict"):
            action, downgraded = "caution", True
        if action == "block" and prescribed and rule.cls in _DOWNGRADE_WHEN_PRESCRIBED:
            action = "caution"
        message = _pick(rule, lang) + _allergy_note(rule, ctx)
        if downgraded:
            lead = (rule.lead_localized.get(lang) if lang else None) or rule.lead
            urgent = registry.messages["info_urgent"]
            message = lead + " " + (urgent.get(lang or "en") or urgent["en"])
        lead = (rule.lead_localized.get(lang) if lang else None) or rule.lead
        shared_text = ""
        if rule.shared:
            variants = registry.messages[rule.shared]
            shared_text = variants.get(lang or "en") or variants["en"]
        result.matches.append(
            GuardMatch(rule.id, rule.kind, action, rule.title, message, matched, _sources(registry, rule), lead + _allergy_note(rule, ctx), shared_text)
        )
    if not result.matches:
        return result
    result.matches.sort(key=lambda m: (-_RANK[m.action], _KIND_ORDER.get(m.kind, 9), m.rule_id))
    result.action = result.matches[0].action
    footer = registry.messages
    top = result.action
    chosen = [m for m in result.matches if m.action == top][:3]
    if top in {"escalate", "block"}:
        # every rule's own sentence first, then each shared line (call 112, see a doctor today...) once
        leads = list(dict.fromkeys(m.lead or m.message for m in chosen))
        shared = list(dict.fromkeys(m.shared for m in chosen if m.shared))
        body = "\n\n".join(leads) if top == "block" else " ".join(leads)
        if shared:
            body += "\n\n" + "\n".join(shared)
        if top == "block":
            extra = [m for m in result.matches if m.action == "caution"][:2]
            if extra:
                body += "\n\n" + "\n".join(dict.fromkeys(m.message for m in extra))
            body += "\n\n" + (footer["doctor_footer"].get(lang or "en") or footer["doctor_footer"]["en"])
        result.response = _dedupe_shared(body)
    result.notices = list(dict.fromkeys(m.message for m in result.matches if m.action == "caution"))[:3]
    return result


def evaluate_profile_watch(ctx: GuardContext, language: str | None = None) -> list[str]:
    """Notices the person should see once, from what they told us: risky medicines on their list, and
    profile-only (term-less) rules such as 'rh negative'."""
    registry = load_registry()
    lang = language if language in {"hi", "gu"} else None
    notices: list[str] = []
    for med in ctx.medications:
        for rule, _matched in scan(med).values():
            if rule.kind == "medication" and rule.cls in {"contraindicated", "avoid"}:
                notices.append(
                    (f"Your profile lists {med}. " if lang is None else "")
                    + _pick(rule, lang)
                )
    for rule in registry.rules:
        if rule.kind == "watch" and rule.when and _when_ok(rule.when, ctx):
            notices.append(_pick(rule, lang))
    return list(dict.fromkeys(notices))[:3]
