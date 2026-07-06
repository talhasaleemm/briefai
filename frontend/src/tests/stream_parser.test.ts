import { describe, it, expect, vi } from 'vitest';

// The streaming parser logic we use in the App component
async function parseStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onChunk: (chunk: string) => void
) {
  const decoder = new TextDecoder('utf-8');
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    onChunk(chunk);
  }
}

describe('SSE Stream Parser Unit Tests', () => {
  it('correctly decodes and aggregates incoming binary chunks', async () => {
    const mockChunks = [
      new TextEncoder().encode('Hello '),
      new TextEncoder().encode('world! '),
      new TextEncoder().encode('This is BriefAI.'),
    ];

    let chunkIndex = 0;
    const mockReader = {
      read: vi.fn().mockImplementation(async () => {
        if (chunkIndex < mockChunks.length) {
          const value = mockChunks[chunkIndex++];
          return { value, done: false };
        }
        return { value: undefined, done: true };
      }),
    } as unknown as ReadableStreamDefaultReader<Uint8Array>;

    const chunksReceived: string[] = [];
    const onChunkCallback = (chunk: string) => {
      chunksReceived.push(chunk);
    };

    await parseStream(mockReader, onChunkCallback);

    expect(mockReader.read).toHaveBeenCalledTimes(4); // 3 data chunks + 1 final done chunk
    expect(chunksReceived).toEqual(['Hello ', 'world! ', 'This is BriefAI.']);
    expect(chunksReceived.join('')).toBe('Hello world! This is BriefAI.');
  });

  it('handles empty streams gracefully', async () => {
    const mockReader = {
      read: vi.fn().mockResolvedValue({ value: undefined, done: true }),
    } as unknown as ReadableStreamDefaultReader<Uint8Array>;

    const chunksReceived: string[] = [];
    const onChunkCallback = (chunk: string) => {
      chunksReceived.push(chunk);
    };

    await parseStream(mockReader, onChunkCallback);

    expect(mockReader.read).toHaveBeenCalledOnce();
    expect(chunksReceived).toHaveLength(0);
  });
});
