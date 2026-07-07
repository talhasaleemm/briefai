import React, { useState, useRef, useEffect } from 'react';

interface AudioRecorderProps {
  onTranscriptChange: (text: string) => void;
  onStatusChange: (status: 'idle' | 'recording' | 'error') => void;
}

export const AudioRecorder: React.FC<AudioRecorderProps> = ({
  onTranscriptChange,
  onStatusChange,
}) => {
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const webSocketRef = useRef<WebSocket | null>(null);
  const transcriptBufferRef = useRef<string>('');
  const isRecordingRef = useRef<boolean>(false);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, []);

  const startRecording = async () => {
    // Guard: if already recording or a WebSocket is already open, don't start again.
    // This prevents React Strict Mode double-invocation from opening two connections.
    if (isRecordingRef.current || webSocketRef.current) {
      return;
    }

    setErrorMessage(null);
    transcriptBufferRef.current = '';
    onTranscriptChange('');

    try {
      // 1. Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      mediaStreamRef.current = stream;

      // 2. Initialize AudioContext and AudioWorklet FIRST
      //    (must succeed before opening WebSocket, so we don't connect then send nothing)
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      audioContextRef.current = audioContext;

      try {
        await audioContext.audioWorklet.addModule('/audio-processor.js');
      } catch (workletErr: any) {
        console.error('AudioWorklet load failed:', workletErr);
        throw new Error(`AudioWorklet failed to load: ${workletErr.message || workletErr}`);
      }

      const sourceNode = audioContext.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(audioContext, 'audio-processor');
      workletNodeRef.current = workletNode;

      // 3. Open WebSocket only AFTER AudioWorklet is ready
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/transcription/stream`;
      console.log('Opening WebSocket:', wsUrl);
      const ws = new WebSocket(wsUrl);
      webSocketRef.current = ws;

      ws.onopen = () => {
        console.log('Transcription WebSocket connected, starting audio stream');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('WS message received:', data);

          if (data.type === 'segment' && data.text) {
            // Interim segment — append to running transcript
            transcriptBufferRef.current = (transcriptBufferRef.current + ' ' + data.text).trim();
            onTranscriptChange(transcriptBufferRef.current);
          } else if (data.type === 'final' && data.transcript) {
            // Final consolidated transcript
            transcriptBufferRef.current = data.transcript;
            onTranscriptChange(transcriptBufferRef.current);
          } else if (data.type === 'error') {
            console.error('Backend transcription error:', data.message);
          }
        } catch (err) {
          console.error('Error parsing WS message:', err, event.data);
        }
      };

      ws.onerror = (err) => {
        console.error('WebSocket Error:', err);
        handleFailure('WebSocket error occurred mid-stream.');
      };

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        if (isRecordingRef.current) {
          handleFailure(`WebSocket closed unexpectedly (code ${event.code}).`);
        }
      };

      // 4. Send audio chunks from worklet to WebSocket
      workletNode.port.onmessage = (event) => {
        const float32Data: Float32Array = event.data;
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(float32Data.buffer as ArrayBuffer);
        }
      };

      // 5. Connect audio graph
      sourceNode.connect(workletNode);
      workletNode.connect(audioContext.destination);

      isRecordingRef.current = true;
      setIsRecording(true);
      onStatusChange('recording');

    } catch (err: any) {
      console.error('Recording initialization failed:', err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        handleFailure('Microphone permission was denied. Please allow microphone access in your browser settings.');
      } else {
        handleFailure(`Failed to initialize recorder: ${err.message || err}`);
      }
    }
  };

  const stopRecording = () => {
    isRecordingRef.current = false;
    setIsRecording(false);
    onStatusChange('idle');

    // Stop audio pipeline first so no more chunks are sent
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(console.error);
      audioContextRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    // CRITICAL: Send {"action":"stop"} to the backend BEFORE closing.
    // The backend only flushes buffered audio and emits the "final" transcript
    // message when it receives this explicit stop signal. Simply closing the
    // socket causes WebSocketDisconnect on the backend and all buffered audio
    // is silently lost.
    if (webSocketRef.current && webSocketRef.current.readyState === WebSocket.OPEN) {
      try {
        webSocketRef.current.send(JSON.stringify({ action: 'stop' }));
        console.log('Sent stop signal to backend, waiting for final transcript...');
        // Give the backend up to 10s to process remaining audio and reply,
        // then close. The onmessage handler will receive the "final" message.
        setTimeout(() => {
          if (webSocketRef.current) {
            webSocketRef.current.close();
            webSocketRef.current = null;
          }
        }, 10000);
      } catch (err) {
        console.error('Failed to send stop signal:', err);
        webSocketRef.current.close();
        webSocketRef.current = null;
      }
    } else {
      webSocketRef.current = null;
    }
  };

  const handleFailure = (msg: string) => {
    isRecordingRef.current = false;
    setErrorMessage(msg);
    onStatusChange('error');
    setIsRecording(false);
    
    // Stop tracks and clean up context
    if (workletNodeRef.current) workletNodeRef.current.disconnect();
    if (audioContextRef.current) audioContextRef.current.close().catch(console.error);
    if (mediaStreamRef.current) mediaStreamRef.current.getTracks().forEach(track => track.stop());
    if (webSocketRef.current) webSocketRef.current.close();

    workletNodeRef.current = null;
    audioContextRef.current = null;
    mediaStreamRef.current = null;
    webSocketRef.current = null;
  };

  return (
    <div className="audio-recorder-container">
      {errorMessage && (
        <div className="alert alert-error backdrop-blur">
          <div className="alert-content">
            <span className="alert-icon">⚠️</span>
            <p className="alert-text">{errorMessage}</p>
          </div>
          <button className="alert-close-btn" onClick={() => setErrorMessage(null)}>✕</button>
        </div>
      )}

      <div className="recorder-controls">
        {!isRecording ? (
          <button 
            type="button"
            className="btn btn-primary btn-record"
            onClick={startRecording}
          >
            <span className="record-dot pulse"></span>
            Start Recording
          </button>
        ) : (
          <button 
            type="button"
            className="btn btn-danger btn-stop"
            onClick={stopRecording}
          >
            <span className="stop-square"></span>
            Stop Recording
          </button>
        )}
        
        {isRecording && (
          <div className="recording-status">
            <span className="recording-indicator"></span>
            <span className="recording-text">Streaming live audio (16kHz PCM)...</span>
          </div>
        )}
      </div>
    </div>
  );
};
