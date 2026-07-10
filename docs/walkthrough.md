# BriefAI Repository Restructure Walkthrough

I've completed the structural refactor to align BriefAI with the Open WebUI conventions! Here's a summary of what was accomplished and verified.

## 1. Backend Restructure
- Renamed the main application directory: `backend/app/` ➡️ `backend/briefai/`.
- Renamed the Alembic migrations folder: `backend/alembic/` ➡️ `backend/migrations/`.
- Split monolithic `models.py` into individual files inside `backend/briefai/models/` (users, transcripts, summaries, templates).
- Split monolithic `schemas.py` into individual files inside `backend/briefai/schemas/` (auth, transcription, summarization, templates).
- Updated internal imports across all Python files to correctly use the new `briefai.*` package namespace.
- Updated `alembic.ini` and `migrations/env.py` to point to the new paths.
- Updated `backend/entrypoint.sh` to run `uvicorn briefai.main:app`.
- **Verification**: `pytest backend/tests/` now passes cleanly!

## 2. Frontend Restructure
- Created a new `frontend/src/screens/` directory for full-page views.
- Moved the following components to `screens/` because they act as full screens instead of embedded widgets:
  - `AuthScreen.tsx`
  - `AskBriefAI.tsx`
  - `Templates.tsx`
  - `BenchmarkDashboard.tsx`
- Kept UI widgets (like `TaskGridSelector` and `TranscriptsSidebar`) in `components/`.
- Updated all React imports and fixed a CSS reference issue with `AskBriefAI.css`.
- **Verification**: `npm run build` inside `frontend/` completes successfully without any TS or Vite errors!

## 3. Running the App & Generating a Public Link

Currently, your Docker Desktop is not running, so I couldn't automatically bring the containers back up or verify the public link. To start the app and share it:

1. **Start Docker Desktop** from your Windows start menu.
2. Once Docker is running, open a terminal in the `briefai` folder and run:
   ```bash
   docker-compose up -d --build
   ```
   *(The `--build` flag is crucial because we changed the folder structures!)*
3. **To generate the public link**, run the Cloudflare tunnel in your terminal:
   ```bash
   .\cloudflared.exe tunnel --url http://localhost:80
   ```
   Copy the `https://<random-words>.trycloudflare.com` URL that it outputs and share it with others!

> [!NOTE]
> If you still experience issues with transcribing or summarization, make sure Ollama is running and configured to accept external connections (by setting `OLLAMA_HOST=0.0.0.0` in your system environment variables and restarting the Ollama app from the system tray).
