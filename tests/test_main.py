from fastapi.testclient import TestClient
from clinical_trial_matcher.main import app


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