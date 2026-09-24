import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.context_packet import build_context_packet
from app.rag.grounding import (
    INSUFFICIENT_EVIDENCE_RESPONSE,
    generate_or_insufficient_evidence,
    has_sufficient_evidence,
)
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk


def make_chunk(chunk_id: str) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        source_id="src-1",
        domain=Domain.NUTRITION,
        evidence_level=EvidenceLevel.SUPPORTED,
        content="content",
        chunk_index=0,
    )


class PoisonCompletions:
    """Raises if called at all -- proves the LLM was never invoked."""

    def create(self, **kwargs):
        raise AssertionError("Groq was called when evidence was insufficient")


class PoisonClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=PoisonCompletions())


class FakeCompletions:
    def __init__(self, content: str):
        self.content = content
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


class FakeClient:
    def __init__(self, content: str):
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


def test_has_sufficient_evidence_empty_list_is_false() -> None:
    assert has_sufficient_evidence([]) is False


def test_has_sufficient_evidence_all_zero_scores_is_false() -> None:
    assert has_sufficient_evidence([(make_chunk("a"), 0.0), (make_chunk("b"), 0.0)]) is False


def test_has_sufficient_evidence_positive_score_is_true() -> None:
    assert has_sufficient_evidence([(make_chunk("a"), 0.5)]) is True


def test_insufficient_evidence_never_calls_the_llm() -> None:
    packet = build_context_packet("out of corpus question", [], safety_result={})
    result = generate_or_insufficient_evidence(packet, [], client=PoisonClient())
    assert result == INSUFFICIENT_EVIDENCE_RESPONSE


def test_sufficient_evidence_delegates_to_generation() -> None:
    chunk = make_chunk("a")
    packet = build_context_packet("in corpus question", [(chunk, 1.0)], safety_result={})
    client = FakeClient("a real grounded answer [a]")
    result = generate_or_insufficient_evidence(packet, [(chunk, 1.0)], client=client)
    assert result == "a real grounded answer [a]"
    assert client.completions.calls == 1
