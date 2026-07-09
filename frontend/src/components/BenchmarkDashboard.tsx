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

interface TooltipState {
  x: number;
  y: number;
  title: string;
  value: string;
  model: string;
  show: boolean;
}

export const BenchmarkDashboard: React.FC = () => {
  const [selectedWorkload, setSelectedWorkload] = useState<string>('All');
  const [tooltip, setTooltip] = useState<TooltipState>({
    x: 0,
    y: 0,
    title: '',
    value: '',
    model: '',
    show: false,
  });

  const filteredData = selectedWorkload === 'All' 
    ? BENCHMARK_DATA 
    : BENCHMARK_DATA.filter(row => row.workload === selectedWorkload);

  // SVG Chart configurations
  const chartWidth = 460;
  const chartHeight = 180;
  const paddingLeft = 40;
  const paddingRight = 10;
  const paddingTop = 20;
  const paddingBottom = 30;

  const graphWidth = chartWidth - paddingLeft - paddingRight;
  const graphHeight = chartHeight - paddingTop - paddingBottom;

  const workloads = ['Small', 'Medium', 'Large'];

  // Helper to handle mouse movements for tooltips
  const handleMouseMove = (e: React.MouseEvent, title: string, value: string, model: string) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const parentRect = e.currentTarget.parentElement?.getBoundingClientRect();
    const x = rect.left - (parentRect?.left || 0) + rect.width / 2;
    const y = rect.top - (parentRect?.top || 0) - 10;
    setTooltip({ x, y, title, value, model, show: true });
  };

  const handleMouseLeave = () => {
    setTooltip(prev => ({ ...prev, show: false }));
  };

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

      {/* Visual Charts Container */}
      <div className="charts-grid grid-2 mb-6">
        
        {/* Chart 1: Generation Throughput (tok/s) */}
        <div className="chart-card backdrop-blur border-glow relative">
          <h3 className="chart-card-title text-gradient">🚀 Token Throughput (higher is better)</h3>
          <div className="svg-container">
            <svg width="100%" height={chartHeight} viewBox={`0 0 ${chartWidth} ${chartHeight}`}>
              <defs>
                <linearGradient id="qwen-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#818cf8" />
                  <stop offset="100%" stopColor="#4f46e5" />
                </linearGradient>
                <linearGradient id="llama-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22d3ee" />
                  <stop offset="100%" stopColor="#0891b2" />
                </linearGradient>
              </defs>
              
              {/* Y-axis gridlines & labels */}
              {[0, 5, 10, 15].map((val) => {
                const y = paddingTop + graphHeight - (val / 15) * graphHeight;
                return (
                  <g key={val} className="grid-group">
                    <line x1={paddingLeft} y1={y} x2={chartWidth - paddingRight} y2={y} stroke="rgba(255,255,255,0.08)" strokeDasharray="3,3" />
                    <text x={paddingLeft - 8} y={y + 4} fill="hsl(var(--text-muted))" fontSize="10" textAnchor="end">{val}</text>
                  </g>
                );
              })}

              {/* Workload columns (X-axis labels) */}
              {workloads.map((wl, wlIdx) => {
                const groupWidth = graphWidth / workloads.length;
                const groupX = paddingLeft + wlIdx * groupWidth;
                const centerX = groupX + groupWidth / 2;

                const qwenData = BENCHMARK_DATA.find(d => d.workload === wl && d.model.includes('qwen'));
                const llamaData = BENCHMARK_DATA.find(d => d.workload === wl && d.model.includes('llama'));

                const qwenVal = qwenData?.throughput || 0;
                const llamaVal = llamaData?.throughput || 0;

                const qwenHeight = (qwenVal / 15) * graphHeight;
                const llamaHeight = (llamaVal / 15) * graphHeight;

                const barWidth = 24;
                const gap = 4;
                const qwenX = centerX - barWidth - gap;
                const llamaX = centerX + gap;

                return (
                  <g key={wl}>
                    {/* Qwen Bar */}
                    <rect
                      x={qwenX}
                      y={paddingTop + graphHeight - qwenHeight}
                      width={barWidth}
                      height={qwenHeight}
                      fill="url(#qwen-grad)"
                      rx="3"
                      className="chart-bar"
                      onMouseMove={(e) => handleMouseMove(e, `Qwen3 (${wl})`, `${qwenVal.toFixed(1)} tok/s`, 'qwen3:1.7b')}
                      onMouseLeave={handleMouseLeave}
                    />
                    {/* Llama Bar */}
                    <rect
                      x={llamaX}
                      y={paddingTop + graphHeight - llamaHeight}
                      width={barWidth}
                      height={llamaHeight}
                      fill="url(#llama-grad)"
                      rx="3"
                      className="chart-bar"
                      onMouseMove={(e) => handleMouseMove(e, `Llama 3.2 (${wl})`, `${llamaVal.toFixed(1)} tok/s`, 'llama3.2:1b')}
                      onMouseLeave={handleMouseLeave}
                    />
                    {/* X-Label */}
                    <text x={centerX} y={chartHeight - 8} fill="hsl(var(--text-muted))" fontSize="11" textAnchor="middle">{wl}</text>
                  </g>
                );
              })}
              
              <line x1={paddingLeft} y1={paddingTop + graphHeight} x2={chartWidth - paddingRight} y2={paddingTop + graphHeight} stroke="rgba(255,255,255,0.15)" />
            </svg>
          </div>
        </div>

        {/* Chart 2: Model Latency (seconds) */}
        <div className="chart-card backdrop-blur border-glow relative">
          <h3 className="chart-card-title text-gradient">⏱️ Total Request Latency (lower is better)</h3>
          <div className="svg-container">
            <svg width="100%" height={chartHeight} viewBox={`0 0 ${chartWidth} ${chartHeight}`}>
              {/* Y-axis gridlines & labels (max 45 seconds) */}
              {[0, 15, 30, 45].map((val) => {
                const y = paddingTop + graphHeight - (val / 45) * graphHeight;
                return (
                  <g key={val} className="grid-group">
                    <line x1={paddingLeft} y1={y} x2={chartWidth - paddingRight} y2={y} stroke="rgba(255,255,255,0.08)" strokeDasharray="3,3" />
                    <text x={paddingLeft - 8} y={y + 4} fill="hsl(var(--text-muted))" fontSize="10" textAnchor="end">{val}s</text>
                  </g>
                );
              })}

              {/* Workload columns (X-axis labels) */}
              {workloads.map((wl, wlIdx) => {
                const groupWidth = graphWidth / workloads.length;
                const groupX = paddingLeft + wlIdx * groupWidth;
                const centerX = groupX + groupWidth / 2;

                const qwenData = BENCHMARK_DATA.find(d => d.workload === wl && d.model.includes('qwen'));
                const llamaData = BENCHMARK_DATA.find(d => d.workload === wl && d.model.includes('llama'));

                const qwenVal = qwenData?.latency || 0;
                const llamaVal = llamaData?.latency || 0;

                const qwenHeight = (qwenVal / 45) * graphHeight;
                const llamaHeight = (llamaVal / 45) * graphHeight;

                const barWidth = 24;
                const gap = 4;
                const qwenX = centerX - barWidth - gap;
                const llamaX = centerX + gap;

                return (
                  <g key={wl}>
                    {/* Qwen Bar */}
                    <rect
                      x={qwenX}
                      y={paddingTop + graphHeight - qwenHeight}
                      width={barWidth}
                      height={qwenHeight}
                      fill="url(#qwen-grad)"
                      rx="3"
                      className="chart-bar"
                      onMouseMove={(e) => handleMouseMove(e, `Qwen3 (${wl})`, `${qwenVal.toFixed(2)} seconds`, 'qwen3:1.7b')}
                      onMouseLeave={handleMouseLeave}
                    />
                    {/* Llama Bar */}
                    <rect
                      x={llamaX}
                      y={paddingTop + graphHeight - llamaHeight}
                      width={barWidth}
                      height={llamaHeight}
                      fill="url(#llama-grad)"
                      rx="3"
                      className="chart-bar"
                      onMouseMove={(e) => handleMouseMove(e, `Llama 3.2 (${wl})`, `${llamaVal.toFixed(2)} seconds`, 'llama3.2:1b')}
                      onMouseLeave={handleMouseLeave}
                    />
                    {/* X-Label */}
                    <text x={centerX} y={chartHeight - 8} fill="hsl(var(--text-muted))" fontSize="11" textAnchor="middle">{wl}</text>
                  </g>
                );
              })}
              
              <line x1={paddingLeft} y1={paddingTop + graphHeight} x2={chartWidth - paddingRight} y2={paddingTop + graphHeight} stroke="rgba(255,255,255,0.15)" />
            </svg>
          </div>
        </div>

        {/* Legend Overlay / Floating Tooltip */}
        {tooltip.show && (
          <div
            className="chart-tooltip backdrop-blur"
            style={{
              position: 'absolute',
              left: `${tooltip.x}px`,
              top: `${tooltip.y}px`,
              transform: 'translate(-50%, -100%)',
              zIndex: 10,
              pointerEvents: 'none',
            }}
          >
            <div className="tooltip-title">{tooltip.title}</div>
            <div className="tooltip-value" style={{ color: tooltip.model.includes('llama') ? 'hsl(var(--secondary))' : 'hsl(var(--primary))' }}>
              {tooltip.value}
            </div>
            <div className="tooltip-model">{tooltip.model}</div>
          </div>
        )}
      </div>

      {/* Global Legend */}
      <div className="chart-legend-row mb-6">
        <div className="legend-item">
          <span className="legend-color-dot" style={{ backgroundColor: '#818cf8' }}></span>
          <span className="legend-label">Qwen3-1.7b (Summarizer)</span>
        </div>
        <div className="legend-item">
          <span className="legend-color-dot" style={{ backgroundColor: '#22d3ee' }}></span>
          <span className="legend-label">Llama 3.2-1b (Translator)</span>
        </div>
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
      <div className="takeaways-section grid-2 mt-6">
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
