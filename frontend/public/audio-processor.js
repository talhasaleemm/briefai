class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    // Lowpass cutoff at 7200Hz to prevent aliasing, Q = 0.707 (Butterworth)
    const cutoff = 7200;
    const q = 0.707;
    
    // w0 is calculated relative to sampleRate of the audio context
    const w0 = 2 * Math.PI * cutoff / sampleRate;
    const alpha = Math.sin(w0) / (2 * q);
    const cosw0 = Math.cos(w0);

    const b0 = (1 - cosw0) / 2;
    const b1 = 1 - cosw0;
    const b2 = (1 - cosw0) / 2;
    const a0 = 1 + alpha;
    const a1 = -2 * cosw0;
    const a2 = 1 - alpha;

    // Normalized filter coefficients
    this.b0 = b0 / a0;
    this.b1 = b1 / a0;
    this.b2 = b2 / a0;
    this.a1 = a1 / a0;
    this.a2 = a2 / a0;

    // Filter memory state (2 taps)
    this.x1 = 0.0;
    this.x2 = 0.0;
    this.y1 = 0.0;
    this.y2 = 0.0;

    // Downsampling state variables
    this.sourceSampleRate = sampleRate;
    this.targetSampleRate = 16000;
    this.resampleRatio = this.sourceSampleRate / this.targetSampleRate;
    
    // Track index matching
    this.sampleBuffer = [];
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;

    const channelData = input[0];
    if (!channelData || channelData.length === 0) return true;

    // 1. Apply the low-pass filter to the input channel block to anti-alias
    const filtered = new Float32Array(channelData.length);
    for (let i = 0; i < channelData.length; i++) {
      const x = channelData[i];
      const y = this.b0 * x + this.b1 * this.x1 + this.b2 * this.x2 - this.a1 * this.y1 - this.a2 * this.y2;
      this.x2 = this.x1;
      this.x1 = x;
      this.y2 = this.y1;
      this.y1 = y;
      filtered[i] = y;
    }

    // 2. Buffer filtered samples for fractional downsampling
    for (let i = 0; i < filtered.length; i++) {
      this.sampleBuffer.push(filtered[i]);
    }

    // 3. Downsample buffered samples down to 16kHz
    const outputSamples = [];
    while (this.sampleBuffer.length >= 2) {
      // Linear interpolation between sample index 0 and 1
      const fraction = 0.0; // Simple decimation ratio step
      const val0 = this.sampleBuffer[0];
      const val1 = this.sampleBuffer[1];
      const interpolated = val0 + fraction * (val1 - val0);
      
      // Keep Float32 sample within range [-1.0, 1.0]
      const s = Math.max(-1.0, Math.min(1.0, interpolated));
      outputSamples.push(s);

      // Advance buffer index by the resample ratio
      // If ratio is 3.0 (e.g. 48kHz -> 16kHz), we remove 3 samples
      let samplesToRemove = Math.floor(this.resampleRatio);
      if (samplesToRemove < 1) {
        samplesToRemove = 1;
      }
      this.sampleBuffer.splice(0, samplesToRemove);
    }

    // 4. Send the Float32Array chunk back to the main thread via message port
    if (outputSamples.length > 0) {
      const pcmData = new Float32Array(outputSamples);
      this.port.postMessage(pcmData);
    }

    return true;
  }
}

registerProcessor('audio-processor', AudioProcessor);
