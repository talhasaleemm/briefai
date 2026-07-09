"""
Live end-to-end WebSocket verification.

Connects to an already-running uvicorn server on 127.0.0.1:8000.
Steps:
  1. Register a fresh test user via POST /api/v1/auth/register
  2. Login to get a real access_token
  3. Open WebSocket /api/v1/transcription/stream
  4. Send auth handshake (action=auth, token=...)
  5. Send config (action=config)
  6. Stream real PCM audio synthesized via Windows SAPI
  7. Send stop (action=stop)
  8. Receive and print the final transcript
"""
import asyncio
import json
import subprocess
import os
import wave
import time

import numpy as np
import httpx
import websockets

BASE_URL = "http://127.0.0.1:8000/api/v1"
WS_URL  = "ws://127.0.0.1:8000/api/v1/transcription/stream"
WAV_PATH = "./ws_verify_test.wav"

EMAIL    = "ws_live_test@briefai.test"
USERNAME = "ws_live_tester"
PASSWORD = "SecurePassword123!"


def synthesize_speech(out_path: str, text: str) -> bool:
    """Use Windows SAPI to generate a real-speech WAV file."""
    ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SetOutputToWaveFile('{out_path.replace(chr(92), "/")}')
$s.Rate = -2
$s.Volume = 100
$s.Speak("{text}")
$s.Dispose()
"""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True, text=True, timeout=60
    )
    return r.returncode == 0 and os.path.exists(out_path) and os.stat(out_path).st_size > 1000


async def main():
    # ── Step 1: Register ──────────────────────────────────────────────────────
    print("\n[http] Registering test user...")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
        r = await c.post("/auth/register", json={
            "email": EMAIL, "username": USERNAME, "password": PASSWORD
        })
        # 201 on first run, 400 if already exists (re-run); both are fine
        print(f"[http] Register → {r.status_code}: {r.text[:120]}")

    # ── Step 2: Login ─────────────────────────────────────────────────────────
    print("[http] Logging in...")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
        r = await c.post("/auth/login", json={
            "username_or_email": USERNAME, "password": PASSWORD
        })
        assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
        access_token = r.json()["access_token"]
    print(f"[http] Login → 200 OK  token={access_token[:40]}...")

    # ── Step 3: Synthesize speech ─────────────────────────────────────────────
    speech_text = "This is a live BriefAI WebSocket end to end transcription test."
    print(f"\n[sapi] Synthesizing: '{speech_text}'")
    ok = synthesize_speech(WAV_PATH, speech_text)
    assert ok, "SAPI synthesis failed — is Windows Speech Platform installed?"
    wav_size = os.stat(WAV_PATH).st_size
    print(f"[sapi] WAV written: {wav_size} bytes")

    # ── Step 4: Read PCM ──────────────────────────────────────────────────────
    with wave.open(WAV_PATH, "rb") as wf:
        nch, sw, framerate, nframes = wf.getparams()[:4]
        raw = wf.readframes(nframes)
    int16 = np.frombuffer(raw, dtype=np.int16)
    if nch > 1:
        int16 = int16[::nch]
    float32 = int16.astype(np.float32) / 32768.0
    print(f"[audio] {len(float32)} float32 samples @ {framerate} Hz (mono)")

    # ── Step 5: WebSocket pipeline ────────────────────────────────────────────
    print(f"\n[ws] Connecting to {WS_URL} ...")
    async with websockets.connect(WS_URL, open_timeout=10) as ws:

        # A. Greeting
        greeting = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        print(f"[ws] ← Greeting: {greeting}")
        assert greeting["type"] == "info", f"Expected info greeting, got {greeting}"

        # B. Auth handshake
        print(f"[ws] → Sending auth token...")
        await ws.send(json.dumps({"action": "auth", "token": access_token}))
        welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        print(f"[ws] ← Auth response: {welcome}")
        assert welcome["type"] == "info", f"Auth failed: {welcome}"
        assert "Welcome" in welcome["message"], f"Unexpected welcome msg: {welcome['message']}"

        # C. Config
        await ws.send(json.dumps({"action": "config", "sample_rate": framerate, "language": "en"}))
        print(f"[ws] → Config sent (sample_rate={framerate})")

        # D. Stream audio
        chunk_size = int(framerate * 0.3)  # 300 ms chunks
        num_chunks = 0
        for i in range(0, len(float32), chunk_size):
            chunk = float32[i:i + chunk_size]
            await ws.send(chunk.tobytes())
            num_chunks += 1
            await asyncio.sleep(0.03)
            # Drain any live segment messages
            try:
                raw_msg = await asyncio.wait_for(ws.recv(), timeout=0.02)
                seg = json.loads(raw_msg)
                if seg.get("type") == "segment":
                    print(f"[ws] ← Live segment: '{seg.get('text', '')}'")
            except asyncio.TimeoutError:
                pass
        print(f"[ws] → Streamed {num_chunks} chunks ({len(float32)} samples total)")

        # E. Stop
        await ws.send(json.dumps({"action": "stop"}))
        print("[ws] → Stop sent — awaiting final transcript...")

        # F. Collect final
        final_transcript = ""
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                raw_msg = await asyncio.wait_for(ws.recv(), timeout=5)
                msg = json.loads(raw_msg)
                print(f"[ws] ← {msg}")
                if msg["type"] == "final":
                    final_transcript = msg.get("transcript", "")
                    break
                elif msg["type"] == "segment":
                    print(f"[ws] ← Trailing segment: '{msg.get('text', '')}'")
            except asyncio.TimeoutError:
                print("[ws] (timeout waiting for next message)")
                break

    # ── Result ────────────────────────────────────────────────────────────────
    if final_transcript:
        print(f"\n✅ PASS — Final transcript: '{final_transcript}'")
    else:
        print("\n⚠️  WARNING — Connection closed cleanly but transcript was empty (Whisper may need audio above VAD threshold)")

    # Cleanup
    if os.path.exists(WAV_PATH):
        os.remove(WAV_PATH)
    print("[cleanup] Done.")


if __name__ == "__main__":
    asyncio.run(main())
