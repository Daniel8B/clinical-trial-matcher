from fastapi.testclient import TestClient
from clinical_trial_matcher.main import app

client = TestClient(app)

def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_search_rejects_missing_query():
    response = client.post("/search", json={"top_k": 3})
    assert response.status_code == 422

def test_prediction_returns_expected_result():
    with TestClient(app) as client:
        response = client.post("/predict", json={"feature_1": 1.5, "feature_2": -0.3})

    assert response.status_code == 200

    data = response.json()
    assert "prediction" in data
    assert isinstance(data["prediction"], int)
