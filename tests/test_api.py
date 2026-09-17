from fastapi.testclient import TestClient

from app.api import app


client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_preview_reads_local_data():
    response = client.post(
        "/preview",
        json={"execution_date": "2026-09-17", "lead_ids": [1, 2]},
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["lead_id"] == 1
