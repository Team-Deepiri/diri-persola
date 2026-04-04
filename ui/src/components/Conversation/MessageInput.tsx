import { useRef, useState, type KeyboardEvent, type ChangeEvent } from 'react';
import { SessionSelector } from './SessionSelector';
import type { Session } from '../../types';
import './MessageInput.css';

interface MessageInputProps {
  sessions: Session[];
  activeSessionId: string | null;
  onSessionSelect: (sessionId: string) => void;
  onNewSession: () => void;
  onSend: (text: string) => void;
  sending: boolean;
  disabled: boolean;
}

const MAX_ROWS = 6;
const LINE_HEIGHT = 22; // px, matches CSS

export function MessageInput({
  sessions,
  activeSessionId,
  onSessionSelect,
  onNewSession,
  onSend,
  sending,
  disabled,
}: MessageInputProps) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || sending || disabled) return;
    onSend(trimmed);
    setText('');
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    // Auto-grow
    const el = e.target;
    el.style.height = 'auto';
    const maxHeight = MAX_ROWS * LINE_HEIGHT + 24; // 24 = top+bottom padding
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  };

  const canSend = text.trim().length > 0 && !sending && !disabled;
  const noSession = !activeSessionId;

  return (
    <div className="message-input-bar">
      <div className="message-input-toolbar">
        <SessionSelector
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelect={onSessionSelect}
          onCreate={onNewSession}
          loading={sending}
        />
        {noSession && (
          <span className="message-input-hint">← select or create a session to chat</span>
        )}
      </div>

      <div className={`message-input-row ${disabled || noSession ? 'is-disabled' : ''}`}>
        <textarea
          ref={textareaRef}
          className="message-textarea"
          placeholder={
            noSession
              ? 'Create or select a session above…'
              : 'Send a message… (Enter to send, Shift+Enter for newline)'
          }
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled || noSession || sending}
          rows={1}
          aria-label="Message"
        />

        <button
          className={`message-send-btn ${sending ? 'is-sending' : ''}`}
          onClick={handleSend}
          disabled={!canSend}
          aria-label="Send message"
          title="Send (Enter)"
        >
          {sending ? (
            <span className="send-spinner" />
          ) : (
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
