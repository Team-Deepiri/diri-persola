import { type ChangeEvent } from 'react';
import type { Session } from '../../types';
import './SessionSelector.css';

interface SessionSelectorProps {
  sessions: Session[];
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onCreate: () => void;
  loading?: boolean;
}

function relativeTime(iso: string | null): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function sessionLabel(s: Session): string {
  const short = s.session_id.length > 24 ? `…${s.session_id.slice(-20)}` : s.session_id;
  const count = s.message_count === 1 ? '1 msg' : `${s.message_count} msgs`;
  const when = relativeTime(s.last_message_at ?? s.created_at);
  return `${short} · ${count}${when ? ` · ${when}` : ''}`;
}

export function SessionSelector({
  sessions,
  activeSessionId,
  onSelect,
  onCreate,
  loading,
}: SessionSelectorProps) {
  const sorted = [...sessions].sort((a, b) => {
    const at = a.last_message_at ?? a.created_at;
    const bt = b.last_message_at ?? b.created_at;
    return new Date(bt).getTime() - new Date(at).getTime();
  });

  return (
    <div className="session-selector">
      {sessions.length === 0 ? (
        <span className="session-selector-empty">No sessions yet</span>
      ) : (
        <select
          className="session-select"
          value={activeSessionId ?? ''}
          onChange={(e: ChangeEvent<HTMLSelectElement>) => onSelect(e.target.value)}
          disabled={loading}
          aria-label="Active session"
        >
          <option value="" disabled>
            — pick a session —
          </option>
          {sorted.map(s => (
            <option key={s.id} value={s.session_id}>
              {sessionLabel(s)}
            </option>
          ))}
        </select>
      )}

      <button
        className="session-new-btn"
        onClick={onCreate}
        disabled={loading}
        title="Start a new session"
      >
        + New
      </button>
    </div>
  );
}
