from fastapi.testclient import TestClient
from clinical_trial_matcher.main import app

def test_health_returns_ok():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_search_rejects_missing_query():
    with TestClient(app) as client:
        response = client.post("/search", json={"top_k": 3})
    assert response.status_code == 422

def test_search_returns_expected_results():
    with TestClient(app) as client:
        response = client.post("/search", json={"query": "Is there a trial for someone whose blood sugar is too high?", "top_k": 5})

    assert response.status_code == 200

    data = response.json()
    scores = [r["score"] for r in data["results"]]

    assert isinstance(data["results"], list)
    assert len(data["results"]) == data["result_count"]
    assert scores == sorted(scores, reverse=True)