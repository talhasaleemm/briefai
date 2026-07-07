/**
 * AudioProcessor Worklet — real-time downsample to 16 kHz for Whisper
 *
 * Approach: fractional-accumulator decimation with linear interpolation.
 *   - Applies a 7200 Hz Butterworth low-pass to prevent aliasing before decimation.
 *   - Accumulates samples and posts Float32Array chunks every ~100 ms to the main thread.
 *   - Works correctly for any integer or fractional ratio (44.1 kHz, 48 kHz, etc.)
 */
class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    this.targetSampleRate = 16000;
    this.sourceSampleRate = sampleRate; // global from AudioWorkletGlobalScope

    // Butterworth low-pass at 7200 Hz (Nyquist for 16 kHz output)
    const cutoff = 7200;
    const q = 0.707;
    const w0 = (2 * Math.PI * cutoff) / sampleRate;
    const alpha = Math.sin(w0) / (2 * q);
    const cosw0 = Math.cos(w0);

    const b0 = (1 - cosw0) / 2;
    const b1 = 1 - cosw0;
    const b2 = (1 - cosw0) / 2;
    const a0 = 1 + alpha;
    const a1n = -2 * cosw0; // a1 (negated in the difference equation)
    const a2 = 1 - alpha;

    this.b0 = b0 / a0;
    this.b1 = b1 / a0;
    this.b2 = b2 / a0;
    this.a1 = a1n / a0;
    this.a2 = a2 / a0;

    // IIR filter state
    this.x1 = 0; this.x2 = 0;
    this.y1 = 0; this.y2 = 0;

    // Fractional accumulator: tracks our position in the source stream
    // in units of source samples. We advance by resampleRatio each output sample.
    this.accumulator = 0;

    // Ring buffer for filtered source samples (simple array for clarity)
    this.filtered = [];

    // Output chunk accumulation — post every TARGET_CHUNK_SAMPLES output samples
    // 100 ms at 16 kHz = 1600 samples
    this.TARGET_CHUNK_SAMPLES = 1600;
    this.outputChunk = [];
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0] || input[0].length === 0) return true;

    const channelData = input[0];

    // 1. Apply Butterworth low-pass filter sample-by-sample
    for (let i = 0; i < channelData.length; i++) {
      const x = channelData[i];
      const y =
        this.b0 * x +
        this.b1 * this.x1 +
        this.b2 * this.x2 -
        this.a1 * this.y1 -
        this.a2 * this.y2;
      this.x2 = this.x1; this.x1 = x;
      this.y2 = this.y1; this.y1 = y;
      this.filtered.push(y);
    }

    const ratio = this.sourceSampleRate / this.targetSampleRate; // e.g. 3.0 for 48k->16k

    // 2. Fractional-accumulator decimation with linear interpolation
    while (true) {
      // We need at least floor(accumulator)+1 samples available to interpolate
      const idx0 = Math.floor(this.accumulator);
      const idx1 = idx0 + 1;

      if (idx1 >= this.filtered.length) break; // not enough data yet

      // Linear interpolation between idx0 and idx1
      const frac = this.accumulator - idx0;
      const s = this.filtered[idx0] * (1 - frac) + this.filtered[idx1] * frac;

      this.outputChunk.push(Math.max(-1, Math.min(1, s)));
      this.accumulator += ratio;

      // 3. Post chunk when we have enough samples
      if (this.outputChunk.length >= this.TARGET_CHUNK_SAMPLES) {
        this.port.postMessage(new Float32Array(this.outputChunk));
        this.outputChunk = [];
      }
    }

    // 4. Discard consumed source samples to keep filtered array small
    const consumed = Math.min(Math.floor(this.accumulator), this.filtered.length);
    if (consumed > 0) {
      this.filtered.splice(0, consumed);
      this.accumulator -= consumed;
    }

    return true;
  }
}

registerProcessor('audio-processor', AudioProcessor);
