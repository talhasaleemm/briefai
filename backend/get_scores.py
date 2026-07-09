import asyncio
import httpx
import sqlite3
import json
import math

async def get_embedding(text):
    async with httpx.AsyncClient() as client:
        res = await client.post("http://localhost:11434/api/embeddings", json={
            "model": "nomic-embed-text",
            "prompt": text
        })
        return res.json()["embedding"]

def cosine_similarity(v1, v2):
    dot = sum(a*b for a,b in zip(v1,v2))
    norm1 = math.sqrt(sum(a*a for a in v1))
    norm2 = math.sqrt(sum(b*b for b in v2))
    return dot / (norm1 * norm2)

async def main():
    query = "What did the management team decide for Q3 and what did they postpone?"
    print(f"Query: {query}")
    query_emb = await get_embedding(query)
    
    conn = sqlite3.connect("briefai.db")
    c = conn.cursor()
    c.execute("SELECT id, text_content, embedding FROM transcript_chunks")
    rows = c.fetchall()
    
    print("\nReal retrieved chunks and scores:")
    for r in rows:
        chunk_text = r[1]
        chunk_emb = json.loads(r[2])
        score = cosine_similarity(query_emb, chunk_emb)
        print(f"[{score:.4f}] {chunk_text}")

if __name__ == "__main__":
    asyncio.run(main())
