import pytest
from backend.abstention import llm_abstained, should_abstain

def test_abstains_when_no_score_reaches_threshold():
    assert should_abstain([{"similarity_score": 0.2}], 0.35) == (True, 0.2)

def test_allows_when_best_score_reaches_threshold():
    # should_abstain scores the *average* of the top-3 chunks, not the max.
    abstained, confidence = should_abstain([{"similarity_score": 0.2}, {"similarity_score": 0.7}], 0.35)
    assert abstained is False
    assert confidence == pytest.approx(0.45)

def test_llm_abstained_detects_refusals():
    assert llm_abstained("I don't know the answer to that.")
    assert llm_abstained("I cannot answer that from my own memory.")
    assert llm_abstained("I'm not sure what the university policy is.")

def test_llm_abstained_ignores_given_answers():
    assert not llm_abstained("The graduation requirement is 120 credits.")
    assert not llm_abstained("Hello! How can I help you today?")

def test_llm_abstained_is_case_insensitive_and_empty_safe():
    assert llm_abstained("I DON'T KNOW")
    assert not llm_abstained("")
    assert not llm_abstained(None)
