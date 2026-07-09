import asyncio
import httpx
import sqlite3
import json
import math

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

async def main():
    async with httpx.AsyncClient() as client:
        # 1. Check all chunks in DB
        conn = sqlite3.connect("briefai.db")
        c = conn.cursor()
        c.execute("SELECT id, source_type, text_content, embedding FROM transcript_chunks")
        rows = c.fetchall()
        print(f"Total chunks in DB: {len(rows)}")
        
        # 2. Get the specific test user and their chunks to isolate it like the API does
        # Let's just find the chunks belonging to the last user inserted in the previous run.
        c.execute("SELECT id FROM users ORDER BY created_at DESC LIMIT 1")
        user_id = c.fetchone()[0]
        c.execute("SELECT id, source_type, text_content, embedding FROM transcript_chunks WHERE user_id = ?", (user_id,))
        user_rows = c.fetchall()
        print(f"Total chunks for test user {user_id}: {len(user_rows)}")
        
        for r in user_rows:
            print(f"  - Chunk ID {r[0]} | Type: {r[1]} | Length: {len(r[2])} | Preview: {r[2][:50]}...")
            
        print("\n=== Similarity Scores for On-Topic Query ===")
        query_topic = "What is the content of the conversation?"
        emb_topic = await get_embedding(client, query_topic)
        for r in user_rows:
            score = cosine_similarity(emb_topic, json.loads(r[3]))
            print(f"[Score: {score:.4f}] Chunk ID {r[0]} ({r[1]}): {r[2][:100]}...")
            
        print("\n=== Similarity Scores for Unrelated Query ===")
        query_unrelated = "What is the capital of France?"
        emb_unrelated = await get_embedding(client, query_unrelated)
        for r in user_rows:
            score = cosine_similarity(emb_unrelated, json.loads(r[3]))
            print(f"[Score: {score:.4f}] Chunk ID {r[0]} ({r[1]}): {r[2][:100]}...")

        # 3. Hit the API to prove the unrelated query triggers grounding guard
        # Login to get token for user_id
        c.execute("SELECT email FROM users WHERE id = ?", (user_id,))
        email = c.fetchone()[0]
        
        res = await client.post("http://127.0.0.1:8000/api/v1/auth/login", json={
            "username_or_email": email,
            "password": "password"
        })
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        print("\n=== API Chat Response for Unrelated Query ===")
        async with client.stream("POST", "http://127.0.0.1:8000/api/v1/chat/ask", headers=headers, json={
            "query": query_unrelated,
            "model": "llama3.2:1b"
        }, timeout=120.0) as response:
            async for chunk in response.aiter_text():
                print(chunk, end="", flush=True)
            print()

if __name__ == "__main__":
    asyncio.run(main())
