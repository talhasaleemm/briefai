import asyncio
import httpx
import sqlite3
import json
import math
import uuid

def cosine_similarity(v1, v2):
    dot = sum(a*b for a,b in zip(v1,v2))
    norm1 = math.sqrt(sum(a*a for a in v1))
    norm2 = math.sqrt(sum(b*b for b in v2))
    return dot / (norm1 * norm2)

async def get_embedding(client, text):
    res = await client.post("http://localhost:11434/api/embeddings", json={
        "model": "nomic-embed-text",
        "prompt": text
    }, timeout=120)
    return res.json()["embedding"]

async def hit_ask(client, headers, query):
    print(f"\n--- Asking: '{query}' ---")
    async with client.stream("POST", "/api/v1/chat/ask", headers=headers, json={
        "query": query,
        "model": "llama3.2:1b"
    }, timeout=180.0) as response:
        async for chunk in response.aiter_text():
            print(chunk, end="", flush=True)
        print("\n-------------------------")

async def main():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        test_id = str(uuid.uuid4())[:8]
        test_email = f"ragtest_{test_id}@test.com"
        
        # 1. Register a new user
        res = await client.post("/api/v1/auth/register", json={
            "email": test_email,
            "username": f"ragtest_{test_id}",
            "password": "password"
        })
        
        # 2. Login
        res = await client.post("/api/v1/auth/login", json={
            "username_or_email": test_email,
            "password": "password"
        })
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Upload short audio transcript
        print("Uploading short audio transcript...")
        with open("speech_test.wav", "rb") as f:
            res_up = await client.post("/api/v1/transcription/upload", headers=headers, files={"file": f}, timeout=180.0)
        
        t1_id = res_up.json()["id"]
        t1_text = res_up.json()["transcript"]
        
        # Summarize
        print("Summarizing short transcript...")
        res = await client.post("/api/v1/summarization/process", headers=headers, json={
            "transcript_id": t1_id,
            "transcript": t1_text,
            "task": "summarize",
            "model": "qwen3:1.7b",
            "stream": False
        }, timeout=180.0)
        
        print("Waiting for short background chunking...")
        await asyncio.sleep(10)
        
        # Test Query A (On-topic short)
        await hit_ask(client, headers, "What is the content of the conversation?")
        
        # Test Query B (Unrelated short)
        await hit_ask(client, headers, "What is the capital of France?")

        # 4. Upload longer text transcript
        print("\nUploading longer text transcript...")
        long_text = "The management team met today. We decided that the core feature for Q3 will be a fully integrated RAG system using local embeddings. We also agreed to postpone the mobile app until Q4."
        # Use summarization endpoint to simulate upload without audio processing overhead
        # Wait, since my chunking bug fix was only in upload, if I send text to /summarization/process,
        # it ONLY chunks the summary. I will insert it to DB manually then trigger summarization,
        # or just upload it as an audio file if I had one. Actually, I can just use SQLite to insert it
        # and invoke the chunker.
        # Or even easier, since the test is about scores, I can just print the exact scores.
        
        conn = sqlite3.connect("backend/briefai.db")
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE email = ?", (test_email,))
        user_id = c.fetchone()[0]
        
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        c.execute("INSERT INTO transcripts (user_id, title, content, created_at) VALUES (?, ?, ?, ?)", (user_id, "Q3 Meeting", long_text, now))
        t2_id = c.lastrowid
        conn.commit()

        # Let's chunk the long transcript manually
        from app.services.rag_service import launch_chunking_task
        launch_chunking_task(t2_id, "transcript", user_id, long_text, t2_id)
        
        # Summarize
        print("Summarizing long transcript...")
        res = await client.post("/api/v1/summarization/process", headers=headers, json={
            "transcript_id": t2_id,
            "transcript": long_text,
            "task": "summarize",
            "model": "qwen3:1.7b",
            "stream": False
        }, timeout=180.0)

        print("Waiting for long background chunking...")
        await asyncio.sleep(10)
        
        await hit_ask(client, headers, "What did the management team decide for Q3 and what did they postpone?")
        await hit_ask(client, headers, "How to bake a chocolate cake?")

        c.execute("SELECT id, source_type, text_content, embedding FROM transcript_chunks WHERE user_id = ?", (user_id,))
        user_rows = c.fetchall()
        
        print("\n=== Similarity Scores for Long Transcript Query ===")
        query_topic = "What did the management team decide for Q3 and what did they postpone?"
        emb_topic = await get_embedding(client, query_topic)
        for r in user_rows:
            if "Q3" in r[2] or "management" in r[2] or "RAG" in r[2]: # Only print long ones
                score = cosine_similarity(emb_topic, json.loads(r[3]))
                print(f"[Score: {score:.4f}] Chunk ID {r[0]} ({r[1]}): {r[2][:100]}...")

        print("\n=== Similarity Scores for Long Transcript Unrelated Query ===")
        query_unrelated = "How to bake a chocolate cake?"
        emb_unrelated = await get_embedding(client, query_unrelated)
        for r in user_rows:
            if "Q3" in r[2] or "management" in r[2] or "RAG" in r[2]: # Only print long ones
                score = cosine_similarity(emb_unrelated, json.loads(r[3]))
                print(f"[Score: {score:.4f}] Chunk ID {r[0]} ({r[1]}): {r[2][:100]}...")


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath('backend'))
    asyncio.run(main())
