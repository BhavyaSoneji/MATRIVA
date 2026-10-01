"""Rule-based guard rails for the chat: medicines, substances, risky requests, symptoms, and the user's own
conditions. Independent of any language model. Rules are data (``app/data/guardrails/*.yaml``), each with
sources and a review status."""

from app.safety.guardrails.context import GuardContext, build_guard_context
from app.safety.guardrails.engine import GuardMatch, GuardResult, evaluate, evaluate_profile_watch
from app.safety.guardrails.output import OutputVerdict, check_output
from app.safety.guardrails.registry import Rule, load_registry, registry_stats

__all__ = [
    "GuardContext", "GuardMatch", "GuardResult", "OutputVerdict", "Rule",
    "build_guard_context", "check_output", "evaluate", "evaluate_profile_watch", "load_registry", "registry_stats",
]
