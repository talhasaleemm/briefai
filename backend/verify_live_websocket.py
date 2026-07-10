import asyncio
import json
import subprocess
import time
import websockets
import os
import wave
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from briefai.utils.security import create_access_token
from briefai.models import Base, User

# Database and test config
DB_PATH = "./live_test_briefai.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"
WAV_PATH = "./speech_test.wav"

def generate_speech_wav(out_path: str, text: str) -> bool:
    """Synthesize real speech text to a WAV file using Windows SAPI (System.Speech)."""
    ps_script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile('{out_path.replace(chr(92), '/')}')
$synth.Rate = -1
$synth.Volume = 100
$synth.Speak("{text}")
$synth.Dispose()
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0 and os.path.exists(out_path) and os.stat(out_path).st_size > 1000

async def run_live_test():
    # 1. Clean up stale test database and WAV if exists
    for path in [DB_PATH, WAV_PATH]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    # 2. Synthesize speech text using Windows SAPI
    text_to_speak = "Welcome to the Brief AI WebSocket pipeline verification test."
    print(f"[sapi] Synthesizing speech text: '{text_to_speak}'...")
    sapi_ok = generate_speech_wav(WAV_PATH, text_to_speak)
    assert sapi_ok, "SAPI speech synthesis failed."
    print(f"[sapi] WAV generated successfully: {os.path.getsize(WAV_PATH)} bytes.")

    # 3. Read WAV and decode PCM to float32 mono PCM
    with wave.open(WAV_PATH, "rb") as wf:
        nchannels, sampwidth, framerate, nframes = wf.getparams()[:4]
        assert sampwidth == 2, "Expected 16-bit PCM WAV"
        raw_bytes = wf.readframes(nframes)
        # Convert int16 frames to numpy array
        int16_samples = np.frombuffer(raw_bytes, dtype=np.int16)
        # Normalize to float32 [-1.0, 1.0]
        float32_samples = int16_samples.astype(np.float32) / 32768.0
        
        # If stereo, take the first channel
        if nchannels > 1:
            float32_samples = float32_samples[::nchannels]
            
    print(f"[audio] Decoded {len(float32_samples)} float32 PCM samples at {framerate}Hz mono.")

    # 4. Setup database schema and insert a test user
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    test_user = User(
        email="liveuser@test.com",
        username="liveuser",
        hashed_password="mockhashedpassword"
    )
    db.add(test_user)
    db.commit()
    db.refresh(test_user)
    user_id = test_user.id
    db.close()
    
    token = create_access_token(user_id)
    print(f"[setup] Generated JWT Access Token: {token[:40]}...")

    # 5. Start the real uvicorn server in a background process
    env = os.environ.copy()
    env["DATABASE_URL"] = DATABASE_URL
    
    server_process = subprocess.Popen(
        [
            "C:\\Users\\talha\\.gemini\\antigravity-ide\\scratch\\briefai\\venv\\Scripts\\python.exe",
            "-m",
            "uvicorn",
            "app.main:app",
            "--host", "127.0.0.1",
            "--port", "8001",
            "--log-level", "warning" # Quiet log to keep output clean
        ],
        cwd="C:\\Users\\talha\\.gemini\\antigravity-ide\\scratch\\briefai\\backend",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    print("[server] Starting uvicorn server on port 8001...")
    time.sleep(3)
    
    uri = "ws://127.0.0.1:8001/api/v1/transcription/stream"
    try:
        async with websockets.connect(uri) as websocket:
            # Step A: Receive connection greeting
            greeting = json.loads(await websocket.recv())
            print(f"[client] Received Connection Greeting: {greeting}")
            assert greeting["type"] == "info"
            
            # Step B: Send JWT auth token
            print(f"[client] Sending Auth Payload...")
            await websocket.send(json.dumps({"action": "auth", "token": token}))
            
            # Step C: Receive welcome response
            welcome = json.loads(await websocket.recv())
            print(f"[client] Received Welcome Response: {welcome}")
            assert welcome["type"] == "info"
            assert "Welcome liveuser" in welcome["message"]
            
            # Step D: Send audio config
            config_payload = {"action": "config", "sample_rate": framerate, "language": "en"}
            print(f"[client] Sending Config Payload: {config_payload}")
            await websocket.send(json.dumps(config_payload))
            
            # Step E: Stream the audio PCM float32 bytes in real-time chunks
            # Send chunks of 4800 samples (300ms at 16kHz)
            chunk_size = int(framerate * 0.3)
            print("[client] Streaming PCM audio chunks to server...")
            
            for i in range(0, len(float32_samples), chunk_size):
                chunk = float32_samples[i:i+chunk_size]
                # Send raw bytes of float32 array
                await websocket.send(chunk.tobytes())
                await asyncio.sleep(0.05) # Mimic stream delay
                
                # Consume any incremental transcription segments if sent
                try:
                    # Non-blocking wait for segment text
                    msg_raw = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                    msg = json.loads(msg_raw)
                    if msg["type"] == "segment":
                        print(f"[client-live] Segment: {msg['text']}")
                except asyncio.TimeoutError:
                    pass
            
            # Step F: Send stop payload
            print("[client] Sending Stop Payload...")
            await websocket.send(json.dumps({"action": "stop"}))
            
            # Step G: Await final consolidated transcript and any trailing segments
            while True:
                msg_raw = await websocket.recv()
                msg = json.loads(msg_raw)
                print(f"[client] Received Response: {msg}")
                if msg["type"] == "final":
                    print(f"[success] E2E Transcription: '{msg['transcript']}'")
                    break
                elif msg["type"] == "segment":
                    print(f"[client-live-trailing] Segment: {msg['text']}")
            
    except Exception as e:
        print(f"[error] Test failed: {e}")
        raise e
    finally:
        print("[server] Shutting down uvicorn server...")
        server_process.terminate()
        server_process.wait()
        
        # Clean up database and audio files
        for path in [DB_PATH, WAV_PATH]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        print("[cleanup] Test resources cleaned up.")

if __name__ == "__main__":
    asyncio.run(run_live_test())
