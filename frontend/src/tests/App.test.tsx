import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import App from '../App';

// Mock the AuthContext to simulate a pre-authenticated session
vi.mock('../components/AuthContext', () => ({
  AuthProvider: ({ children }: any) => <>{children}</>,
  useAuth: () => ({
    user: { id: 1, username: 'alice', email: 'alice@example.com' },
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

// Mock the TranscriptsSidebar to avoid unnecessary database mock requirements
vi.mock('../components/TranscriptsSidebar', () => ({
  TranscriptsSidebar: () => <div data-testid="sidebar">Mock Sidebar</div>
}));

describe('App Component - Incomplete Markdown Streaming Test', () => {
  beforeEach(() => {
    // Mock global fetch
    (window as any).fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders incomplete/partial markdown mid-stream gracefully without crashing', async () => {
    const unclosedMarkdown = '### 1. Executive Summary\n- **Incomplete bold text';
    
    const mockStreamReader = {
      read: vi.fn()
        .mockResolvedValueOnce({
          value: new TextEncoder().encode(unclosedMarkdown),
          done: false,
        })
        .mockResolvedValueOnce({
          value: undefined,
          done: true,
        }),
    };

    const mockResponse = {
      ok: true,
      body: {
        getReader: () => mockStreamReader,
      },
    };

    (window.fetch as any).mockResolvedValue(mockResponse);

    render(<App />);

    // 1. Enter some transcript to enable processing
    const textarea = screen.getByPlaceholderText(/Paste your meeting notes/i);
    fireEvent.change(textarea, { target: { value: 'This is a long transcript for testing.' } });

    // 2. Click process
    const processBtn = screen.getByText(/Process Transcript/i);
    await act(async () => {
      fireEvent.click(processBtn);
    });

    // 3. Assert that the unclosed markdown is rendered in the terminal screen
    const terminal = screen.getByText(/Incomplete bold text/i);
    expect(terminal).toBeInTheDocument();
    
    // Check that it rendered the structure (our completed layout is applied)
    expect(terminal.closest('.markdown-output')).toBeInTheDocument();
  });
});
