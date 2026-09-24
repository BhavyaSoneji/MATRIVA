from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, SafetyEvent, SafetyRule


def record_audit(
    db: Session,
    *,
    actor_user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    event = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )
    db.add(event)
    return event


def record_safety_event(
    db: Session,
    *,
    user_id: str | None,
    query_hash: str,
    risk_level: str,
    matched_rule_ids: list[str],
    action: str,
) -> SafetyEvent:
    event = SafetyEvent(
        user_id=user_id,
        query_hash=query_hash,
        risk_level=risk_level,
        matched_rule_ids=matched_rule_ids,
        action=action,
    )
    db.add(event)
    return event


def active_safety_rules(db: Session) -> list[SafetyRule]:
    return list(db.query(SafetyRule).filter(SafetyRule.active.is_(True)).all())
