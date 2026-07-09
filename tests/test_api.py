from fastapi.testclient import TestClient

from dewaag.api import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "constitution_signed" in body


def test_home_page_boots_and_shows_constitution():
    r = client.get("/")
    assert r.status_code == 200
    assert "De Waag" in r.text
    assert "Risk per idea" in r.text


def test_constitution_endpoint():
    r = client.get("/api/constitution")
    assert r.status_code == 200
    assert r.json()["leverage"] == 0
