from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_sample_project_and_report_are_available_without_model():
    sample = client.get("/api/demo")
    report = client.get("/api/demo-report")
    assert sample.status_code == 200
    assert "PROJECT QUOTE" in sample.json()["quote_text"]
    assert report.status_code == 200
    assert report.json()["mode"] == "illustrative_demo"
    assert len(report.json()["findings"]) >= 3


def test_analyze_requires_both_inputs():
    response = client.post("/api/analyze", data={"quote_text": "A quote", "messages_text": ""})
    assert response.status_code == 400
    assert "conversation" in response.json()["detail"].lower()
