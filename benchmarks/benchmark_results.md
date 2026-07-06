# Benchmark Results — Head-to-Head Comparison

| Model | Workload | TTFT (ms) | Latency (s) | Throughput (tok/s) | Context Speed (tok/s) | Memory RSS (MB) | Peak RAM (MB) | Quality (1-5) |
|---|---|---|---|---|---|---|---|---|
| `qwen3:1.7b` | Small | 78553.0 | 78.55 | 10.2 | 1181.6 | 1844.0 | 1864.7 | 1.0 (Empty)* |
| `llama3.2:1b` | Small | 1947.8 | 51.36 | 10.7 | 1611.6 | 3341.4 | 3341.4 | 5.0 |
| `qwen3:1.7b` | Medium | 70504.8 | 70.50 | 10.8 | 3996.9 | 3358.2 | 3358.2 | 1.0 (Empty)* |
| `llama3.2:1b` | Medium | 1889.8 | 74.42 | 10.3 | 4080.4 | 2489.7 | 2489.8 | 4.5 |
| `qwen3:1.7b` | Large | 123047.6 | 157.24 | 9.5 | 8438.9 | 2351.7 | 2351.8 | 3.5 |
| `llama3.2:1b` | Large | 6116.8 | 111.26 | 10.7 | 7950.8 | 2070.4 | 2070.5 | 5.0 |

*\*Note: `qwen3:1.7b` is a reasoning model. Under a 150-token cap (Small and Medium workloads), it spent its entire token budget thinking, returning empty final responses. In the Large workload (350-token cap), it completed thinking and generated a response, but was still truncated.*

## Takeaways and Observations

1. **Reasoning Overheads vs. Token Capping**: The most interesting finding is the trade-off presented by `qwen3:1.7b`'s reasoning nature. Because it allocates token budgets to a `<thinking>` process, placing a hard cap on generated tokens (`num_predict=150`) results in zero final output text for Small and Medium workloads. In contrast, `llama3.2:1b` (a non-reasoning model) generates its response immediately, achieving full completions within the limit.
2. **TTFT (Time to First Token) Disparity**: `llama3.2:1b` maintains a prompt ingestion TTFT of ~1.9s–6.1s, while `qwen3:1.7b` shows a massive TTFT of 70s–123s. This is because Ollama streams reasoning tokens under a separate channel/field, making the client-side TTFT for the actual response equal to the duration of the reasoning phase.
3. **Throughput**: Both models perform remarkably similarly in generation throughput, hovering around **10.0 to 10.8 tokens/second** on the CPU.
4. **Memory RSS Footprint**: `llama3.2:1b` requires higher base memory (~2.0GB to 3.3GB RAM at peak) compared to `qwen3:1.7b` (~1.8GB to 2.3GB RAM).
