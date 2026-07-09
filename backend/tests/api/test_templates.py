import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import get_current_user

client = TestClient(app)

@pytest.fixture
def clean_dependency_overrides():
    old_override = app.dependency_overrides.pop(get_current_user, None)
    yield
    if old_override is not None:
        app.dependency_overrides[get_current_user] = old_override

@pytest.fixture
def auth_client_a(db, clean_dependency_overrides):
    client.post("/api/v1/auth/register", json={
        "email": "user_a@test.com", "username": "user_a", "password": "password"
    })
    res = client.post("/api/v1/auth/login", json={
        "username_or_email": "user_a@test.com", "password": "password"
    })
    token = res.json()["access_token"]
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c

@pytest.fixture
def auth_client_b(db, clean_dependency_overrides):
    client.post("/api/v1/auth/register", json={
        "email": "user_b@test.com", "username": "user_b", "password": "password"
    })
    res = client.post("/api/v1/auth/login", json={
        "username_or_email": "user_b@test.com", "password": "password"
    })
    token = res.json()["access_token"]
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c

def test_template_crud(auth_client_a):
    # Create
    res = auth_client_a.post("/api/v1/templates/", json={
        "name": "My Template",
        "system_prompt": "System",
        "prompt_template": "Transcript: {transcript}"
    })
    assert res.status_code == 201
    t_id = res.json()["id"]

    # Read
    res = auth_client_a.get("/api/v1/templates/")
    assert len(res.json()) == 1
    assert res.json()[0]["name"] == "My Template"

    # Update
    res = auth_client_a.put(f"/api/v1/templates/{t_id}", json={
        "name": "Updated Template"
    })
    assert res.status_code == 200
    assert res.json()["name"] == "Updated Template"

    # Delete
    res = auth_client_a.delete(f"/api/v1/templates/{t_id}")
    assert res.status_code == 204

    # Read again
    res = auth_client_a.get("/api/v1/templates/")
    assert len(res.json()) == 0

def test_template_validation(auth_client_a):
    # Missing {transcript}
    payload_1 = {
        "name": "Bad Template",
        "prompt_template": "No placeholder here."
    }
    print(f"\\n--- [EVIDENCE] Validation: Missing {{transcript}} ---")
    print(f"Request: POST /api/v1/templates/ | Payload: {payload_1}")
    res = auth_client_a.post("/api/v1/templates/", json=payload_1)
    print(f"Response Status: {res.status_code}")
    print(f"Response Body: {res.text}")
    assert res.status_code == 422
    assert "must contain the {transcript} placeholder" in res.text

    # Malformed template
    payload_2 = {
        "name": "Bad Template 2",
        "prompt_template": "Placeholder {transcript} but also {unknown_var}"
    }
    print(f"\\n--- [EVIDENCE] Validation: Malformed Brace ---")
    print(f"Request: POST /api/v1/templates/ | Payload: {payload_2}")
    res = auth_client_a.post("/api/v1/templates/", json=payload_2)
    print(f"Response Status: {res.status_code}")
    print(f"Response Body: {res.text}")
    assert res.status_code == 422
    assert "unknown variable" in res.text

def test_custom_template_isolation(auth_client_a, auth_client_b):
    # User A creates a template
    res = auth_client_a.post("/api/v1/templates/", json={
        "name": "User A Template",
        "prompt_template": "Transcript: {transcript}"
    })
    assert res.status_code == 201
    a_template_id = res.json()["id"]

    # User B tries to read User A's template (not possible via list)
    res = auth_client_b.get("/api/v1/templates/")
    assert len(res.json()) == 0

    # User B tries to update User A's template
    res = auth_client_b.put(f"/api/v1/templates/{a_template_id}", json={
        "name": "Hacked"
    })
    assert res.status_code == 404

    # User B tries to use User A's template in summarization
    payload = {
        "transcript": "Hello this is a test transcript with enough words.",
        "task": "summarize",
        "model": "qwen3:1.7b",
        "custom_template_id": a_template_id
    }
    print(f"\\n--- [EVIDENCE] Isolation: User B using User A's template ---")
    print(f"Request: POST /api/v1/summarization/process | Payload: {payload}")
    res = auth_client_b.post("/api/v1/summarization/process", json=payload)
    print(f"Response Status: {res.status_code}")
    print(f"Response Body: {res.text}")
    assert res.status_code == 404
    assert "Custom template not found" in res.text
