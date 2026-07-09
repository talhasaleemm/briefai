import React from 'react';

interface LabeledSegment {
  start: number;
  end: number;
  text: string;
  speaker: string;
  confidence?: number;
}

interface DiarizedTranscriptViewProps {
  status: string;
  segments: LabeledSegment[];
  rawTranscript: string;
}

// Simple deterministic color generator for speakers
const getSpeakerColor = (speakerName: string) => {
  let hash = 0;
  for (let i = 0; i < speakerName.length; i++) {
    hash = speakerName.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue}, 70%, 65%)`; // Pastel color
};

export const DiarizedTranscriptView: React.FC<DiarizedTranscriptViewProps> = ({
  status,
  segments,
  rawTranscript
}) => {
  if (status === 'pending') {
    return (
      <div className="diarization-pending" style={{ padding: '2rem', textAlign: 'center', background: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
        <div className="spinner-border text-primary" role="status" style={{ marginBottom: '1rem' }}></div>
        <h4>Identifying speakers…</h4>
        <p style={{ color: '#888' }}>This may take a few minutes depending on the audio length.</p>
        <div className="raw-transcript-preview" style={{ marginTop: '2rem', textAlign: 'left', opacity: 0.5 }}>
          <h5>Raw Transcript:</h5>
          <p style={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>{rawTranscript}</p>
        </div>
      </div>
    );
  }

  if (status === 'failed') {
    return (
      <div className="diarization-failed" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div style={{ background: 'rgba(255, 50, 50, 0.2)', borderLeft: '4px solid #ff4444', padding: '1rem', marginBottom: '1rem', borderRadius: '4px' }}>
          <strong style={{ color: '#ffaaaa' }}>⚠️ Speaker identification failed.</strong>
          <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.9rem' }}>The raw transcript is still available below.</p>
        </div>
        <textarea
          className="transcript-textarea"
          readOnly
          value={rawTranscript}
          style={{ flex: 1 }}
        />
      </div>
    );
  }

  if (status === 'complete' && segments && segments.length > 0) {
    // Group consecutive segments by the same speaker
    const blocks: { speaker: string; text: string; start: number; end: number }[] = [];
    
    segments.forEach((seg) => {
      if (blocks.length === 0) {
        blocks.push({ speaker: seg.speaker, text: seg.text.trim(), start: seg.start, end: seg.end });
      } else {
        const lastBlock = blocks[blocks.length - 1];
        if (lastBlock.speaker === seg.speaker) {
          lastBlock.text += ' ' + seg.text.trim();
          lastBlock.end = seg.end;
        } else {
          blocks.push({ speaker: seg.speaker, text: seg.text.trim(), start: seg.start, end: seg.end });
        }
      }
    });

    const formatTime = (seconds: number) => {
      const m = Math.floor(seconds / 60);
      const s = Math.floor(seconds % 60);
      return `${m}:${s.toString().padStart(2, '0')}`;
    };

    return (
      <div className="diarized-transcript-view" style={{ 
        background: 'rgba(0,0,0,0.2)', 
        borderRadius: '8px', 
        padding: '1rem',
        height: '100%',
        overflowY: 'auto'
      }}>
        {blocks.map((block, idx) => (
          <div key={idx} style={{ 
            marginBottom: '1.5rem', 
            borderLeft: `4px solid ${getSpeakerColor(block.speaker)}`,
            paddingLeft: '1rem'
          }}>
            <div style={{ fontSize: '0.85rem', color: '#aaa', marginBottom: '0.3rem', fontWeight: 600 }}>
              <span style={{ color: getSpeakerColor(block.speaker) }}>🎙 {block.speaker}</span> 
              <span style={{ margin: '0 0.5rem' }}>·</span>
              <span>{formatTime(block.start)} – {formatTime(block.end)}</span>
            </div>
            <div style={{ lineHeight: 1.5 }}>
              {block.text}
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Fallback (e.g. status === 'none' or missing segments)
  return (
    <textarea
      className="transcript-textarea"
      readOnly
      value={rawTranscript}
    />
  );
};
