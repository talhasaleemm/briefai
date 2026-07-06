import React, { useState } from 'react';

interface BenchmarkRow {
  model: string;
  workload: string;
  status: string;
  ttft: number;
  latency: number;
  throughput: number;
  contextSpeed: number;
  rss: number;
  peak: number;
  quality: string;
}

const BENCHMARK_DATA: BenchmarkRow[] = [
  { model: 'qwen3:1.7b', workload: 'Small', status: 'Empty (Token Cap)', ttft: 14321.5, latency: 14.32, throughput: 11.7, contextSpeed: 1515.6, rss: 3428.3, peak: 3448.9, quality: 'N/A' },
  { model: 'llama3.2:1b', workload: 'Small', status: 'Success', ttft: 1603.5, latency: 10.63, throughput: 11.6, contextSpeed: 1556.8, rss: 3467.0, peak: 3467.0, quality: '5.0' },
  { model: 'qwen3:1.7b', workload: 'Medium', status: 'Empty (Token Cap)', ttft: 14851.9, latency: 14.85, throughput: 11.2, contextSpeed: 3983.2, rss: 3477.0, peak: 3477.0, quality: 'N/A' },
  { model: 'llama3.2:1b', workload: 'Medium', status: 'Success', ttft: 1657.1, latency: 15.49, throughput: 11.1, contextSpeed: 3649.1, rss: 3508.8, peak: 3508.8, quality: '4.5' },
  { model: 'qwen3:1.7b', workload: 'Large', status: 'Success', ttft: 29870.7, latency: 40.39, throughput: 9.0, contextSpeed: 7793.0, rss: 3584.7, peak: 3584.7, quality: '3.5' },
  { model: 'llama3.2:1b', workload: 'Large', status: 'Success', ttft: 1411.8, latency: 25.64, throughput: 10.2, contextSpeed: 8053.1, rss: 3492.6, peak: 3492.7, quality: '5.0' },
];

export const BenchmarkDashboard: React.FC = () => {
  const [selectedWorkload, setSelectedWorkload] = useState<string>('All');

  const filteredData = selectedWorkload === 'All' 
    ? BENCHMARK_DATA 
    : BENCHMARK_DATA.filter(row => row.workload === selectedWorkload);

  return (
    <div className="benchmark-dashboard">
      <div className="dashboard-header">
        <h2 className="dashboard-title">Local LLM Performance Profile</h2>
        <p className="dashboard-subtitle">
          Head-to-head metrics comparing performance on host CPUFallback hardware (3 trials averaged, with active memory polling).
        </p>
      </div>

      {/* Filter Tabs */}
      <div className="filter-tabs">
        {['All', 'Small', 'Medium', 'Large'].map(workload => (
          <button
            key={workload}
            onClick={() => setSelectedWorkload(workload)}
            className={`filter-tab-btn ${selectedWorkload === workload ? 'active' : ''}`}
          >
            {workload}
          </button>
        ))}
      </div>

      {/* Metrics Table */}
      <div className="table-container backdrop-blur">
        <table className="benchmark-table">
          <thead>
            <tr>
              <th>Model</th>
              <th>Workload</th>
              <th>Status</th>
              <th>TTFT</th>
              <th>Total Latency</th>
              <th>Throughput</th>
              <th>Context Ingest</th>
              <th>Peak RAM</th>
              <th>Quality</th>
            </tr>
          </thead>
          <tbody>
            {filteredData.map((row, idx) => {
              const isLlama = row.model.includes('llama');
              const isSuccess = row.status === 'Success';
              return (
                <tr key={idx} className={isLlama ? 'row-llama' : 'row-qwen'}>
                  <td className="model-cell"><code>{row.model}</code></td>
                  <td>{row.workload}</td>
                  <td>
                    <span className={`status-tag ${isSuccess ? 'success' : 'warn'}`}>
                      {row.status}
                    </span>
                  </td>
                  <td>{(row.ttft / 1000).toFixed(2)}s</td>
                  <td>{row.latency.toFixed(2)}s</td>
                  <td>{row.throughput.toFixed(1)} tok/s</td>
                  <td>{row.contextSpeed.toFixed(0)} tok/s</td>
                  <td>{(row.peak / 1024).toFixed(2)} GB</td>
                  <td>
                    {isSuccess ? (
                      <span className="badge-quality">{row.quality} / 5.0</span>
                    ) : (
                      <span className="badge-na">N/A</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Key Takeaways Section */}
      <div className="takeaways-section grid-2">
        <div className="takeaway-card backdrop-blur border-glow">
          <h3 className="takeaway-title text-gradient">💡 The Reasoning Token Budget Constraint</h3>
          <p className="takeaway-text">
            <strong>Qwen3-1.7B</strong> behaves as a distilled reasoning model, dedicating 150–200 tokens to internal 
            <code>&lt;thinking&gt;</code> before outputting its response. 
            Under token-capped workloads (Small and Medium workloads limited to 150 tokens), it exhausts the entire 
            budget in thinking, returning an empty text response.
          </p>
          <div className="takeaway-alert-box">
            <strong>Backend Safeguard Active:</strong> Our backend detects Qwen3 empty responses and automatically retries with 
            <code>num_predict=1024</code> or fails loudly.
          </div>
        </div>

        <div className="takeaway-card backdrop-blur border-glow">
          <h3 className="takeaway-title text-gradient">⚡ CPU Latency & Resource Findings</h3>
          <p className="takeaway-text">
            <strong>Llama 3.2-1B</strong> achieves an outstanding Time to First Token (TTFT) of <strong>~1.4s to 1.6s</strong>, 
            making it perfect for low-latency, real-time feedback paths. Qwen3 requires a warmup and reasoning phase 
            which inflates TTFT to <strong>14s+</strong> on CPU.
          </p>
          <p className="takeaway-text" style={{ marginTop: '1rem' }}>
            <strong>Continuous RAM Footprint:</strong> Using our 100ms background polling task, we measured a stable combined 
            active memory usage of **~3.4 to 3.5 GB RAM** when both models are loaded concurrently by Ollama.
          </p>
        </div>
      </div>
    </div>
  );
};
