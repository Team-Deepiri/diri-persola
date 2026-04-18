import { useEffect, useRef } from 'react';
import type { Message } from '../../types';
import './MessageList.css';

interface MessageListProps {
  messages: Message[];
  visibleCount: number;
  agentName: string;
  loading: boolean;
  sending: boolean;
  onLoadMore: () => void;
}

const PAGE_SIZE = 50;

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}

/** Insert date-separator markers between messages on different calendar days. */
function groupByDay(messages: Message[]): Array<Message | { __separator: string }> {
  const out: Array<Message | { __separator: string }> = [];
  let lastDate = '';
  for (const msg of messages) {
    const day = new Date(msg.created_at).toDateString();
    if (day !== lastDate) {
      out.push({ __separator: formatDate(msg.created_at) });
      lastDate = day;
    }
    out.push(msg);
  }
  return out;
}

function isSeparator(item: Message | { __separator: string }): item is { __separator: string } {
  return '__separator' in item;
}

export function MessageList({
  messages,
  visibleCount,
  agentName,
  loading,
  sending,
  onLoadMore,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when new messages arrive (unless user scrolled up)
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    if (isNearBottom || sending) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages.length, sending]);

  if (loading) {
    return (
      <div className="message-list message-list-loading" ref={listRef}>
        <div className="msg-loading-indicator">
          <span className="msg-spinner" />
          Loading messages…
        </div>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="message-list message-list-empty" ref={listRef}>
        <div className="msg-empty-state">
          <div className="msg-empty-icon">💬</div>
          <p className="msg-empty-title">No messages yet</p>
          <p className="msg-empty-sub">Send a message to start the conversation.</p>
        </div>
      </div>
    );
  }

  const totalCount = messages.length;
  const startIdx = Math.max(0, totalCount - visibleCount);
  const visible = messages.slice(startIdx);
  const hasMore = startIdx > 0;
  const items = groupByDay(visible);

  return (
    <div className="message-list" ref={listRef}>
      {hasMore && (
        <div className="msg-load-more">
          <button className="msg-load-more-btn" onClick={onLoadMore}>
            ↑ Load earlier messages ({startIdx} hidden)
          </button>
        </div>
      )}

      {items.map((item, i) => {
        if (isSeparator(item)) {
          return (
            <div key={`sep-${i}`} className="msg-day-separator">
              <span>{item.__separator}</span>
            </div>
          );
        }

        const msg = item;

        if (msg.role === 'system') {
          return (
            <div key={msg.id} className="msg-system">
              <span className="msg-system-label">system</span>
              <span className="msg-system-content">{msg.content}</span>
            </div>
          );
        }

        const isUser = msg.role === 'user';

        return (
          <div
            key={msg.id}
            className={`msg-row ${isUser ? 'msg-row-user' : 'msg-row-agent'}`}
          >
            {!isUser && (
              <div className="msg-avatar msg-avatar-agent" title={agentName}>
                {agentName.charAt(0).toUpperCase()}
              </div>
            )}

            <div className="msg-bubble-group">
              <div className="msg-meta-top">
                <span className="msg-role-label">
                  {isUser ? 'You' : agentName}
                </span>
                <span className="msg-time">{formatTime(msg.created_at)}</span>
              </div>

              <div className={`msg-bubble ${isUser ? 'msg-bubble-user' : 'msg-bubble-agent'}`}>
                <p className="msg-content">{msg.content}</p>
              </div>

              {!isUser && (msg.model || msg.tokens_used != null) && (
                <div className="msg-meta-bottom">
                  {msg.model && (
                    <span className="msg-model-tag">{msg.model}</span>
                  )}
                  {msg.tokens_used != null && (
                    <span className="msg-tokens-tag">{msg.tokens_used} tokens</span>
                  )}
                </div>
              )}
            </div>

            {isUser && (
              <div className="msg-avatar msg-avatar-user" title="You">
                U
              </div>
            )}
          </div>
        );
      })}

      {/* Typing indicator */}
      {sending && (
        <div className="msg-row msg-row-agent">
          <div className="msg-avatar msg-avatar-agent">{agentName.charAt(0).toUpperCase()}</div>
          <div className="msg-bubble-group">
            <div className="msg-meta-top">
              <span className="msg-role-label">{agentName}</span>
            </div>
            <div className="msg-bubble msg-bubble-agent msg-typing">
              <span /><span /><span />
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}

export { PAGE_SIZE };
