import pytest
from fastapi.testclient import TestClient
from briefai.main import app
from briefai.utils.deps import get_current_user

client = TestClient(app, raise_server_exceptions=False)


def _register_and_login(db, email: str, username: str, password: str = "password") -> str:
    """
    Register (idempotent) and log in a real user, returning a real JWT.
    The default mock auth override must be popped by the caller so this
    JWT is actually validated (Stage 7 test_true_e2e_jwt_isolation pattern).
    """
    reg = client.post("/api/v1/auth/register", json={
        "email": email, "username": username, "password": password
    })
    # 400 means already registered (re-use is fine)
    assert reg.status_code in (201, 400), f"Register failed: {reg.text}"

    res = client.post("/api/v1/auth/login", json={
        "username_or_email": email, "password": password
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


def _auth_client(token: str) -> TestClient:
    """Return a TestClient whose requests carry a real Bearer JWT."""
    c = TestClient(app, raise_server_exceptions=False)
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c


@pytest.fixture
def auth_client_a(db):
    # Pop the autouse default mock override so the real JWT is validated,
    # exactly like test_true_e2e_jwt_isolation in Stage 7.
    app.dependency_overrides.pop(get_current_user, None)
    token = _register_and_login(db, "user_a@test.com", "user_a")
    return _auth_client(token)


@pytest.fixture
def auth_client_b(db):
    app.dependency_overrides.pop(get_current_user, None)
    token = _register_and_login(db, "user_b@test.com", "user_b")
    return _auth_client(token)


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
    print(f"\n--- [EVIDENCE] Validation: Missing {{transcript}} ---")
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
    print(f"\n--- [EVIDENCE] Validation: Malformed Brace ---")
    print(f"Request: POST /api/v1/templates/ | Payload: {payload_2}")
    res = auth_client_a.post("/api/v1/templates/", json=payload_2)
    print(f"Response Status: {res.status_code}")
    print(f"Response Body: {res.text}")
    assert res.status_code == 422
    assert "unknown variable" in res.text

def test_custom_template_isolation(auth_client_a, auth_client_b):
    # User A creates a template (authenticated via real A-JWT)
    res = auth_client_a.post("/api/v1/templates/", json={
        "name": "User A Template",
        "prompt_template": "Transcript: {transcript}"
    })
    assert res.status_code == 201
    a_template_id = res.json()["id"]

    # User B (real B-JWT) must NOT see User A's template via list
    res = auth_client_b.get("/api/v1/templates/")
    assert len(res.json()) == 0

    # User B cannot update User A's template (must be 404)
    res = auth_client_b.put(f"/api/v1/templates/{a_template_id}", json={
        "name": "Hacked"
    })
    assert res.status_code == 404

    # User B cannot use User A's template in summarization (must be 404)
    payload = {
        "transcript": "Hello this is a test transcript with enough words.",
        "task": "summarize",
        "model": "qwen3:1.7b",
        "custom_template_id": a_template_id
    }
    print(f"\n--- [EVIDENCE] Isolation: User B using User A's template ---")
    print(f"Request: POST /api/v1/summarization/process | Payload: {payload}")
    res = auth_client_b.post("/api/v1/summarization/process", json=payload)
    print(f"Response Status: {res.status_code}")
    print(f"Response Body: {res.text}")
    assert res.status_code == 404
    assert "Custom template not found" in res.text
