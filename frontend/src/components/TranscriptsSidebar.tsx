import React, { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "./AuthContext";

interface TranscriptItem {
  id: number;
  title: string;
  content: string;
  created_at: string;
  diarization_status?: 'none' | 'pending' | 'complete' | 'failed';
  diarized_segments?: any[];
}

interface TranscriptsSidebarProps {
  selectedId: number | null;
  onSelect: (transcript: TranscriptItem | null) => void;
  refreshTrigger: number;
  onRefresh: () => void;
}

export const TranscriptsSidebar: React.FC<TranscriptsSidebarProps> = ({
  selectedId,
  onSelect,
  refreshTrigger,
  onRefresh,
}) => {
  const { user, logout } = useAuth();
  const [transcripts, setTranscripts] = useState<TranscriptItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  const fetchTranscripts = async () => {
    setLoading(true);
    try {
      const res = await api.get("/transcription/");
      setTranscripts(res.data);
    } catch (err) {
      console.error("Failed to load transcripts history:", err);
    } finally {
      setLoading(false);
    }
  };

  // Re-fetch whenever refreshTrigger changes OR when the authenticated user changes.
  // Without 'user' in deps, logging out and back in within the same session
  // leaves the sidebar showing stale (empty) history from the previous mount.
  useEffect(() => {
    if (user) {
      fetchTranscripts();
    } else {
      setTranscripts([]);
    }
  }, [refreshTrigger, user]);

  const handleDelete = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation(); // Prevent selecting the item
    if (!window.confirm("Are you sure you want to delete this transcript?")) {
      return;
    }

    try {
      await api.delete(`/transcription/${id}`);
      if (selectedId === id) {
        onSelect(null);
      }
      fetchTranscripts();
      onRefresh();
    } catch (err) {
      console.error("Failed to delete transcript:", err);
      alert("Error deleting transcript. Please try again.");
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return dateStr;
    }
  };

  return (
    <aside className="transcripts-sidebar">
      <div className="sidebar-header">
        <h2>History</h2>
        {loading && <span className="loader-mini"></span>}
      </div>

      <div className="sidebar-list-container">
        {transcripts.length === 0 ? (
          <div className="sidebar-empty-state">
            No saved sessions yet.
            <br />
            Upload a file or record live audio to begin.
          </div>
        ) : (
          transcripts.map((item) => (
            <div
              key={item.id}
              className={`transcript-history-item ${selectedId === item.id ? "active" : ""}`}
              onClick={() => onSelect(item)}
            >
              <div className="history-item-details">
                <span className="history-item-title">{item.title}</span>
                <span className="history-item-date">{formatDate(item.created_at)}</span>
              </div>
              <button
                className="transcript-delete-btn"
                onClick={(e) => handleDelete(e, item.id)}
                title="Delete session"
              >
                ✕
              </button>
            </div>
          ))
        )}
      </div>

      {user && (
        <div className="sidebar-user-section">
          <div className="user-badge">
            <span className="user-badge-name">{user.username}</span>
            <span className="user-badge-email">{user.email}</span>
          </div>
          <button onClick={logout} className="sidebar-logout-btn">
            Logout
          </button>
        </div>
      )}
    </aside>
  );
};
