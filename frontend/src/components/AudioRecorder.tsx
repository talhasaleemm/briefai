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

      // 2. Connect WebSocket to the backend
      const wsUrl = `ws://localhost:8000/api/v1/transcription/ws`;
      const ws = new WebSocket(wsUrl);
      webSocketRef.current = ws;

      ws.onopen = () => {
        console.log('Transcription WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.transcript) {
            // Append segment updates or handle text aggregation
            transcriptBufferRef.current = data.transcript;
            onTranscriptChange(transcriptBufferRef.current);
          }
        } catch (err) {
          console.error('Error parsing WS message:', err);
        }
      };

      ws.onerror = (err) => {
        console.error('WebSocket Error:', err);
        handleFailure('WebSocket error occurred mid-stream.');
      };

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event);
        if (isRecordingRef.current) {
          handleFailure('WebSocket connection closed unexpectedly.');
        }
      };

      // 3. Initialize AudioContext and AudioWorklet
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      audioContextRef.current = audioContext;

      // Load the Worklet module from the public directory
      await audioContext.audioWorklet.addModule('/audio-processor.js');

      // Create nodes
      const sourceNode = audioContext.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(audioContext, 'audio-processor');
      workletNodeRef.current = workletNode;

      // Listen for downsampled PCM chunks from the worklet
      workletNode.port.onmessage = (event) => {
        const pcm16Data = event.data; // Int16Array
        if (ws.readyState === WebSocket.OPEN) {
          // Stream raw binary data to backend
          ws.send(pcm16Data.buffer);
        }
      };

      // Connect nodes
      sourceNode.connect(workletNode);
      workletNode.connect(audioContext.destination);

      // Start processing
      isRecordingRef.current = true;
      setIsRecording(true);
      onStatusChange('recording');
    } catch (err: any) {
      console.error('Recording initialization failed:', err);
      // Capture mic permission denial explicitly
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        handleFailure('Microphone permission was denied. Please allow microphone access in your browser settings to record live.');
      } else {
        handleFailure(`Failed to initialize recorder: ${err.message || err}`);
      }
    }
  };

  const stopRecording = () => {
    isRecordingRef.current = false;
    setIsRecording(false);
    onStatusChange('idle');

    // Close AudioWorklet and AudioContext
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(console.error);
      audioContextRef.current = null;
    }

    // Stop all media tracks
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    // Close WebSocket
    if (webSocketRef.current) {
      if (webSocketRef.current.readyState === WebSocket.OPEN) {
        // Send a final stop message if needed, or simply close
        webSocketRef.current.close();
      }
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
