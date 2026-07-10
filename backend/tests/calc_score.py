import asyncio
import httpx
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
        long_text = "The management team met today. We decided that the core feature for Q3 will be a fully integrated RAG system using local embeddings. We also agreed to postpone the mobile app until Q4."
        long_emb = await get_embedding(client, long_text)
        
        q1 = "What did the management team decide for Q3 and what did they postpone?"
        q1_emb = await get_embedding(client, q1)
        
        q2 = "How to bake a chocolate cake?"
        q2_emb = await get_embedding(client, q2)
        
        print(f"Q1 (On-topic) vs Long Transcript: {cosine_similarity(q1_emb, long_emb):.4f}")
        print(f"Q2 (Unrelated) vs Long Transcript: {cosine_similarity(q2_emb, long_emb):.4f}")

if __name__ == "__main__":
    asyncio.run(main())
