import { useState, useRef } from 'react';
import { AudioRecorder } from './components/AudioRecorder';
import { BenchmarkDashboard } from './components/BenchmarkDashboard';
import { MetricCard } from './components/MetricCard';
import './App.css';

type TabType = 'workspace' | 'benchmarks';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>('workspace');
  const [inputMode, setInputMode] = useState<'paste' | 'mic'>('paste');
  
  // LLM Input State
  const [transcript, setTranscript] = useState<string>('');
  const [model, setModel] = useState<string>('qwen3:1.7b');
  const [task, setTask] = useState<string>('summarize');
  const [targetLanguage, setTargetLanguage] = useState<string>('Spanish');
  const [stream, setStream] = useState<boolean>(true);
  
  // LLM Output & Processing State
  const [outputText, setOutputText] = useState<string>('');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  
  // Metrics State
  const [ttftMs, setTtftMs] = useState<number | null>(null);
  const [totalLatencyS, setTotalLatencyS] = useState<number | null>(null);
  const [throughput, setThroughput] = useState<number | null>(null);
  const [tokenCount, setTokenCount] = useState<number | null>(null);
  
  // Recorder status
  const [recorderStatus, setRecorderStatus] = useState<'idle' | 'recording' | 'error'>('idle');

  // Stream parsing references
  const streamStartTimeRef = useRef<number>(0);
  const firstTokenTimeRef = useRef<number>(0);

  const handleProcess = async () => {
    if (!transcript.trim()) {
      setErrorMessage('Please provide a meeting transcript first.');
      return;
    }

    setIsProcessing(true);
    setErrorMessage(null);
    setOutputText('');
    setTtftMs(null);
    setTotalLatencyS(null);
    setThroughput(null);
    setTokenCount(null);

    streamStartTimeRef.current = performance.now();
    firstTokenTimeRef.current = 0;

    const payload = {
      transcript: transcript.trim(),
      task,
      model,
      target_language: task === 'translate' ? targetLanguage : null,
      stream,
    };

    try {
      const response = await fetch('http://localhost:8000/api/v1/summarization/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server returned HTTP ${response.status}`);
      }

      if (stream) {
        // SSE Stream Reader
        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('ReadableStream is not supported by your browser.');
        }

        const decoder = new TextDecoder('utf-8');
        let accumulatedText = '';
        let hasFirstToken = false;

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          
          if (!hasFirstToken && chunk.trim()) {
            hasFirstToken = true;
            const now = performance.now();
            firstTokenTimeRef.current = now;
            setTtftMs(Math.round(now - streamStartTimeRef.current));
          }

          accumulatedText += chunk;
          setOutputText(accumulatedText);
        }

        const endTime = performance.now();
        const totalDuration = (endTime - streamStartTimeRef.current) / 1000.0;
        setTotalLatencyS(parseFloat(totalDuration.toFixed(2)));

        // Estimate token counts based on whitespace separation (standard rule of thumb: ~1.3 tokens per word)
        const wordCount = accumulatedText.trim().split(/\s+/).length;
        const estTokens = Math.round(wordCount * 1.3);
        setTokenCount(estTokens);

        const genDuration = firstTokenTimeRef.current 
          ? (endTime - firstTokenTimeRef.current) / 1000.0 
          : totalDuration;
        setThroughput(parseFloat((estTokens / (genDuration || 1)).toFixed(1)));

        // Check if Qwen3 streaming failed due to token budget constraint
        if (accumulatedText.includes('[ERROR: Qwen3 failed')) {
          setErrorMessage('Reasoning Token Cap Exceeded: The model failed to generate response text within the budget.');
        }
      } else {
        // Non-streaming block response
        const data = await response.json();
        const latency = data.latency_ms / 1000.0;
        
        setOutputText(data.result);
        setTokenCount(data.output_tokens);
        setTotalLatencyS(latency);
        
        // Non-streaming TTFT is equal to generation latency
        setTtftMs(data.latency_ms);
        setThroughput(parseFloat((data.output_tokens / (latency || 1)).toFixed(1)));
      }
    } catch (err: any) {
      console.error('Processing failed:', err);
      setErrorMessage(err.message || 'An unknown error occurred during generation.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(outputText);
  };

  const handleDownload = () => {
    const blob = new Blob([outputText], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `briefai_summary_${task}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="app-container">
      {/* Header / Navbar */}
      <header className="app-navbar backdrop-blur">
        <div className="nav-logo">
          <span className="logo-icon">🚀</span>
          <span className="logo-text text-gradient">BriefAI</span>
        </div>
        <nav className="nav-links">
          <button 
            className={`nav-link-btn ${activeTab === 'workspace' ? 'active' : ''}`}
            onClick={() => setActiveTab('workspace')}
          >
            Workspace
          </button>
          <button 
            className={`nav-link-btn ${activeTab === 'benchmarks' ? 'active' : ''}`}
            onClick={() => setActiveTab('benchmarks')}
          >
            Performance Benchmarks
          </button>
        </nav>
      </header>

      {/* Main Container */}
      <main className="app-main-content">
        {activeTab === 'workspace' ? (
          <div className="workspace-container grid-2">
            
            {/* Left Panel: Inputs */}
            <div className="workspace-panel panel-left backdrop-blur border-glow">
              <h2 className="panel-title">1. Input Transcript</h2>
              
              {/* Input Mode Selector */}
              <div className="input-mode-tabs">
                <button
                  className={`input-mode-btn ${inputMode === 'paste' ? 'active' : ''}`}
                  onClick={() => setInputMode('paste')}
                >
                  📝 Paste Transcript
                </button>
                <button
                  className={`input-mode-btn ${inputMode === 'mic' ? 'active' : ''}`}
                  onClick={() => setInputMode('mic')}
                >
                  🎙️ Live Microphone
                </button>
              </div>

              {/* Input Text Box */}
              <div className="input-area-container">
                {inputMode === 'paste' ? (
                  <textarea
                    className="transcript-textarea"
                    placeholder="Paste your meeting notes, conversation logs, or board transcript here (min 10 characters)..."
                    value={transcript}
                    onChange={(e) => setTranscript(e.target.value)}
                  />
                ) : (
                  <div className="mic-mode-container">
                    <AudioRecorder 
                      onTranscriptChange={setTranscript}
                      onStatusChange={setRecorderStatus}
                    />
                    <div className="live-transcript-box">
                      <label className="box-label">Live Finalizing Transcript:</label>
                      <textarea
                        className="transcript-textarea-mic-mode"
                        readOnly
                        placeholder="Live transcript will populate here once you start speaking..."
                        value={transcript}
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* LLM Task Configuration */}
              <div className="task-config-section">
                <h3 className="section-title">2. Processing Options</h3>
                
                <div className="config-grid">
                  <div className="config-item">
                    <label className="config-label">Local LLM Model</label>
                    <select className="config-select" value={model} onChange={(e) => setModel(e.target.value)}>
                      <option value="qwen3:1.7b">Qwen3-1.7B (Summarizer)</option>
                      <option value="llama3.2:1b">Llama 3.2-1B (Translator)</option>
                    </select>
                  </div>

                  <div className="config-item">
                    <label className="config-label">Task Type</label>
                    <select className="config-select" value={task} onChange={(e) => setTask(e.target.value)}>
                      <option value="summarize">Executive Summary</option>
                      <option value="translate">Multilingual Translation</option>
                      <option value="action_items">Action Items Extraction</option>
                      <option value="lecture_notes">Lecture Study Notes</option>
                      <option value="decisions">Decisions Log</option>
                      <option value="terminology">Terminology definitions</option>
                    </select>
                  </div>

                  {task === 'translate' && (
                    <div className="config-item animate-fade-in">
                      <label className="config-label">Target Language</label>
                      <input 
                        type="text" 
                        className="config-input"
                        value={targetLanguage} 
                        onChange={(e) => setTargetLanguage(e.target.value)}
                      />
                    </div>
                  )}

                  <div className="config-item toggle-item">
                    <label className="config-toggle-label">
                      <input 
                        type="checkbox" 
                        checked={stream} 
                        onChange={(e) => setStream(e.target.checked)}
                      />
                      Enable Token Streaming
                    </label>
                  </div>
                </div>

                <button 
                  type="button"
                  className="btn btn-success btn-process"
                  disabled={isProcessing || recorderStatus === 'recording' || !transcript.trim()}
                  onClick={handleProcess}
                >
                  {isProcessing ? 'Generating Response...' : '⚡ Process Transcript'}
                </button>
              </div>
            </div>

            {/* Right Panel: Output Terminal */}
            <div className="workspace-panel panel-right backdrop-blur border-glow">
              <div className="panel-header-actions">
                <h2 className="panel-title">3. Processed Output</h2>
                {outputText && !isProcessing && (
                  <div className="output-actions">
                    <button className="btn-icon" onClick={handleCopy} title="Copy Content">📋 Copy</button>
                    <button className="btn-icon" onClick={handleDownload} title="Download Markdown">💾 Download</button>
                  </div>
                )}
              </div>

              {/* Output Display Container */}
              <div className="output-terminal">
                {errorMessage && (
                  <div className="alert alert-error">
                    <p className="alert-text"><strong>Error:</strong> {errorMessage}</p>
                  </div>
                )}

                {isProcessing && !outputText && (
                  <div className="loader-container">
                    <div className="spinner"></div>
                    <p className="loader-text">Loading local LLM model & digesting context...</p>
                  </div>
                )}

                {outputText ? (
                  <div className="markdown-output pre-wrap">
                    {outputText}
                  </div>
                ) : (
                  !isProcessing && (
                    <div className="terminal-placeholder">
                      <span className="terminal-icon">📟</span>
                      <p>Output terminal idle. Run a task to generate structured meeting summaries.</p>
                    </div>
                  )
                )}
              </div>

              {/* Metrics Display */}
              <div className="metrics-dashboard">
                <MetricCard 
                  title="TTFT"
                  value={ttftMs !== null ? ttftMs : '—'}
                  unit="ms"
                  description="Time to first generated token"
                  icon={<span>⏱️</span>}
                />
                <MetricCard 
                  title="Total Latency"
                  value={totalLatencyS !== null ? totalLatencyS : '—'}
                  unit="s"
                  description="Complete request duration"
                  icon={<span>⌛</span>}
                />
                <MetricCard 
                  title="Throughput"
                  value={throughput !== null ? throughput : '—'}
                  unit="tok/s"
                  description="Generation tokens per second"
                  icon={<span>🚀</span>}
                />
                <MetricCard 
                  title="Output Length"
                  value={tokenCount !== null ? tokenCount : '—'}
                  unit="tok"
                  description="Estimated generated length"
                  icon={<span>📄</span>}
                />
              </div>
            </div>

          </div>
        ) : (
          <BenchmarkDashboard />
        )}
      </main>
    </div>
  );
}
