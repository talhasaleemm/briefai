"""
Precise rate-limit threshold diagnostic.

Fires 8 login attempts with bad credentials against the TestClient and prints
the status code for each attempt, verifying:
  - Attempts 1-5  → 401 Unauthorized (bad credentials reach the handler)
  - Attempt 6     → 429 Too Many Requests (rate limit fires exactly at threshold)
  - Attempts 7-8  → 429 (window has not reset)
"""
import os
os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
os.environ.setdefault("WHISPER_DEVICE", "cpu")
os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from briefai.main import app
from briefai.internal.db import Base, get_db
from briefai.utils.limiter import limiter

# ── In-memory test database ───────────────────────────────────────────────────
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

session = SessionLocal()

def get_db_override():
    try:
        yield session
    finally:
        pass

app.dependency_overrides[get_db] = get_db_override

client = TestClient(app, raise_server_exceptions=False)

# ── Run diagnostic ────────────────────────────────────────────────────────────
limiter.reset()

payload = {"username_or_email": "nobody", "password": "wrongpassword"}

print("\nPer-attempt login status codes (threshold = 5/5minutes):\n")
print(f"{'Attempt':>8}  {'Status':>8}  Note")
print("-" * 45)

all_codes = []
for i in range(1, 9):
    resp = client.post("/api/v1/auth/login", json=payload)
    code = resp.status_code
    all_codes.append(code)

    if code == 401:
        note = "401 Unauthorized (bad creds — handler reached)"
    elif code == 429:
        note = "429 Too Many Requests (rate limit triggered)"
    else:
        note = f"unexpected {code}"

    print(f"{i:>8}  {code:>8}  {note}")

print("-" * 45)
print(f"\nFull sequence: {all_codes}")

# ── Assertions ────────────────────────────────────────────────────────────────
assert all(c == 401 for c in all_codes[:5]), \
    f"Expected 401 for attempts 1-5, got: {all_codes[:5]}"
assert all_codes[5] == 429, \
    f"Expected 429 at attempt 6, got: {all_codes[5]}"
assert all(c == 429 for c in all_codes[6:]), \
    f"Expected 429 for attempts 7+, got: {all_codes[6:]}"

print("\n✅ PASS: Rate limit fires at exactly attempt 6 (threshold=5/5minutes)")

session.close()
limiter.reset()
