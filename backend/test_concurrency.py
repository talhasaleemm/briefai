import asyncio
import time
from app.services.ollama_service import OllamaService

async def main():
    svc = OllamaService()
    print("Testing concurrency limit (Semaphore=1)...")
    
    start = time.perf_counter()
    
    async def task_gen():
        print(f"[{time.perf_counter()-start:.2f}s] Queuing GENERATE task...")
        # Since it's Ollama, it will block on httpx. 
        await svc.generate("qwen3:1.7b", "Tell me a short story.", options={"num_predict": 10})
        print(f"[{time.perf_counter()-start:.2f}s] GENERATE task completed.")
        
    async def task_embed():
        print(f"[{time.perf_counter()-start:.2f}s] Queuing EMBED task...")
        # Give generate task a tiny headstart to get the lock first
        await asyncio.sleep(0.5) 
        print(f"[{time.perf_counter()-start:.2f}s] EMBED task requesting lock...")
        await svc.embed("nomic-embed-text", "Hello world")
        print(f"[{time.perf_counter()-start:.2f}s] EMBED task completed.")

    await asyncio.gather(task_gen(), task_embed())

if __name__ == "__main__":
    asyncio.run(main())
