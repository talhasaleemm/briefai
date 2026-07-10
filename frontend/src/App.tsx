import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { AudioRecorder } from './components/AudioRecorder';
import { AudioUploader } from './components/AudioUploader';
import { DiarizedTranscriptView } from './components/DiarizedTranscriptView';
import { BenchmarkDashboard } from './screens/BenchmarkDashboard';
import { MetricCard } from './components/MetricCard';
import { TaskGridSelector } from './components/TaskGridSelector';
import { AuthProvider, useAuth } from './components/AuthContext';
import { AuthScreen } from './screens/AuthScreen';
import { TranscriptsSidebar } from './components/TranscriptsSidebar';
import { AskBriefAI } from './screens/AskBriefAI';
import { Templates } from './screens/Templates';
import { getAccessToken } from './api/client';
import './App.css';

type TabType = 'workspace' | 'benchmarks' | 'ask' | 'templates';

export function AppWorkspace() {
  const [activeTab, setActiveTab] = useState<TabType>('workspace');
  const [inputMode, setInputMode] = useState<'paste' | 'mic' | 'upload'>('paste');
  
  // Historical transcripts state
  const [selectedTranscript, setSelectedTranscript] = useState<TranscriptItem | null>(null);
  const [sidebarRefresh, setSidebarRefresh] = useState<number>(0);

  const handleSelectTranscript = (item: TranscriptItem | null) => {
    setSelectedTranscript(item);
    if (item) {
      setTranscript(item.content);
      setDiarizationStatus(item.diarization_status || 'none');
      setDiarizedSegments(item.diarized_segments || []);
      // Reset output states for clean workspace
      setOutputText('');
      setErrorMessage(null);
      setTtftMs(null);
      setTotalLatencyS(null);
      setThroughput(null);
      setTokenCount(null);
      setCheckedItems({});
      setOutputSegments([]);
    } else {
      setTranscript('');
      setDiarizationStatus('none');
      setDiarizedSegments([]);
    }
  };
  
  // LLM Input State
  const [transcript, setTranscript] = useState<string>('');
  const [diarizationStatus, setDiarizationStatus] = useState<string>('none');
  const [diarizedSegments, setDiarizedSegments] = useState<any[]>([]);
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

  const [outputTab, setOutputTab] = useState<'preview' | 'raw' | 'actions' | 'timeline'>('preview');
  const [outputSegments, setOutputSegments] = useState<any[]>([]);
  const [checkedItems, setCheckedItems] = useState<{[key: number]: boolean}>({});
  
  // Custom Templates
  const [customTemplates, setCustomTemplates] = useState<any[]>([]);
  useEffect(() => {
    fetch('/api/v1/templates/', {
      headers: {
        'Authorization': `Bearer ${getAccessToken()}`
      }
    })
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setCustomTemplates(data);
      })
      .catch(console.error);
  }, [activeTab]);

  // Stream parsing references
  const streamStartTimeRef = useRef<number>(0);
  const firstTokenTimeRef = useRef<number>(0);

  // Keyboard Shortcuts Hook
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // 1. Process Transcript: Ctrl/Cmd + Enter
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (!isProcessing && transcript.trim().length >= 10) {
          e.preventDefault();
          handleProcess();
        }
      }
      // 2. Toggle Recording: Alt + R
      if (e.altKey && e.key.toLowerCase() === 'r') {
        e.preventDefault();
        const recordBtn = document.querySelector('.btn-record, .btn-stop') as HTMLButtonElement | null;
        if (recordBtn) {
          recordBtn.click();
        }
      }
      // 3. Clear Output/Cancel: Escape
      if (e.key === 'Escape') {
        if (isProcessing) {
          setErrorMessage(null);
        } else {
          setOutputText('');
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isProcessing, transcript, outputText]);

  // Polling for Diarization Status
  useEffect(() => {
    let interval: any;
    if (diarizationStatus === 'pending' && selectedTranscript?.id) {
      interval = setInterval(async () => {
        try {
          const res = await (window as any).api.get(`/api/v1/transcripts/${selectedTranscript.id}/diarization`);
          if (res.data.diarization_status !== 'pending') {
            setDiarizationStatus(res.data.diarization_status);
            setDiarizedSegments(res.data.diarized_segments || []);
            setSidebarRefresh(prev => prev + 1); // Refresh sidebar to update stored status
          }
        } catch (err) {
          console.error('Error polling diarization status:', err);
        }
      }, 5000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [selectedTranscript?.id, diarizationStatus]);

  // When outputText changes (e.g. starting a new process), reset action list check states
  const handleProcess = async () => {
    if (!transcript.trim()) {
      setErrorMessage('Please provide a meeting transcript first.');
      return;
    }

    if (transcript.trim().length < 10) {
      setErrorMessage(
        'Transcript too short (minimum 10 characters). ' +
        'If you just recorded, try speaking louder and closer to the microphone, then record again.'
      );
      return;
    }

    setIsProcessing(true);
    setErrorMessage(null);
    setOutputText('');
    setTtftMs(null);
    setTotalLatencyS(null);
    setThroughput(null);
    setTokenCount(null);
    setCheckedItems({});

    streamStartTimeRef.current = performance.now();
    firstTokenTimeRef.current = 0;

    let actualTask = task;
    let customTemplateId: number | null = null;
    if (task.startsWith('custom_')) {
      customTemplateId = parseInt(task.split('_')[1], 10);
      actualTask = 'summarize'; // fallback string, it will be overridden in backend
    }

    const payload = {
      transcript: transcript.trim(),
      task: actualTask,
      model,
      target_language: task === 'translate' ? targetLanguage : null,
      stream,
      transcript_id: selectedTranscript?.id ?? null,
      custom_template_id: customTemplateId,
    };

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      const token = getAccessToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch('/api/v1/summarization/process', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        let detailMsg: string;
        const detail = errorData.detail;
        if (typeof detail === 'string') {
          detailMsg = detail;
        } else if (Array.isArray(detail)) {
          detailMsg = detail.map((e: any) => e.msg || JSON.stringify(e)).join('; ');
        } else if (detail) {
          detailMsg = JSON.stringify(detail);
        } else {
          detailMsg = `Server returned HTTP ${response.status}`;
        }
        throw new Error(detailMsg);
      }

      if (stream) {
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

        const wordCount = accumulatedText.trim().split(/\s+/).length;
        const estTokens = Math.round(wordCount * 1.3);
        setTokenCount(estTokens);

        const genDuration = firstTokenTimeRef.current 
          ? (endTime - firstTokenTimeRef.current) / 1000.0 
          : totalDuration;
        setThroughput(parseFloat((estTokens / (genDuration || 1)).toFixed(1)));

        if (accumulatedText.includes('[ERROR: Qwen3 failed')) {
          setErrorMessage('Reasoning Token Cap Exceeded: The model failed to generate response text within the budget.');
        }
      } else {
        const data = await response.json();
        const latency = data.latency_ms / 1000.0;
        
        setOutputText(data.result);
        setTokenCount(data.output_tokens);
        setTotalLatencyS(latency);
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

  const handleFinalSegmentsReceived = (segments: any[]) => {
    setOutputSegments(segments);
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
            className={`nav-link-btn ${activeTab === 'ask' ? 'active' : ''}`}
            onClick={() => setActiveTab('ask')}
          >
            Ask BriefAI 🧠
          </button>
          <button 
            className={`nav-link-btn ${activeTab === 'templates' ? 'active' : ''}`}
            onClick={() => setActiveTab('templates')}
          >
            Template Builder
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
          <div className="workspace-container">
            <TranscriptsSidebar
              selectedId={selectedTranscript?.id ?? null}
              onSelect={handleSelectTranscript}
              refreshTrigger={sidebarRefresh}
              onRefresh={() => setSidebarRefresh(prev => prev + 1)}
            />
            
            <div className="workspace-grid grid-2" style={{ flex: 1, padding: '1.5rem 2rem', overflowY: 'auto' }}>
            
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
                <button
                  className={`input-mode-btn ${inputMode === 'upload' ? 'active' : ''}`}
                  onClick={() => setInputMode('upload')}
                >
                  📁 Upload Audio
                </button>
              </div>

              {/* Input Text Box */}
              <div className="input-area-container">
                {inputMode === 'paste' ? (
                  diarizationStatus !== 'none' ? (
                    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '0.5rem' }}>
                        <button 
                          className="btn btn-sm btn-secondary" 
                          onClick={() => { 
                            setDiarizationStatus('none'); 
                            setDiarizedSegments([]); 
                            setTranscript(''); 
                            setSelectedTranscript(null);
                          }}
                        >
                          Clear Transcript
                        </button>
                      </div>
                      <div style={{ flex: 1, minHeight: 0 }}>
                        <DiarizedTranscriptView 
                          status={diarizationStatus} 
                          segments={diarizedSegments} 
                          rawTranscript={transcript} 
                        />
                      </div>
                    </div>
                  ) : (
                    <textarea
                      className="transcript-textarea"
                      placeholder="Paste your meeting notes, conversation logs, or board transcript here (min 10 characters)..."
                      value={transcript}
                      onChange={(e) => setTranscript(e.target.value)}
                    />
                  )
                ) : inputMode === 'upload' ? (
                  <div className="upload-mode-container">
                    <AudioUploader
                      onUploadSuccess={(_id, text, dStatus, dSegments) => {
                        setSidebarRefresh(prev => prev + 1);
                        // Assuming TranscriptsSidebar auto-selects the newest, or we can just set it here:
                        setTranscript(text);
                        setDiarizationStatus(dStatus);
                        setDiarizedSegments(dSegments);
                      }}
                      onUploadError={setErrorMessage}
                    />
                    <div className="live-transcript-box mt-3" style={{ flex: 1, minHeight: 0 }}>
                      <label className="box-label">Uploaded Transcript:</label>
                      {diarizationStatus !== 'none' ? (
                        <div style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
                          <DiarizedTranscriptView 
                            status={diarizationStatus} 
                            segments={diarizedSegments} 
                            rawTranscript={transcript} 
                          />
                        </div>
                      ) : (
                        <textarea
                          className="transcript-textarea-mic-mode"
                          readOnly
                          placeholder="Transcript will appear here after upload..."
                          value={transcript}
                          style={{ flex: 1 }}
                        />
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="mic-mode-container">
                    <AudioRecorder 
                      onTranscriptChange={setTranscript}
                      onStatusChange={setRecorderStatus}
                      onFinalSegments={handleFinalSegmentsReceived}
                      onRecordingFinished={() => setSidebarRefresh(prev => prev + 1)}
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
                <h3 className="section-title">2. Select LLM Task</h3>
                
                {/* Visual Task Grid Selector */}
                <TaskGridSelector currentTask={task} onChange={setTask} customTemplates={customTemplates} />

                <div className="config-grid mt-4">
                  <div className="config-item">
                    <label className="config-label">Local LLM Model</label>
                    <select className="config-select" value={model} onChange={(e) => setModel(e.target.value)}>
                      <option value="qwen3:1.7b">Qwen3-1.7B (Summarizer)</option>
                      <option value="llama3.2:1b">Llama 3.2-1B (Translator)</option>
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
                  <kbd className="shortcut-badge ml-2">⌘↵</kbd>
                </button>
              </div>
            </div>

            {/* Right Panel: Output Terminal */}
            <div className="workspace-panel panel-right backdrop-blur border-glow">
              <div className="panel-header-actions flex-col md:flex-row gap-3">
                <div className="panel-title-group">
                  <h2 className="panel-title mb-2 md:mb-0">3. Processed Output</h2>
                  {/* Visual Tab Bar */}
                  <div className="output-tab-bar">
                    <button 
                      className={`output-tab-btn ${outputTab === 'preview' ? 'active' : ''}`}
                      onClick={() => setOutputTab('preview')}
                    >
                      📄 Preview
                    </button>
                    <button 
                      className={`output-tab-btn ${outputTab === 'raw' ? 'active' : ''}`}
                      onClick={() => setOutputTab('raw')}
                    >
                      📝 Raw Text
                    </button>
                    <button 
                      className={`output-tab-btn ${outputTab === 'actions' ? 'active' : ''}`}
                      onClick={() => setOutputTab('actions')}
                    >
                      ☑️ Checklists
                    </button>
                    <button 
                      className={`output-tab-btn ${outputTab === 'timeline' ? 'active' : ''}`}
                      onClick={() => setOutputTab('timeline')}
                    >
                      ⏱️ Timeline
                    </button>
                  </div>
                </div>
                {outputText && !isProcessing && (
                  <div className="output-actions self-end md:self-auto">
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
                  <div className="output-tab-content flex-1 flex flex-col">
                    {outputTab === 'preview' && (
                      <div className="markdown-output">
                        {isProcessing ? (
                          <pre className="markdown-streaming">{outputText}</pre>
                        ) : (
                          <ReactMarkdown>{outputText}</ReactMarkdown>
                        )}
                      </div>
                    )}

                    {outputTab === 'raw' && (
                      <textarea
                        className="markdown-raw-textbox"
                        value={outputText}
                        onChange={(e) => setOutputText(e.target.value)}
                        readOnly={isProcessing}
                      />
                    )}

                    {outputTab === 'actions' && (
                      <div className="actions-tab-view">
                        <h4 className="actions-title">Interactive Action Items Checkoff</h4>
                        {(() => {
                          const lines = outputText.split('\n');
                          const actionLines = lines.map((line, idx) => {
                            const trimmed = line.trim();
                            const isListItem = trimmed.startsWith('-') || trimmed.startsWith('*') || /^\d+\./.test(trimmed);
                            if (isListItem) {
                              const cleanText = trimmed
                                .replace(/^[-*]\s*(\[ \])?\s*/, '')
                                .replace(/^\d+\.\s*/, '');
                              const isChecked = checkedItems[idx] || false;
                              return (
                                <label key={idx} className="action-checkbox-row border-glow">
                                  <input
                                    type="checkbox"
                                    checked={isChecked}
                                    onChange={() => setCheckedItems(prev => ({ ...prev, [idx]: !isChecked }))}
                                    className="action-checkbox-input"
                                  />
                                  <span className={`action-checkbox-text ${isChecked ? 'completed' : ''}`}>
                                    {cleanText}
                                  </span>
                                </label>
                              );
                            }
                            return null;
                          }).filter(Boolean);

                          return actionLines.length > 0 ? (
                            <div className="action-checkboxes-list">{actionLines}</div>
                          ) : (
                            <div className="terminal-placeholder">
                              <p>No list items detected. Process a transcript containing tasks or select the "Action Items" task.</p>
                            </div>
                          );
                        })()}
                      </div>
                    )}

                    {outputTab === 'timeline' && (
                      <div className="timeline-tab-view">
                        <h4 className="timeline-title">Audio Segment Sequence Log</h4>
                        {outputSegments && outputSegments.length > 0 ? (
                          <div className="timeline-segments-list">
                            {outputSegments.map((seg, idx) => (
                              <div key={idx} className="timeline-segment border-glow">
                                <div className="segment-metadata">
                                  <span className="segment-time-range">⏱️ {seg.start.toFixed(1)}s - {seg.end.toFixed(1)}s</span>
                                  <span className="segment-confidence">Confidence: {Math.round(Math.exp(seg.confidence || 0) * 100)}%</span>
                                </div>
                                <p className="segment-text">{seg.text}</p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="terminal-placeholder">
                            <p>No timeline segments recorded. Record from microphone in live mode to collect segments.</p>
                          </div>
                        )}
                      </div>
                    )}
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
        </div>
        ) : activeTab === 'ask' ? (
          <div className="workspace-container" style={{ padding: '2rem' }}>
            <AskBriefAI />
          </div>
        ) : activeTab === 'templates' ? (
          <div className="workspace-container" style={{ padding: '2rem', overflowY: 'auto' }}>
            <Templates />
          </div>
        ) : (
          <BenchmarkDashboard />
        )}
      </main>
    </div>
  );
}

interface TranscriptItem {
  id: number;
  title: string;
  content: string;
  created_at: string;
  diarization_status?: string;
  diarized_segments?: any[];
}

function AppContent() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="auth-container">
        <div className="auth-card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '200px' }}>
          <div className="loader-mini" style={{ width: '40px', height: '40px', borderWidth: '4px', borderColor: 'hsl(var(--primary-color)) transparent transparent transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }}></div>
          <p style={{ marginTop: '1.5rem', color: 'hsl(var(--text-muted))', fontWeight: 600 }}>Restoring secure session...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthScreen />;
  }

  return <AppWorkspace />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
