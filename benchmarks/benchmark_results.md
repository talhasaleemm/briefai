# Benchmark Results — Head-to-Head Comparison

| Model | Workload | Status | TTFT (ms) | Latency (s) | Throughput (tok/s) | Context Speed (tok/s) | Memory RSS (MB) | Peak RAM (MB) | Quality (1-5) |
|---|---|---|---|---|---|---|---|---|---|
| `qwen3:1.7b` | Small | Empty (Token Cap) | 14321.5 | 14.32 | 11.7 | 1515.6 | 3428.3 | 3448.9 | N/A |
| `llama3.2:1b` | Small | Success | 1603.5 | 10.63 | 11.6 | 1556.8 | 3467.0 | 3467.0 | *TBD (Blind Review)* |
| `qwen3:1.7b` | Medium | Empty (Token Cap) | 14851.9 | 14.85 | 11.2 | 3983.2 | 3477.0 | 3477.0 | N/A |
| `llama3.2:1b` | Medium | Success | 1657.1 | 15.49 | 11.1 | 3649.1 | 3508.8 | 3508.8 | *TBD (Blind Review)* |
| `qwen3:1.7b` | Large | Success | 29870.7 | 40.39 | 9.0 | 7793.0 | 3584.7 | 3584.7 | *TBD (Blind Review)* |
| `llama3.2:1b` | Large | Success | 1411.8 | 25.64 | 10.2 | 8053.1 | 3492.6 | 3492.7 | *TBD (Blind Review)* |
