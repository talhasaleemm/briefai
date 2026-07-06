# BriefAI — Real-Time Meeting Transcription & Multilingual Summarization Platform

> **Status:** 🚧 Under active development — Stage 1 (Scaffold) complete.

BriefAI converts live speech or pasted meeting notes into structured summaries, translations, action items, and searchable Markdown documents — all running locally via open-weight LLMs.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          BriefAI                                │
│                                                                 │
│   ┌──────────────┐    WebSocket    ┌──────────────────────────┐ │
│   │   Frontend   │◄───────────────►│   FastAPI Backend        │ │
│   │  (React/Vite)│    REST/HTTP    │                          │ │
│   └──────────────┘                 │  ┌────────────────────┐  │ │
│                                    │  │ Transcription       │  │ │
│                                    │  │ (faster-whisper)    │  │ │
│                                    │  └────────────────────┘  │ │
│                                    │  ┌────────────────────┐  │ │
│                                    │  │ LLM Services        │  │ │
│                                    │  │ (Ollama)            │  │ │
│                                    │  │  • Qwen3-1.7B       │  │ │
│                                    │  │  • Llama 3.2-1B     │  │ │
│                                    │  └────────────────────┘  │ │
│                                    └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Features (Planned)

- 🎤 **Live streaming transcription** via faster-whisper + FastAPI WebSocket
- 🤖 **Structured summarization** with Qwen3-1.7B and Llama 3.2-1B via Ollama
- 🌍 **Multilingual translation** with prompt-engineered templates
- ✅ **Action-item extraction** and decision tracking
- 📄 **Markdown export** of meeting notes
- 📊 **Benchmarking module** for latency, memory, and quality comparison

---

## Tech Stack

| Layer | Technology |
|---|---|
| Speech-to-Text | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) |
| Backend API | [FastAPI](https://fastapi.tiangolo.com/) |
| LLM Runtime | [Ollama](https://ollama.com/) |
| LLM Models | Qwen3-1.7B, Llama 3.2-1B |
| Frontend | React + Vite |
| Python | 3.12 |

---

## Quick Start

### Prerequisites

- Python 3.12 (via `py` launcher or Anaconda)
- [Ollama](https://ollama.com/download) installed and running
- Node.js 18+ (for frontend)
- Git

### 1. Clone the Repository

```powershell
git clone https://github.com/talhasaleemm/briefai.git
cd briefai
```

### 2. Set Up Python Environment

```powershell
# Using venv (recommended)
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r backend/requirements.txt
```

### 3. Configure Environment

```powershell
Copy-Item backend\.env.example backend\.env
# Edit backend\.env with your settings
```

### 4. Pull LLM Models

```powershell
.\scripts\pull_models.ps1
```

### 5. Run the Backend

```powershell
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Run the Frontend

```powershell
cd frontend
npm install
npm run dev
```

---

## Project Structure

```
briefai/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI route handlers
│   │   ├── core/          # Config, settings
│   │   ├── models/        # Pydantic schemas
│   │   ├── services/      # Business logic (whisper, ollama)
│   │   └── prompts/       # LLM prompt templates
│   ├── tests/             # Pytest test suite
│   └── requirements.txt
├── frontend/              # React + Vite app (Stage 6)
├── benchmarks/            # Latency/quality benchmarking (Stage 5)
├── scripts/
│   ├── pull_models.ps1    # Downloads Ollama models
│   └── setup.ps1          # Full environment setup
├── sample_audio/          # Test audio files (not committed)
├── .env.example
└── README.md
```

---

## Development Stages

| Stage | Description | Status |
|---|---|---|
| 1 | Scaffold — folder structure, config, deps | ✅ Complete |
| 2 | Transcription pipeline — faster-whisper + WebSocket | ✅ Complete |
| 3 | Ollama integration — Qwen3 + Llama wired in | ⏳ Pending |
| 4 | Prompt templates — summary, translate, actions | ⏳ Pending |
| 5 | Benchmarking module | ⏳ Pending |
| 6 | Frontend — React/Vite UI | ⏳ Pending |
| 7 | Tests + README polish | ⏳ Pending |
| 8 | CI — GitHub Actions | ⏳ Pending |

---

## Contributing

This project is built stage-by-stage with explicit approval gates. See the Stage Report at the end of each stage for details on what was built and what comes next.

---

## License

MIT
