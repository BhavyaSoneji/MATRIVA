"""Idempotent synthetic data for local demos and tests.

All records created here are explicitly marked as DEMO DATA.  They are not a substitute
for a current clinical review or a complete government-guideline corpus.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

from sqlalchemy import select

def _find_backend_dir() -> Path:
    configured = os.environ.get("MATRIVA_BACKEND_DIR")
    candidates = []
    if configured:
        candidates.append(Path(configured))
    source = Path(__file__).resolve()
    parents = list(source.parents)
    candidates.extend([
        parents[2] / "backend" if len(parents) > 2 else source.parent / "backend",
        parents[-1],
        Path("/app"),
    ])
    for candidate in candidates:
        if (candidate / "app").is_dir():
            return candidate
    return source.parents[2] / "backend"


BACKEND_DIR = _find_backend_dir()
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import SessionLocal, init_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import (  # noqa: E402
    AyurvedicSource,
    ConsentRecord,
    DietaryProfile,
    EvidenceLevel,
    EvidenceMetadata,
    ExerciseGuidance,
    FoodItem,
    Guideline,
    HealthProfile,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
    LifestyleProfile,
    PregnancyProfile,
    ReviewStatus,
    SafetyStatus,
    SourceType,
    User,
    UserRole,
)
from app.rag.embeddings import embed_text  # noqa: E402
from app.services.stage import calculate_stage  # noqa: E402

DEMO_PASSWORD = "DemoPass123!"


def _seed_embedding(content: str) -> list[float] | None:
    """Best-effort embedding for demo chunks so the seeded corpus actually
    exercises real vector retrieval (see retrieve_chunks_scored) when an
    embedding key is configured, instead of always falling back to keyword
    search just because demo data was never (re)indexed through the admin
    upload path."""
    api_key = os.environ.get("EMBEDDING_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        return embed_text(content, api_key=api_key)
    except Exception:  # noqa: BLE001
        return None


def _user(db, email: str, role: UserRole, name: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user:
        return user
    user = User(email=email, password_hash=hash_password(DEMO_PASSWORD), full_name=name, role=role.value)
    db.add(user)
    db.flush()
    return user


def _profile(db, user: User, week: int, region: str, diet: str) -> None:
    consent = db.execute(select(ConsentRecord).where(ConsentRecord.user_id == user.id)).scalar_one_or_none()
    if consent is None:
        db.add(ConsentRecord(user_id=user.id, consent_type="profile_and_health", granted=True, version="DEMO-2026", granted_at=datetime.now(timezone.utc)))
    if db.execute(select(HealthProfile).where(HealthProfile.user_id == user.id)).scalar_one_or_none() is None:
        db.add(HealthProfile(user_id=user.id, known_conditions=[], doctor_restrictions=[], dietary_restrictions=[], activity_restrictions=[], allergies=[]))
    if db.execute(select(LifestyleProfile).where(LifestyleProfile.user_id == user.id)).scalar_one_or_none() is None:
        db.add(LifestyleProfile(user_id=user.id, activity_level="moderate", sleep_hours=7, stress_level="moderate", preferences=["walking"]))
    if db.execute(select(DietaryProfile).where(DietaryProfile.user_id == user.id)).scalar_one_or_none() is None:
        db.add(DietaryProfile(user_id=user.id, diet_type=diet, region=region, cuisine="regional", food_preferences=[], allergies=[]))
    if db.execute(select(PregnancyProfile).where(PregnancyProfile.user_id == user.id)).scalar_one_or_none() is None:
        db.add(PregnancyProfile(user_id=user.id, current_week=week, due_date=None, first_pregnancy=True, stage=calculate_stage(week).stage))


def _source(db, key: str, **values: str) -> KnowledgeSource:
    source = db.execute(select(KnowledgeSource).where(KnowledgeSource.name == key)).scalar_one_or_none()
    if source:
        return source
    source = KnowledgeSource(id=key, **values)
    db.add(source)
    db.flush()
    return source


def seed_demo_data() -> None:
    init_db()
    db = SessionLocal()
    try:
        admin = _user(db, "admin@demo.example.com", UserRole.ADMIN, "Demo Administrator")
        _user(db, "evaluator@demo.example.com", UserRole.EVALUATOR, "Demo Evaluator")
        users = [
            _user(db, "demo.a@example.com", UserRole.USER, "Demo User A"),
            _user(db, "demo.b@example.com", UserRole.USER, "Demo User B"),
            _user(db, "demo.c@example.com", UserRole.USER, "Demo User C"),
        ]
        for index, user in enumerate(users, start=1):
            _profile(db, user, 14 + index * 4, ["Gujarat", "Maharashtra", "Karnataka"][index - 1], "vegetarian")

        anc = _source(
            db,
            "fogsi-anc-contact-schedule",
            name="fogsi-anc-contact-schedule",
            title="DEMO DATA — ANC contact-week schedule excerpt",
            source_type=SourceType.PROFESSIONAL_SOCIETY.value,
            authority="FOGSI (demo excerpt; verify current source before production)",
            jurisdiction="India",
            topic="antenatal care",
            version="demo-2026",
            review_status=ReviewStatus.APPROVED.value,
            evidence_level=EvidenceLevel.SUPPORTED.value,
            description="Synthetic demo excerpt for the R0 scenario. Not a complete clinical guideline.",
            extra_metadata={"demo_data": True, "page_or_section": "demo ANC schedule excerpt", "review_note": "Replace with current, clinically reviewed guideline before deployment."},
        )
        anc_doc = db.execute(select(KnowledgeDocument).where(KnowledgeDocument.source_id == anc.id, KnowledgeDocument.title == "DEMO DATA — ANC schedule")).scalar_one_or_none()
        if anc_doc is None:
            anc_doc = KnowledgeDocument(source_id=anc.id, title="DEMO DATA — ANC schedule", domain="antenatal_care", language="en", region="India", review_status=ReviewStatus.APPROVED.value, index_status="indexed", content_hash="demo-anc", file_name="demo-anc.txt", mime_type="text/plain", raw_content=b"demo", active=True, created_by=admin.id, approved_by=admin.id)
            db.add(anc_doc)
            db.flush()
            anc_content = "For the demo scenario, the configured antenatal contact weeks are 12, 20, 26, 30, 34, 36, 38, 40, and 41. The next visit is the first configured week that is not earlier than the current week. Confirm timing and instructions with the maternity-care professional."
            db.add(KnowledgeChunk(document_id=anc_doc.id, source_id=anc.id, chunk_index=0, content=anc_content, embedding=_seed_embedding(anc_content)))
        if anc.evidence_metadata is None:
            db.add(EvidenceMetadata(source_id=anc.id, evidence_level=EvidenceLevel.SUPPORTED.value, evidence_label="DEMO — clinical review required", review_status=ReviewStatus.APPROVED.value, reviewer=admin.email, notes="Synthetic demo only."))
        if anc.guideline is None:
            db.add(Guideline(source_id=anc.id, authority="FOGSI (demo)", jurisdiction="India", status="active", scope_notes="Demo-only; not a complete government guideline registry."))

        food_source = _source(
            db,
            "ifct-demo-foods",
            name="ifct-demo-foods",
            title="DEMO DATA — food and nutrition source card",
            source_type=SourceType.GOVERNMENT.value,
            authority="ICMR/NIN reference category (demo placeholder)",
            jurisdiction="India",
            topic="nutrition",
            version="demo-2026",
            review_status=ReviewStatus.APPROVED.value,
            evidence_level=EvidenceLevel.SUPPORTED.value,
            description="Synthetic placeholder for a reviewed food-composition source.",
            extra_metadata={"demo_data": True, "review_note": "Replace with the current reviewed IFCT data and citation."},
        )
        food_doc = db.execute(select(KnowledgeDocument).where(KnowledgeDocument.source_id == food_source.id)).scalar_one_or_none()
        if food_doc is None:
            food_doc = KnowledgeDocument(source_id=food_source.id, title="DEMO DATA — balanced meal examples", domain="nutrition", language="en", region="India", review_status=ReviewStatus.APPROVED.value, index_status="indexed", content_hash="demo-food", file_name="demo-food.txt", mime_type="text/plain", raw_content=b"demo", active=True, created_by=admin.id, approved_by=admin.id)
            db.add(food_doc)
            db.flush()
            food_content = "A balanced meal can include a variety of foods from the food groups appropriate to the user's needs and preferences. This demo does not prescribe quantities or replace individualized nutrition advice from a qualified clinician."
            db.add(KnowledgeChunk(document_id=food_doc.id, source_id=food_source.id, chunk_index=0, content=food_content, embedding=_seed_embedding(food_content)))
        if db.execute(select(FoodItem).where(FoodItem.name == "Demo seasonal fruit")).scalar_one_or_none() is None:
            db.add(FoodItem(name="Demo seasonal fruit", local_names=["demo seasonal fruit"], region="India", cuisine="regional", ingredients=["demo placeholder"], dietary_types=["vegetarian", "vegan"], nutrition_metadata={"demo": True}, pregnancy_context="Use only as a placeholder until a current reviewed food source is loaded.", evidence_status=EvidenceLevel.SUPPORTED.value, safety_status=SafetyStatus.SAFE_GENERAL.value, source_ids=[food_source.id]))
        if db.execute(select(ExerciseGuidance).where(ExerciseGuidance.title == "Demo gentle walking")).scalar_one_or_none() is None:
            db.add(ExerciseGuidance(category="activity", title="Demo gentle walking", description="Demo guidance only. Discuss activity and restrictions with your maternity-care professional.", suitable_stages=["first_trimester", "second_trimester", "third_trimester"], restrictions=[], evidence_status=EvidenceLevel.SUPPORTED.value, safety_status=SafetyStatus.SAFE_GENERAL.value, source_ids=[food_source.id]))

        ayurveda_source = _source(
            db,
            "garbhini-paricharya-demo",
            name="garbhini-paricharya-demo",
            title="DEMO DATA — traditional provenance record",
            source_type=SourceType.TRADITIONAL.value,
            authority="Traditional source; not a government clinical guideline",
            jurisdiction="India",
            topic="ayurveda",
            version="demo-2026",
            review_status=ReviewStatus.APPROVED.value,
            evidence_level=EvidenceLevel.TRADITIONAL.value,
            description="Synthetic provenance record. Do not treat as a substitute for clinical review.",
            extra_metadata={"demo_data": True, "review_note": "Replace with a reviewed source and translation."},
        )
        ayurveda_doc = db.execute(select(KnowledgeDocument).where(KnowledgeDocument.source_id == ayurveda_source.id)).scalar_one_or_none()
        if ayurveda_doc is None:
            ayurveda_doc = KnowledgeDocument(source_id=ayurveda_source.id, title="DEMO DATA — traditional guidance", domain="ayurveda", language="en", region="India", review_status=ReviewStatus.APPROVED.value, index_status="indexed", content_hash="demo-ayurveda", file_name="demo-ayurveda.txt", mime_type="text/plain", raw_content=b"demo", active=True, created_by=admin.id, approved_by=admin.id)
            db.add(ayurveda_doc)
            db.flush()
            ayurveda_content = "This synthetic traditional record is provided only to demonstrate provenance and evidence labels. It is not a government guideline and must not be used to diagnose or treat a condition."
            db.add(KnowledgeChunk(document_id=ayurveda_doc.id, source_id=ayurveda_source.id, chunk_index=0, content=ayurveda_content, embedding=_seed_embedding(ayurveda_content)))
        if db.execute(select(AyurvedicSource).where(AyurvedicSource.source_id == ayurveda_source.id)).scalar_one_or_none() is None:
            db.add(AyurvedicSource(source_id=ayurveda_source.id, book="DEMO traditional text", chapter="Demo chapter", verse_or_page="Demo locator", original_text="Synthetic placeholder", translation="Synthetic placeholder", interpretation="Traditional content is labelled separately and is not automatically safe or clinically established.", traditional_context="Demo only", evidence_label="traditional", provenance={"demo_data": True}))

        db.commit()
        print("Seeded DEMO DATA successfully")
        print("Demo accounts: admin@demo.example.com, evaluator@demo.example.com, demo.a@example.com")
        print(f"Demo password: {DEMO_PASSWORD}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()
    seed_demo_data()
