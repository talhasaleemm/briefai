import React, { useState, useRef } from 'react';
import { api } from '../api/client';

interface AudioUploaderProps {
  onUploadSuccess: (transcriptId: number, transcriptText: string, status: string, segments: any[]) => void;
  onUploadError: (error: string) => void;
}

export const AudioUploader: React.FC<AudioUploaderProps> = ({
  onUploadSuccess,
  onUploadError
}) => {
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setProgress(0);
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      // Simulate progress for large files since actual progress events 
      // are only for the network upload, not the whisper transcription time
      const progressInterval = setInterval(() => {
        setProgress(p => Math.min(p + (90 - p) / 10, 95));
      }, 500);

      const response = await api.post('/transcription/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      
      clearInterval(progressInterval);
      setProgress(100);
      
      const data = response.data;
      onUploadSuccess(
        data.id, 
        data.transcript, 
        data.diarization_status || 'none', 
        data.diarized_segments || []
      );
    } catch (err: any) {
      console.error('Upload failed:', err);
      let errMsg = 'Upload failed. ';
      if (err.response?.data?.detail) {
        errMsg += typeof err.response.data.detail === 'string' 
          ? err.response.data.detail 
          : JSON.stringify(err.response.data.detail);
      } else {
        errMsg += err.message || 'Unknown error';
      }
      onUploadError(errMsg);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="audio-uploader-container">
      <div 
        className="upload-dropzone"
        onClick={() => !isUploading && fileInputRef.current?.click()}
        style={{
          border: '2px dashed rgba(255, 255, 255, 0.2)',
          borderRadius: '8px',
          padding: '2rem',
          textAlign: 'center',
          cursor: isUploading ? 'not-allowed' : 'pointer',
          background: 'rgba(0, 0, 0, 0.2)',
          transition: 'all 0.2s',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '150px'
        }}
      >
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={handleFileSelect} 
          style={{ display: 'none' }}
          accept=".wav,.mp3,.flac,.ogg,.opus,.m4a,.webm,.mp4,.aac"
        />
        
        {isUploading ? (
          <div className="uploading-state">
            <div className="spinner-border text-primary" role="status" style={{ marginBottom: '1rem' }}></div>
            <p>Transcribing audio... ({Math.round(progress)}%)</p>
            <p style={{ fontSize: '0.8rem', color: '#888' }}>This may take a few minutes for long files.</p>
          </div>
        ) : (
          <div className="idle-state">
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📁</div>
            <p style={{ fontWeight: 'bold' }}>Click to select audio file</p>
            <p style={{ fontSize: '0.8rem', color: '#888' }}>
              WAV, MP3, FLAC, M4A (Max 50MB)
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
