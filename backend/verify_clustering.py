import asyncio
import os
import subprocess
import wave
from pathlib import Path
import json

import numpy as np
from briefai.services.diarization_service import DiarizationService

def generate_multi_speaker_wav(out_path: Path):
    """Generates a WAV file with two distinct speakers (using SAPI male/female voices if possible)."""
    # Just use SAPI with different pitches to simulate 2 speakers
    ps_script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile('{str(out_path).replace(chr(92), '/')}')

# Speaker 1
$synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Male)
$synth.Rate = -1
$synth.Speak("Hello, this is the first speaker. I am demonstrating the two-speaker separation test for BriefAI diarization.")

# Speaker 2
$synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female)
$synth.Rate = 0
$synth.Speak("And I am the second speaker. My voice has different acoustic characteristics, so I should be clustered into a second group.")

# Speaker 1 again
$synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Male)
$synth.Rate = -1
$synth.Speak("Excellent, I agree completely. Let's see if it successfully groups my segments together.")

$synth.Dispose()
Write-Host "OK"
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True)

def generate_single_speaker_wav(out_path: Path):
    """Generates a WAV file with exactly ONE speaker with long pauses to test anti-hallucination."""
    ps_script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile('{str(out_path).replace(chr(92), '/')}')
$synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female)

$synth.Speak("This is a single speaker test.")
$synth.Speak("There is nobody else in this room.")
$synth.Speak("This is a long dictated note. The system must not hallucinate a second speaker here.")
$synth.Speak("Just me speaking. End of note.")

$synth.Dispose()
Write-Host "OK"
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True)


async def run_verification():
    print("Initializing DiarizationService...")
    svc = DiarizationService()
    
    # Generate Audio
    multi_wav = Path("multi_speaker.wav")
    single_wav = Path("single_speaker.wav")
    
    print("Generating audio files...")
    generate_multi_speaker_wav(multi_wav)
    generate_single_speaker_wav(single_wav)
    
    from briefai.services.whisper_service import WhisperService
    tsvc = WhisperService()
    
    print("\nTranscribing multi_speaker.wav to get true timestamps...")
    multi_transcription_result = tsvc.transcribe_file(multi_wav, "en")
    multi_segments = multi_transcription_result.segments
    print(f"Got {len(multi_segments)} segments from Whisper.")
        
    import time
    print("\n--- Running HARD GATE #1: 2-Speaker Separation ---")
    t0 = time.perf_counter()
    multi_labeled = svc.diarize_segments(multi_wav, [s.model_dump() for s in multi_segments])
    t1 = time.perf_counter()
    print(json.dumps(multi_labeled, indent=2))
    print(f"Gate #1 CPU Processing Time: {t1 - t0:.2f} seconds")
    speakers_multi = set(s['speaker'] for s in multi_labeled)
    if len(speakers_multi) == 2:
        print("✅ Gate #1 Passed: Detected exactly 2 speakers.")
    else:
        print(f"❌ Gate #1 Failed: Detected {len(speakers_multi)} speakers.")
        
    print("\nTranscribing single_speaker.wav to get true timestamps...")
    single_transcription_result = tsvc.transcribe_file(single_wav, "en")
    single_segments = single_transcription_result.segments
    print(f"Got {len(single_segments)} segments from Whisper.")

    print("\n--- Running HARD GATE #2: 1-Speaker Anti-Hallucination ---")
    t0 = time.perf_counter()
    single_labeled = svc.diarize_segments(single_wav, [s.model_dump() for s in single_segments])
    t1 = time.perf_counter()
    print(json.dumps(single_labeled, indent=2))
    print(f"Gate #2 CPU Processing Time: {t1 - t0:.2f} seconds")
    speakers_single = set(s['speaker'] for s in single_labeled)
    if len(speakers_single) == 1:
        print("✅ Gate #2 Passed: Detected exactly 1 speaker. No hallucination.")
    else:
        print(f"❌ Gate #2 Failed: Detected {len(speakers_single)} speakers (hallucination).")

if __name__ == "__main__":
    asyncio.run(run_verification())
