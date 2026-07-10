# BriefAI PROGRESS_LOG.md

This file is the source of truth for project history. Updated at the end of each working session.
Do not rely on assumptions - read this file first every session.

---

## Session 1 - Security Hardening Before Public Tunnel Activation
**Date:** 2026-07-10

### Context
An ngrok authtoken and account email were accidentally exposed in a previous AI chat session screenshot.
This session performed a full security review and hardening before the app goes publicly live via ngrok.

---

### PRIORITY 1 - ngrok Token Rotation (MANUAL ACTION REQUIRED BY YOU)

The exposed token cannot be rotated programmatically. You must:
1. Go to https://dashboard.ngrok.com/authtokens
2. Revoke/delete the old token
3. Generate a new one
4. Run: `ngrok config add-authtoken <new_token>`
5. Verify: `ngrok config check` should show your email + new credential

After step 4, the old token is dead - any tunnel attempt with the old config will fail with an auth error.

---

### PRIORITY 2 - Security Review Results (all evidence is real command output)

#### 1. JWT Secret Key - FIXED
WHAT WAS FOUND:
- backend/briefai/config.py had a hardcoded 56-char hex string as the DEFAULT for JWT_SECRET_KEY
- backend/.env had NO JWT_SECRET_KEY entry - app was running entirely on the hardcoded source-code fallback
- This value was visible in any git log or code review

WHAT WAS DONE:
- Generated a new cryptographically random 64-char hex secret via secrets.token_hex(32) (Python 3.13)
- Written to backend/.env as JWT_SECRET_KEY (not shown here - redacted)
- config.py hardcoded default REMOVED - field is now `JWT_SECRET_KEY: str` with NO default
  - App will FAIL TO START if JWT_SECRET_KEY is missing from .env (fail-safe behavior)

EVIDENCE (actual command output):
  JWT_SECRET_KEY present in .env: YES
  Length: 64
  Format check (all hex chars): True
  First 4 chars: 0b39...
  config.py:35: JWT_SECRET_KEY: str

#### 2. Debug Mode - FIXED
WHAT WAS FOUND:
- config.py had DEBUG: bool = True as the default
- docker-compose.yml does NOT pass DEBUG= env var, so Docker inherited the True default
- entrypoint.sh uses: exec python -m uvicorn briefai.main:app --host 0.0.0.0 --port 8000
  (no --reload, no --log-level debug - uvicorn startup was OK)
- FastAPI constructor has no debug=True flag
- But DEBUG=True in settings exposes verbose tracebacks via exception handlers

WHAT WAS DONE:
- config.py line 23 changed to: DEBUG: bool = False
  Comment: Must be explicitly enabled via .env; defaults secure-off

EVIDENCE:
  config.py:23: DEBUG: bool = False  # Must be explicitly enabled via .env; defaults secure-off

#### 3. Rate Limiting - CONFIRMED CORRECT (no changes needed)
ACTUAL DECORATORS IN auth.py:
  @limiter.limit("3/30minutes")  on /auth/register
  @limiter.limit("5/5minutes")   on /auth/login

LIMITER SETUP in utils/limiter.py:
  limiter = Limiter(key_func=get_remote_address)

WIRED IN main.py:
  app.state.limiter = limiter
  app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

Rate limits are correctly configured and wired end-to-end. slowapi uses get_remote_address which
reads X-Forwarded-For when present (ngrok sets this). Verify per-client enforcement after first
live tunnel test.

#### 4. CORS Configuration - FIXED (minor)
WHAT WAS FOUND:
- main.py uses allow_origins=settings.CORS_ORIGINS - NOT wildcard *, correct
- allow_credentials=True - correct (needed for HttpOnly refresh token cookie)
- BUT config.py had a hardcoded stale Cloudflare URL in the CORS_ORIGINS default list:
  https://save-twist-moving-boss.trycloudflare.com  (leftover from a previous dev session)

WHAT WAS DONE:
- Removed the stale Cloudflare URL from CORS_ORIGINS default in config.py
- Defaults are now: ["http://localhost:5173", "http://localhost:3000"]
- To enable the ngrok domain, add to backend/.env:
  CORS_ORIGINS=http://localhost:5173,http://localhost:3000,https://magnetic-status-unsecured.ngrok-free.dev

EVIDENCE:
  config.py:28: CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

#### 5. Cookie Secure Flag - FIXED (bonus issue)
WHAT WAS FOUND:
- auth.py had secure=False hardcoded on the refresh token HttpOnly cookie
  with comment "Set to True in production (requires HTTPS)" - it was NEVER actually set

WHAT WAS DONE:
- Changed to: secure=not settings.DEBUG
  When DEBUG=False (production): cookie is Secure (HTTPS only)
  When DEBUG=True (local dev): cookie not Secure (HTTP works)

EVIDENCE:
  auth.py:104: secure=not settings.DEBUG,  # True in production (HTTPS); False only in dev

---

### Docker Status at End of Session
Docker Desktop: NOT RUNNING (daemon not found).
No containers were started this session.

---

### Pre-Launch Checklist (complete BEFORE running docker-compose)
[ ] YOU: Rotate ngrok authtoken (Priority 1 above)
[ ] Add JWT_SECRET_KEY to backend/.env if deploying fresh (already done on this machine)
[ ] Add CORS_ORIGINS to backend/.env including the ngrok domain
[ ] Start Docker Desktop
[ ] docker-compose up -d --build
[ ] docker ps (verify both containers healthy)
[ ] ngrok http --domain=magnetic-status-unsecured.ngrok-free.dev 80
[ ] curl https://magnetic-status-unsecured.ngrok-free.dev/health

---

### Files Modified This Session
| File                                    | Change                                                              |
|-----------------------------------------|---------------------------------------------------------------------|
| backend/.env                            | Added JWT_SECRET_KEY (64-char hex, cryptographically random)        |
| backend/briefai/config.py               | Removed hardcoded JWT default; DEBUG->False; removed stale CF URL   |
| backend/briefai/routers/auth.py         | Cookie secure flag now not settings.DEBUG (env-driven)              |
| PROGRESS_LOG.md                         | Created (this file)                                                 |

---

### Outstanding Items for Next Session
- [ ] YOU: Rotate ngrok token (https://dashboard.ngrok.com/authtokens)
- [ ] Add CORS_ORIGINS with ngrok domain to backend/.env before starting tunnel
- [ ] Start Docker Desktop, run docker-compose up -d --build, verify both containers healthy
- [ ] Test rate limiting through live ngrok tunnel (confirm per-client IP enforcement works)
- [ ] Consider disabling or auth-gating /docs and /redoc in production (currently public)
- [ ] Consider adding APP_ENV=production to docker-compose environment block


---

## Session 2 -- Docker Launch, Rate-Limit Fix, and Live Tunnel Verification
**Date:** 2026-07-10

### Context
Session 1 hardened security. Session 2 got the app live through the ngrok tunnel and verified
the rate limiter works correctly per real client IP.

---

### Step 1: ngrok Token Rotation
Confirmed by user. ngrok config check shows a valid token (length=49, new format).
Tunnel connected as account talhasaleemab@gmail.com via India region.

### Step 2: CORS_ORIGINS and docker-compose.yml fixes

Two bugs found and fixed:

**Bug 1: docker-compose.yml did not pass .env to the container**
docker-compose.yml had hardcoded environment vars but no env_file directive.
The container never received JWT_SECRET_KEY, causing immediate startup crash:
  pydantic_core.ValidationError: JWT_SECRET_KEY Field required

Fix: Added env_file: ./backend/.env to the backend service in docker-compose.yml.

**Bug 2: CORS_ORIGINS env format incompatible with pydantic-settings v2**
.env had CORS_ORIGINS as a comma-separated string. pydantic-settings v2 tries to
JSON-decode List[str] fields from env_file sources before running field_validators.
This caused: SettingsError: error parsing value for field "CORS_ORIGINS"

Fix (two-part):
1. Added field_validator("CORS_ORIGINS", mode="before") to config.py that handles
   both comma-separated strings and JSON arrays.
2. Changed .env to use JSON array format:
   CORS_ORIGINS=["http://localhost:5173","http://localhost:3000","https://magnetic-status-unsecured.ngrok-free.dev"]

### Step 3: Container Health Confirmed

docker ps output (both containers up):
  briefai-backend-1    Up   0.0.0.0:8000->8000/tcp
  briefai-frontend-1   Up   0.0.0.0:80->80/tcp

http://localhost:8000/health response:
  {"status": "ok", "app": "BriefAI", "version": "0.2.0"}

ngrok tunnel online:
  https://magnetic-status-unsecured.ngrok-free.dev -> localhost:80
  Frontend HTML confirmed served at public URL.
  /api/ routes proxied through nginx to backend (confirmed via /api/v1/auth/me returning 401, not HTML).

### Step 4: Rate Limiter Bug Found and Fixed

**Bug found: rate limiter was tracking nginx container IP, not real client IP**

Before fix, slowapi warning log showed:
  ratelimit 5 per 5 minute (172.18.0.3) -- this is the nginx container IP

Root cause: slowapi's default get_remote_address() only reads request.client.host
(the TCP connection source). Behind nginx, ALL requests come from 172.18.0.3.
This means any 5 login attempts by ANYONE through the tunnel would lock out ALL users.

Fix: Replaced get_remote_address with a custom get_forwarded_address() in
backend/briefai/utils/limiter.py that reads X-Forwarded-For header first:
  - nginx.conf already sets X-Forwarded-For via proxy_set_header
  - New key function takes the first IP from X-Forwarded-For (real client)
  - Falls back to request.client.host for direct connections

### Step 5: Rate Limit Test -- Real Evidence

Test: 6 rapid POST /api/v1/auth/login via https://magnetic-status-unsecured.ngrok-free.dev
Headers: ngrok-skip-browser-warning: 1, Content-Type: application/json

Results:
  Attempt 1: HTTP 401 (wrong credentials -- expected)
  Attempt 2: HTTP 401
  Attempt 3: HTTP 401
  Attempt 4: HTTP 401
  Attempt 5: HTTP 401
  Attempt 6: HTTP 429 (rate limit hit -- correct)

slowapi log confirming real IP tracking:
  WARNING slowapi -- ratelimit 5 per 5 minute (111.68.96.42) exceeded at /api/v1/auth/login
  (111.68.96.42 is the real public client IP, NOT 172.18.0.3 the nginx container IP)

VERIFIED: Rate limiter is working correctly per real client IP via X-Forwarded-For.

---

### Files Modified This Session

| File                                         | Change                                                              |
|----------------------------------------------|---------------------------------------------------------------------|
| docker-compose.yml                           | Added env_file: ./backend/.env; removed duplicate hardcoded vars    |
| backend/.env                                 | CORS_ORIGINS changed to JSON array format                           |
| backend/briefai/config.py                    | Added field_validator for CORS_ORIGINS (comma and JSON support)     |
| backend/briefai/utils/limiter.py             | Replaced get_remote_address with X-Forwarded-For-aware key function |
| PROGRESS_LOG.md                              | This entry                                                          |

---

### Outstanding Items

- [ ] Consider disabling /docs and /redoc in production (currently public, no auth gate)
- [ ] Consider adding APP_ENV=production to docker-compose environment block
- [ ] Monitor: confirm rate limit window resets correctly after 5 minutes
- [ ] If second device test is needed: use a phone on mobile data to confirm different IPs get independent counters
