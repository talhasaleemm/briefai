"""
Stage 5 Benchmarking Module — head-to-head performance profile of Qwen3-1.7B vs Llama3.2-1B.
Measures TTFT, Total Latency, Throughput, and RSS Memory.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
import psutil

# Add backend to python path
repo_root = Path(__file__).resolve().parent.parent
backend_path = repo_root / "backend"
if str(backend_path) not in sys.path:
    sys.path.append(str(backend_path))

import httpx

# ── Workloads ──────────────────────────────────────────────────────────────────

WORKLOADS = {
    "Small": (
        "Welcome to the Brief AI Integration Test. Today we will review the transcription "
        "pipeline and verify that faster-whisper returns accurate results. Action item one: "
        "confirm the API is working. Action item two: proceed to the next stage."
    ),
    "Medium": (
        "Project Standup Meeting Transcript:\n"
        "Manager: \"Okay everyone, let's start the standup. Sarah, how is the frontend work going?\"\n"
        "Sarah: \"I've completed the login screen styling and connected the authentication routes. "
        "The token is stored correctly in local storage. Currently, I'm working on the main dashboard layout. "
        "I expect to finish the responsive layout design by tomorrow afternoon, but I need the finalized "
        "API endpoints from the backend team to wire in the actual data.\"\n"
        "Alex: \"Backend is almost ready. The database schemas are set up and migrated. I implemented the "
        "WebSocket connection for real-time updates yesterday. I still need to finish the post-processing route "
        "for the transcription data, which is what we're working on today. I'll make sure the API docs are "
        "updated and shared with you by tonight so you can start styling the UI components tomorrow.\"\n"
        "Sarah: \"Great, that works perfectly. I will pull the database changes and start matching the layout fields.\"\n"
        "Manager: \"Excellent. Let's make sure we have a clear documentation page for the WebSocket API parameters. "
        "Alex, can you add a section on WebSocket error codes in the README?\"\n"
        "Alex: \"Yes, I will add that to my task list for tonight.\"\n"
        "Manager: \"Good. That covers our immediate priorities. Let's touch base again tomorrow morning.\""
    ),
    "Large": (
        "Strategic Product & Architecture Alignment Meeting Transcript:\n"
        "Director: \"Good morning, team. Today we are reviewing the core roadmap for the BriefAI platform "
        "and resolving our architectural scale challenges. We need to finalize our database migration "
        "strategy, address transcription latency bottlenecks, and outline our deployment model. Let's start "
        "with database scaling. Alex, what is the plan?\"\n"
        "Alex: \"Currently, we are running PostgreSQL locally. As user count grows, we'll hit connections "
        "and read bottlenecks. I propose migrating our read-heavy tables to Redis for caching, specifically "
        "for storing hot session tokens and active WebSocket channels. For the historical transcript records, "
        "we should implement a Partition-by-Month strategy in PostgreSQL to prevent query speeds from degrading "
        "over millions of rows. If we do this, we can maintain sub-10ms response times for active queries.\"\n"
        "Director: \"Sounds logical. Sarah, how does this impact the frontend state management?\"\n"
        "Sarah: \"As long as the API payload schema remains consistent, it won't impact us directly. However, "
        "with caching in place, we must ensure cache invalidation happens immediately when a user edits a transcript. "
        "I'll write an event listener in the React state manager to trigger re-fetches upon receiving edit "
        "confirmations over the WebSocket channel. By doing this, we keep the UI synchronized in real time.\"\n"
        "Director: \"Perfect. Make sure that cache eviction event is covered in our architecture document. "
        "Next topic: transcription pipeline latencies. Sarah mentioned some frame drops during peak streaming. "
        "Alex, is this a CPU bottleneck?\"\n"
        "Alex: \"Yes, on CPU-only machines, running faster-whisper tiny model while managing multiple active "
        "WebSocket connections causes occasional audio chunk drops. The problem is that the transcription service "
        "blocks the main async event loop. To resolve this, I recommend offloading transcription processing to a "
        "separate worker pool using multiprocessing. ProcessPoolExecutor will let us utilize other CPU cores "
        "without blocking FastAPI's ASGI event loop. We should also force client-side audio resampling to 16kHz "
        "to save CPU cycles in the backend.\"\n"
        "Director: \"Let's proceed with that. Moving the transcription inference off the main async loop is a priority. "
        "Alex, set up the worker pool structure by Wednesday. Sarah, verify if client-side audio resampling reduces "
        "our latency footprint on the frontend.\"\n"
        "Sarah: \"I've already tested it locally. Resampling using Web Audio API on the client browser reduces "
        "the backend CPU processing time by about 12% per incoming audio packet. I will commit the resampling "
        "worker script to the frontend repository today.\"\n"
        "Director: \"Great progress. Finally, deployment. Are we deploying bare-metal or using Docker?\"\n"
        "Alex: \"For bare-metal, it's easier to leverage host GPU bindings, but setup is brittle. I recommend "
        "building a Docker setup using the official Nvidia CUDA container base. That way, we package the ffmpeg "
        "and CUDA libraries, making GPU acceleration plug-and-play across our staging and production servers. "
        "I will write the Dockerfile and docker-compose configurations by Friday.\"\n"
        "Director: \"Excellent. Let's summarize the key decisions. First, cache read-heavy session metadata in "
        "Redis and partition PostgreSQL historical tables. Second, isolate Whisper inference in a backend worker pool "
        "using ProcessPoolExecutor and resample audio on the client. Third, package the stack using Docker with GPU "
        "support. This covers the strategy. Let's meet tomorrow to review the implementation progress.\""
    )
}

# ── Memory Tracker ─────────────────────────────────────────────────────────────

def get_llm_memory_mb() -> float:
    """Read Resident Set Size (RSS) memory of all llama-server processes in MB."""
    total_rss = 0.0
    for p in psutil.process_iter(['name', 'memory_info']):
        try:
            if p.info['name'] and 'llama-server' in p.info['name'].lower():
                total_rss += p.info['memory_info'].rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return total_rss / (1024 * 1024)

# ── Async Benchmark Runner ─────────────────────────────────────────────────────

async def run_inference_trial(
    client: httpx.AsyncClient,
    model: str,
    prompt: str,
    system_prompt: str,
    max_tokens: int
) -> dict:
    """Run a single streaming inference request and measure performance metrics."""
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": True,
        "options": {
            "temperature": 0.0,
            "num_predict": max_tokens,  # Token limit to control duration
        }
    }
    
    t_start = time.perf_counter()
    t_first = None
    t_end = None
    
    output_text_parts = []
    
    # Track base memory before start
    mem_base = get_llm_memory_mb()
    mem_peak = mem_base
    
    # Set up background memory polling task to capture true peak memory
    done_event = asyncio.Event()
    
    async def poll_memory():
        nonlocal mem_peak
        while not done_event.is_set():
            try:
                current_mem = get_llm_memory_mb()
                if current_mem > mem_peak:
                    mem_peak = current_mem
            except Exception:
                pass
            await asyncio.sleep(0.1)
            
    polling_task = asyncio.create_task(poll_memory())
    
    try:
        async with client.stream("POST", url, json=payload, timeout=120.0) as response:
            response.raise_for_status()
            
            # Read the stream
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                
                data = json.loads(line)
                chunk_text = data.get("response", "")
                output_text_parts.append(chunk_text)
                
                # Capture Time to First Token (TTFT)
                if t_first is None and chunk_text.strip():
                    t_first = time.perf_counter()
                    
                # If done, record metrics
                if data.get("done", False):
                    t_end = time.perf_counter()
                    eval_count = data.get("eval_count", 0)  # output tokens
                    prompt_eval_count = data.get("prompt_eval_count", 0)  # input tokens
                    prompt_eval_time_ns = data.get("prompt_eval_duration", 0)
                    eval_time_ns = data.get("eval_duration", 0)
    finally:
        # Guarantee memory poller shuts down
        done_event.set()
        await polling_task
        
    t_end = t_end or time.perf_counter()
    t_first = t_first or t_end
    
    total_latency = t_end - t_start
    ttft_ms = (t_first - t_start) * 1000.0
    
    generated_text = "".join(output_text_parts).strip()
    
    # Calculate throughput using model reported token counts and latency
    # Ollama returns durations in nanoseconds
    gen_time_s = eval_time_ns / 1e9 if eval_time_ns > 0 else (t_end - t_first)
    throughput = eval_count / gen_time_s if gen_time_s > 0 else 0.0
    
    prompt_time_s = prompt_eval_time_ns / 1e9 if prompt_eval_time_ns > 0 else (t_first - t_start)
    prompt_speed = prompt_eval_count / prompt_time_s if prompt_time_s > 0 else 0.0
    
    return {
        "text": generated_text,
        "ttft_ms": ttft_ms,
        "total_latency_s": total_latency,
        "throughput": throughput,
        "prompt_speed": prompt_speed,
        "input_tokens": prompt_eval_count,
        "output_tokens": eval_count,
        "mem_base_mb": mem_base,
        "mem_peak_mb": mem_peak
    }

async def benchmark_configuration(
    model: str,
    workload_name: str,
    transcript: str,
    max_tokens: int,
    trials: int = 3
) -> dict:
    """Run multiple trials and average the results."""
    print(f"Profiling {model} on {workload_name} workload (max_tokens={max_tokens})...")
    
    system_prompt = (
        "You are an expert meeting assistant. Provide a structured summary of the meeting "
        "transcript in clean Markdown detailing the main topics, action items, and takeaways."
    )
    
    # Simple prompt template for head-to-head evaluation
    prompt = (
        "Meeting Transcript:\n"
        "\"\"\"\n"
        f"{transcript}\n"
        "\"\"\"\n\n"
        "Please provide a concise summary of the meeting transcript above in clean Markdown using the following structure:\n"
        "### 1. Executive Summary\n"
        "### 2. Key Themes\n"
        "### 3. Action Items"
    )
    
    # Warmup run to load model into memory and stabilize caches
    async with httpx.AsyncClient() as client:
        await run_inference_trial(client, model, prompt, system_prompt, max_tokens)
        
        # Run trials
        runs = []
        for i in range(1, trials + 1):
            print(f"  - Trial {i}/{trials}...")
            trial_data = await run_inference_trial(client, model, prompt, system_prompt, max_tokens)
            runs.append(trial_data)
            await asyncio.sleep(1.0)
            
    # Aggregate stats
    avg_ttft = sum(r["ttft_ms"] for r in runs) / trials
    avg_latency = sum(r["total_latency_s"] for r in runs) / trials
    avg_throughput = sum(r["throughput"] for r in runs) / trials
    avg_prompt_speed = sum(r["prompt_speed"] for r in runs) / trials
    avg_mem_base = sum(r["mem_base_mb"] for r in runs) / trials
    avg_mem_peak = sum(r["mem_peak_mb"] for r in runs) / trials
    
    # Save the sample text from the last trial for blind quality scoring
    sample_text = runs[-1]["text"]
    
    # Determine execution status based on text output presence
    status = "Success" if sample_text.strip() else "Empty (Token Cap)"
    
    return {
        "model": model,
        "workload": workload_name,
        "status": status,
        "ttft_ms": avg_ttft,
        "latency_s": avg_latency,
        "throughput": avg_throughput,
        "prompt_speed": avg_prompt_speed,
        "mem_base_mb": avg_mem_base,
        "mem_peak_mb": avg_mem_peak,
        "sample_text": sample_text,
    }

# ── Main Runner ────────────────────────────────────────────────────────────────

async def main():
    print("=== BRIEF AI BENCHMARKING ENGINE ===")
    
    models = ["qwen3:1.7b", "llama3.2:1b"]
    
    results = []
    text_samples = []  # Store for randomized blind review
    
    # Map max token limits by workload size (150 for A/B, 350 for C to prevent mid-thought cuts)
    workload_tokens = {
        "Small": 150,
        "Medium": 150,
        "Large": 350
    }
    
    sample_id = 1
    
    for w_name, transcript in WORKLOADS.items():
        print(f"\n==================== WORKLOAD: {w_name} ====================")
        max_tokens = workload_tokens[w_name]
        
        for model in models:
            res = await benchmark_configuration(model, w_name, transcript, max_tokens, trials=3)
            results.append(res)
            
            # Anonymize text sample for blind quality review
            text_samples.append({
                "sample_id": sample_id,
                "workload": w_name,
                "model": model,  # Hidden from preview
                "text": res["sample_text"]
            })
            # Remove text from metrics results to avoid leakage before scoring
            res.pop("sample_text")
            sample_id += 1
            
    # Write metrics to CSV/JSON or construct the Markdown baseline table
    print("\n=== Benchmarks completed! ===")
    print("Generating raw benchmark metrics file...")
    
    # Shuffle samples to ensure blind review
    import random
    random.seed(42)  # Stable shuffle
    blind_samples = list(text_samples)
    random.shuffle(blind_samples)
    
    # Output metrics to json
    results_file = repo_root / "benchmarks" / "metrics_data.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Metrics saved to: {results_file}")
    
    # Save the shuffled text file for quality scoring
    blind_file = repo_root / "benchmarks" / "blind_samples.txt"
    with open(blind_file, "w", encoding="utf-8") as f:
        f.write("=== BLIND QUALITY REVIEW SAMPLES ===\n")
        f.write("Evaluate each sample out of 5 based on: coherence, accuracy, and formatting.\n")
        f.write("Do not look at the answer mapping file until you have assigned a rating!\n\n")
        for s in blind_samples:
            f.write(f"--------------------------------------------------------------------------------\n")
            f.write(f"Sample ID: {s['sample_id']} | Workload: {s['workload']}\n")
            f.write(f"--------------------------------------------------------------------------------\n")
            f.write(f"{s['text']}\n\n")
            
    # Save key mapping file privately for reference
    map_file = repo_root / "benchmarks" / "blind_map.json"
    with open(map_file, "w") as f:
        json.dump(blind_samples, f, indent=2)
        
    print(f"Blind review text file saved to: {blind_file}")
    print(f"Mapping keys saved to: {map_file}")
    
    # Generate the baseline Markdown table
    md_table = (
        "# Benchmark Results — Head-to-Head Comparison\n\n"
        "| Model | Workload | Status | TTFT (ms) | Latency (s) | Throughput (tok/s) | Context Speed (tok/s) | Memory RSS (MB) | Peak RAM (MB) | Quality (1-5) |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
    )
    for r in results:
        quality_str = "*TBD (Blind Review)*" if r["status"] == "Success" else "N/A"
        md_table += (
            f"| `{r['model']}` | {r['workload']} | {r['status']} | {r['ttft_ms']:.1f} | {r['latency_s']:.2f} | "
            f"{r['throughput']:.1f} | {r['prompt_speed']:.1f} | {r['mem_base_mb']:.1f} | "
            f"{r['mem_peak_mb']:.1f} | {quality_str} |\n"
        )
        
    md_file = repo_root / "benchmarks" / "benchmark_results.md"
    with open(md_file, "w") as f:
        f.write(md_table)
    print(f"Baseline results markdown saved to: {md_file}")

if __name__ == "__main__":
    asyncio.run(main())
