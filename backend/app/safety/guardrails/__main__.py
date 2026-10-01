"""`python -m app.safety.guardrails` prints what the guard rails contain, so the numbers in the docs are never guessed."""

from __future__ import annotations

from collections import Counter

from app.safety.guardrails.registry import load_registry, registry_stats


def main() -> None:
    registry = load_registry()
    stats = registry_stats()
    print(f"rules: {stats['rules']}   trigger phrases: {stats['trigger_terms']}   sources: {stats['sources']}")
    print("\nby kind")
    for kind, n in sorted(stats["by_kind"].items(), key=lambda kv: -kv[1]):
        print(f"  {kind:<12}{n:>5}")
    print("\nmedicines and substances by class")
    classes = Counter(rule.cls for rule in registry.rules if rule.cls)
    for cls, n in classes.most_common():
        print(f"  {cls:<20}{n:>5}")
    print("\nby action")
    for action, n in Counter(rule.action for rule in registry.rules if rule.kind != "output").most_common():
        print(f"  {action:<12}{n:>5}")
    used = Counter(key for rule in registry.rules for key in rule.sources)
    print("\nmost cited sources")
    for key, n in used.most_common(8):
        print(f"  {n:>5}  {registry.sources[key]['name']}")


if __name__ == "__main__":
    main()
