from fastapi.testclient import TestClient

from dewaag.api import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "constitution_signed" in body


def test_root_serves_something_that_boots():
    # Phase 0: a plain status page. Phase 2+: the built React app.
    # Either way "/" must never 404 — the front door always opens.
    r = client.get("/")
    assert r.status_code == 200
    assert ("root" in r.text) or ("De Waag" in r.text)


def test_status_page_shows_constitution():
    r = client.get("/status")
    assert r.status_code == 200
    assert "De Waag" in r.text
    assert "constitution" in r.text.lower()


def test_constitution_endpoint():
    r = client.get("/api/constitution")
    assert r.status_code == 200
    assert r.json()["leverage"] == 0
