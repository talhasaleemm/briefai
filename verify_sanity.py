import asyncio
import json
import uuid
import httpx

async def verify_sanity():
    print("--- Starting Sanity Pass ---")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=120.0) as client:
        # 1. Auth
        print("\n1. Login / Auth Flow")
        user_suffix = str(uuid.uuid4())[:8]
        username = f"test_{user_suffix}"
        res = await client.post("/api/v1/auth/register", json={
            "email": f"{username}@example.com",
            "username": username,
            "password": "password"
        })
        print(f"Register status: {res.status_code}")
        
        res = await client.post("/api/v1/auth/login", json={
            "username_or_email": username,
            "password": "password"
        })
        token = res.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        print("Auth success!")

        # 2. Upload Audio & Transcribe
        print("\n2 & 3. Upload & Transcription")
        with open("backend/speech_test.wav", "rb") as f:
            files = {"file": ("speech_test.wav", f, "audio/wav")}
            res = await client.post("/api/v1/transcription/upload", files=files)
        
        print(f"Upload status: {res.status_code}")
        transcript_data = res.json()
        transcript_id = transcript_data.get('id')
    
        res = await client.get(f"/api/v1/transcription/{transcript_id}")
        assert res.status_code == 200, f"Failed to fetch transcript: {res.text}"
        transcript_data = res.json()
            
        print(f"Transcript text: {transcript_data.get('content')[:100]}...")

        # 4. Summarization
        print("\n4. Summarization")
        summarize_payload = {
            "transcript": transcript_data.get('content'),
            "task": "summarize",
            "model": "qwen3:1.7b",
            "stream": False
        }
        res = await client.post("/api/v1/summarization/process", json=summarize_payload)
        print(f"Summarize status: {res.status_code}")
        print(f"Summary: {res.json().get('result')[:100]}...")

        # 5. Ask BriefAI (RAG)
        print("\n5. Ask BriefAI RAG")
        rag_payload = {
            "question": "What is this recording about?",
            "stream": False,
            "model": "qwen3:1.7b"
        }
        res = await client.post("/api/v1/chat/ask", json=rag_payload)
        print(f"RAG status: {res.status_code}")
        print(f"Answer: {res.json().get('answer')}")

if __name__ == "__main__":
    asyncio.run(verify_sanity())
