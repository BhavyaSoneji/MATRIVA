import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.keyword_search import keyword_overlap_score
from app.rag.query_rewriting import UserProfile, rewrite_query
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk


def make_chunk(chunk_id: str, content: str) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        source_id="src-1",
        domain=Domain.NUTRITION,
        evidence_level=EvidenceLevel.SUPPORTED,
        content=content,
        chunk_index=0,
    )


def test_no_profile_info_returns_only_the_raw_query() -> None:
    result = rewrite_query("What can I eat?", UserProfile())
    assert result == ["What can I eat?"]


def test_pregnancy_stage_generates_a_variant() -> None:
    result = rewrite_query("What can I eat?", UserProfile(pregnancy_stage="second_trimester"))
    assert "What can I eat? second_trimester" in result


def test_diet_generates_a_variant() -> None:
    result = rewrite_query("What can I eat?", UserProfile(diet="vegetarian"))
    assert "What can I eat? vegetarian diet" in result


def test_region_generates_a_variant() -> None:
    result = rewrite_query("What can I eat?", UserProfile(region="Gujarat"))
    assert "What can I eat? Gujarat regional" in result


def test_each_restriction_generates_its_own_variant() -> None:
    result = rewrite_query(
        "What can I eat?", UserProfile(restrictions=["avoid papaya", "lactose intolerant"])
    )
    assert "What can I eat? avoid papaya" in result
    assert "What can I eat? lactose intolerant" in result


def test_full_profile_generates_all_variants_plus_original() -> None:
    profile = UserProfile(
        pregnancy_stage="third_trimester",
        diet="vegan",
        region="Kerala",
        restrictions=["nut allergy"],
    )
    result = rewrite_query("What can I eat?", profile)
    assert len(result) == 5  # original + stage + diet + region + 1 restriction
    assert result[0] == "What can I eat?"


def test_rewriting_never_invents_new_medical_terms() -> None:
    """Section 23: personalization selects relevant info, never invents
    medical guidance -- every generated variant must be built purely from
    the raw query plus profile fields the caller supplied, nothing else."""
    profile = UserProfile(pregnancy_stage="first_trimester", diet="vegetarian")
    result = rewrite_query("What can I eat?", profile)
    for variant in result:
        assert variant.startswith("What can I eat?")
        extra = variant.removeprefix("What can I eat?").strip()
        if extra:
            assert profile.pregnancy_stage in extra or profile.diet in extra


def test_same_raw_query_different_profiles_retrieve_different_top_chunk() -> None:
    """Acceptance criteria: same query + different profiles -> different
    relevant docs. Corpus has a vegetarian-focused chunk and a
    Kerala-regional chunk; different profiles should surface different
    top matches via keyword-overlap scoring over the rewritten queries."""
    vegetarian_chunk = make_chunk(
        "veg", "vegetarian diet protein sources moong dal paneer tofu lentils"
    )
    kerala_chunk = make_chunk(
        "kerala", "Kerala regional pregnancy foods coconut rice fish curry traditions"
    )
    corpus = [vegetarian_chunk, kerala_chunk]

    def top_chunk_for(profile: UserProfile) -> str:
        queries = rewrite_query("What can I eat?", profile)
        combined_query_text = " ".join(queries)
        scored = [
            (chunk, keyword_overlap_score(combined_query_text, chunk.content))
            for chunk in corpus
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[0][0].chunk_id

    vegetarian_profile = UserProfile(diet="vegetarian")
    kerala_profile = UserProfile(region="Kerala")

    assert top_chunk_for(vegetarian_profile) == "veg"
    assert top_chunk_for(kerala_profile) == "kerala"
