import { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import { agentsApi } from '../../api';
import type { AgentConfig, InvokeRequest } from '../../types';
import './AgentCard.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface AgentCardProps {
  agent: AgentConfig;
  personaName?: string;
  onEdit?: () => void;
}

export function AgentCard({ agent, personaName, onEdit }: AgentCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [invoking, setInvoking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (expanded && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, expanded]);

  const handleInvoke = async () => {
    const text = input.trim();
    if (!text || invoking) return;

    const userMsg: Message = { role: 'user', content: text };
    const history = messages.map(m => ({ role: m.role, content: m.content }));

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setInvoking(true);
    setError(null);

    try {
      const req: InvokeRequest = { message: text, history };
      const res = await agentsApi.invoke(agent.agent_id, req);
      const reply = res.data.response ?? res.data.message ?? '';
      setMessages(prev => [...prev, { role: 'assistant', content: reply }]);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Invocation failed. Is the backend running?';
      setError(msg);
      // Roll back the optimistic user message
      setMessages(prev => prev.slice(0, -1));
      setInput(text);
    } finally {
      setInvoking(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleInvoke();
    }
  };

  const handleClearHistory = () => {
    setMessages([]);
    setError(null);
  };

  return (
    <div className={`agent-card ${expanded ? 'expanded' : ''}`}>
      {/* Card header */}
      <div className="agent-card-header">
        <div className="agent-card-avatar">
          {agent.name.charAt(0).toUpperCase()}
        </div>

        <div className="agent-card-info">
          <div className="agent-card-name">{agent.name}</div>
          <div className="agent-card-meta">
            {agent.role && (
              <span className="agent-card-role">{agent.role}</span>
            )}
            <span className="agent-card-model">{agent.model}</span>
            {personaName && (
              <span className="agent-card-persona">persona: {personaName}</span>
            )}
            {agent.memory_enabled && (
              <span className="agent-card-memory-badge">memory</span>
            )}
          </div>
        </div>

        <div className="agent-card-actions">
          {onEdit && (
            <button className="card-action-btn" onClick={onEdit} title="Edit agent">
              ✏️
            </button>
          )}
          {messages.length > 0 && expanded && (
            <button className="card-action-btn" onClick={handleClearHistory} title="Clear history">
              🗑️
            </button>
          )}
          <button
            className="card-invoke-btn"
            onClick={() => {
              setExpanded(v => !v);
              setTimeout(() => inputRef.current?.focus(), 80);
            }}
          >
            {expanded ? '▾ Close' : '▸ Invoke'}
          </button>
        </div>
      </div>

      {/* Expanded chat panel */}
      {expanded && (
        <div className="agent-card-chat">
          <div className="agent-chat-messages">
            {messages.length === 0 && !invoking && (
              <div className="agent-chat-empty">
                Send a message to invoke <strong>{agent.name}</strong>.
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`chat-bubble ${msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-agent'}`}
              >
                <span className="chat-bubble-role">
                  {msg.role === 'user' ? 'You' : agent.name}
                </span>
                <p className="chat-bubble-content">{msg.content}</p>
              </div>
            ))}

            {invoking && (
              <div className="chat-bubble chat-bubble-agent chat-bubble-loading">
                <span className="chat-bubble-role">{agent.name}</span>
                <span className="chat-typing">
                  <span /><span /><span />
                </span>
              </div>
            )}

            {error && (
              <div className="chat-error">
                <span>⚠</span> {error}
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          <div className="agent-chat-input-row">
            <textarea
              ref={inputRef}
              className="agent-chat-input"
              placeholder={`Message ${agent.name}… (Enter to send, Shift+Enter for newline)`}
              rows={2}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={invoking}
            />
            <button
              className="agent-chat-send"
              onClick={handleInvoke}
              disabled={invoking || !input.trim()}
              title="Send"
            >
              {invoking ? '…' : '→'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
