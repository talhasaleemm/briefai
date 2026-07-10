import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { getAccessToken } from '../api/client';
import './AskBriefAI.css';

export function AskBriefAI() {
  const [query, setQuery] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [response, setResponse] = useState('');
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll output when response changes
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [response]);

  const handleAsk = async () => {
    const q = query.trim();
    if (!q) return;

    setIsProcessing(true);
    setResponse('');
    setError(null);
    setQuery('');

    try {
      const token = getAccessToken();
      const res = await fetch('/api/v1/chat/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          query: q,
          model: 'llama3.2:1b'
        })
      });

      if (!res.ok) {
        throw new Error('Failed to fetch response');
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error('Streaming not supported');

      const decoder = new TextDecoder('utf-8');
      let text = '';
      
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        text += decoder.decode(value, { stream: true });
        setResponse(text);
      }
    } catch (err: any) {
      setError(err.message || 'Error communicating with BriefAI');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="ask-briefai-container backdrop-blur border-glow">
      <div className="chat-header">
        <h2 className="panel-title">Ask BriefAI</h2>
        <p className="subtitle">Ask questions over your entire meeting history. (Single-turn MVP)</p>
      </div>

      <div className="chat-output" ref={scrollRef}>
        {error && (
          <div className="alert alert-error">
            <p className="alert-text">{error}</p>
          </div>
        )}
        
        {response ? (
          <div className="markdown-output">
            <ReactMarkdown>{response}</ReactMarkdown>
            {isProcessing && <span className="blinking-cursor">▋</span>}
          </div>
        ) : !isProcessing ? (
          <div className="empty-state">
            <span className="empty-icon">🤖</span>
            <p>I am BriefAI. What would you like to know about your past meetings?</p>
          </div>
        ) : null}

        {isProcessing && !response && (
          <div className="loader-container">
            <div className="spinner"></div>
            <p className="loader-text">Searching your meetings & generating response...</p>
          </div>
        )}
      </div>

      <div className="chat-input-container">
        <input 
          type="text" 
          className="chat-input"
          placeholder="e.g. What did we decide about the new feature?"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleAsk();
          }}
          disabled={isProcessing}
        />
        <button 
          className="btn btn-primary"
          onClick={handleAsk}
          disabled={isProcessing || !query.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
