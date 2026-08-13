from fastapi.testclient import TestClient
from clinical_trial_matcher.main import app
from clinical_trial_matcher.llm import StubClient
from clinical_trial_matcher.main import app, get_llm


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_rejects_missing_query():
    with TestClient(app) as client:
        response = client.post("/search", json={"top_k": 3})
    assert response.status_code == 422


def test_search_returns_shape():
    with TestClient(app) as client:
        response = client.post("/search", json={"query": "diabetes", "top_k": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "diabetes"
    assert data["result_count"] == len(data["results"])
    assert len(data["results"]) <= 3
    for result in data["results"]:
        assert result["nct_id"].startswith("NCT")
        assert isinstance(result["brief_title"], str)
        assert result["section"] in {"inclusion", "exclusion", "brief_summary"}
        assert isinstance(result["chunk_text"], str)
        assert isinstance(result["score"], float)


def test_search_results_are_distinct_trials():
    with TestClient(app) as client:
        response = client.post("/search", json={"query": "diabetes", "top_k": 5})
    nct_ids = [r["nct_id"] for r in response.json()["results"]]
    assert len(nct_ids) == len(set(nct_ids))


def test_search_results_are_descending():
    with TestClient(app) as client:
        response = client.post("/search", json={"query": "cancer", "top_k": 5})
    scores = [r["score"] for r in response.json()["results"]]
    assert scores == sorted(scores, reverse=True)


def test_answer_returns_answer_and_valid_citations():
    stub = StubClient(response="Trial one accepts these patients [1]. Also [9].")
    app.dependency_overrides[get_llm] = lambda: stub
    try:
        with TestClient(app) as client:
            response = client.post(
                "/answer",
                json={"query": "type 2 diabetes trials", "top_k": 5},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["generation_available"] is True
    assert data["reason"] is None
    # [9] does not exist in the evidence and must be dropped.
    assert data["citations"] == [1]
    assert len(data["evidence"]) <= 5


def test_answer_reports_when_generation_is_unavailable():
    stub = StubClient(available=False)
    app.dependency_overrides[get_llm] = lambda: stub
    try:
        with TestClient(app) as client:
            response = client.post(
                "/answer",
                json={"query": "type 2 diabetes trials", "top_k": 5},
            )
    finally:
        app.dependency_overrides.clear()

    data = response.json()
    assert data["generation_available"] is False
    assert data["answer"] is None
    # Evidence is still returned. The endpoint degrades, it does not fail.
    assert len(data["evidence"]) > 0
    assert stub.calls == []


def test_answer_declines_when_no_result_clears_the_threshold():
    stub = StubClient(response="should never be called")
    app.dependency_overrides[get_llm] = lambda: stub
    try:
        with TestClient(app) as client:
            response = client.post(
                "/answer",
                json={"query": "zzzqxv nonexistent condition", "top_k": 5},
            )
    finally:
        app.dependency_overrides.clear()

    data = response.json()
    assert data["answer"] is None
    assert data["reason"] == "no_good_match"
    assert stub.calls == []