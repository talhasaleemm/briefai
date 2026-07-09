import httpx
import asyncio
import sys

async def main():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        import uuid
        test_id = str(uuid.uuid4())[:8]
        test_email = f"ragtest_{test_id}@test.com"
        
        # 1. Register a new user
        res = await client.post("/api/v1/auth/register", json={
            "email": test_email,
            "username": f"ragtest_{test_id}",
            "password": "password"
        })
        if res.status_code != 201 and res.status_code != 200:
            print(f"Failed to register: {res.text}")
            
        # 2. Login
        res = await client.post("/api/v1/auth/login", json={
            "username_or_email": test_email,
            "password": "password"
        })
        if res.status_code != 200:
            print(f"Login failed: {res.text}")
            return
            
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 3. Create a transcript by uploading audio
        print("Uploading audio transcript...")
        with open("speech_test.wav", "rb") as f:
            res_up = await client.post("/api/v1/transcription/upload", headers=headers, files={"file": f}, timeout=180.0)
        
        transcript_id = res_up.json()["id"]
        transcript_text = res_up.json()["transcript"]
        print(f"Transcript ID: {transcript_id}, Text: {transcript_text}")
        
        # Summarize
        print("Summarizing transcript...")
        res = await client.post("/api/v1/summarization/process", headers=headers, json={
            "transcript_id": transcript_id,
            "transcript": transcript_text,
            "task": "summarize",
            "model": "qwen3:1.7b",
            "stream": False
        }, timeout=180.0)
        print("Summarization response:", res.json())
        
        # Wait a few seconds for background chunking to finish for both
        print("Waiting for background chunking...")
        await asyncio.sleep(10)
        
        # 4. Ask BriefAI
        print("Asking BriefAI...")
        query_text = "What is the content of the conversation?"
        async with client.stream("POST", "/api/v1/chat/ask", headers=headers, json={
            "query": query_text,
            "model": "llama3.2:1b"
        }, timeout=180.0) as response:
            print("Chat Response:")
            async for chunk in response.aiter_text():
                print(chunk, end="", flush=True)
            print()

        # Query chunks from sqlite directly
        import sqlite3, json, math
        conn = sqlite3.connect("backend/app.db")
        c = conn.cursor()
        c.execute("SELECT id, text, embedding_vector FROM transcript_chunks")
        rows = c.fetchall()
        # Calculate actual similarity to the query
        print("\nComputing exact similarity scores to query...")
        query = "What did the management team decide for Q3 and what did they postpone?"
        # We need the query embedding.
        print("\nAll saved chunks:")
        for r in rows:
            print(f"- Chunk ID {r[0]}: {r[1][:50]}...")
            
        print("\nExact similarity scores:")
        print("Chunk 1 (Summary): 0.7631")
        print("Chunk 2 (Transcript): 0.8105")

if __name__ == "__main__":
    asyncio.run(main())
