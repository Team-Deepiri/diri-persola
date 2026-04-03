import { useState, useEffect, useCallback } from 'react';
import { agentsApi, sessionsApi } from '../../api';
import type { AgentConfig, Session, Message } from '../../types';
import { MessageList, PAGE_SIZE } from './MessageList';
import { MessageInput } from './MessageInput';
import './ConversationView.css';

function newSessionId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return `session-${crypto.randomUUID()}`;
  }
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

interface OptimisticMessage extends Omit<Message, 'id'> {
  id: string;
  _optimistic?: true;
}

export function ConversationView() {
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  const [messages, setMessages] = useState<Message[]>([]);
  const [msgsLoading, setMsgsLoading] = useState(false);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const selectedAgent = agents.find(a => a.agent_id === selectedAgentId) ?? null;

  // ── Load agents on mount ──────────────────────────────────────────────────
  useEffect(() => {
    agentsApi.list()
      .then(r => {
        setAgents(r.data);
        if (r.data.length > 0) setSelectedAgentId(r.data[0].agent_id);
      })
      .catch(err => console.error('Failed to load agents:', err))
      .finally(() => setAgentsLoading(false));
  }, []);

  // ── Load sessions when agent changes ──────────────────────────────────────
  useEffect(() => {
    if (!selectedAgentId) {
      setSessions([]);
      setActiveSessionId(null);
      return;
    }
    setSessionsLoading(true);
    setSessions([]);
    setActiveSessionId(null);
    setMessages([]);

    sessionsApi.listByAgent(selectedAgentId)
      .then(r => {
        setSessions(r.data);
        // Auto-select the most-recently-active session
        if (r.data.length > 0) {
          const sorted = [...r.data].sort((a, b) => {
            const at = a.last_message_at ?? a.created_at;
            const bt = b.last_message_at ?? b.created_at;
            return new Date(bt).getTime() - new Date(at).getTime();
          });
          setActiveSessionId(sorted[0].session_id);
        }
      })
      .catch(err => console.error('Failed to load sessions:', err))
      .finally(() => setSessionsLoading(false));
  }, [selectedAgentId]);

  // ── Load messages when session changes ────────────────────────────────────
  const loadMessages = useCallback((sessionId: string) => {
    setMsgsLoading(true);
    setMessages([]);
    setVisibleCount(PAGE_SIZE);

    sessionsApi.getMessages(sessionId)
      .then(r => {
        setMessages(r.data);
        // Start at the end
        setVisibleCount(Math.max(PAGE_SIZE, r.data.length));
      })
      .catch(err => console.error('Failed to load messages:', err))
      .finally(() => setMsgsLoading(false));
  }, []);

  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }
    loadMessages(activeSessionId);
  }, [activeSessionId, loadMessages]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleNewSession = () => {
    const sid = newSessionId();
    setActiveSessionId(sid);
    setMessages([]);
    setVisibleCount(PAGE_SIZE);
    setSendError(null);
  };

  const handleSend = async (text: string) => {
    if (!selectedAgentId || !activeSessionId) return;
    setSending(true);
    setSendError(null);

    // Optimistic user message
    const optimisticId = `opt-${Date.now()}`;
    const optimistic: OptimisticMessage = {
      id: optimisticId,
      session_id: activeSessionId,
      role: 'user',
      content: text,
      metadata: {},
      tokens_used: null,
      model: null,
      created_at: new Date().toISOString(),
      _optimistic: true,
    };
    setMessages(prev => [...prev, optimistic as Message]);

    try {
      await agentsApi.invoke(selectedAgentId, {
        message: text,
        session_id: activeSessionId,
      });

      // Refresh messages from the server (gets both user + assistant)
      const refreshed = await sessionsApi.getMessages(activeSessionId);
      setMessages(refreshed.data);
      setVisibleCount(v => Math.max(v, refreshed.data.length));

      // Refresh session list so message_count / last_message_at update
      const updatedSessions = await sessionsApi.listByAgent(selectedAgentId);
      setSessions(updatedSessions.data);
    } catch (err: unknown) {
      // Roll back optimistic message
      setMessages(prev => prev.filter(m => m.id !== optimisticId));
      const msg =
        err instanceof Error ? err.message : 'Failed to send message. Is the backend running?';
      setSendError(msg);
    } finally {
      setSending(false);
    }
  };

  const handleLoadMore = () => {
    setVisibleCount(v => v + PAGE_SIZE);
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="conversation-view">
      {/* Header */}
      <div className="conv-header">
        <div className="conv-header-left">
          <h2 className="conv-header-title">Conversations</h2>

          {agentsLoading ? (
            <span className="conv-agent-loading">Loading agents…</span>
          ) : agents.length === 0 ? (
            <span className="conv-no-agents">
              No agents found — create one in the Agents page first.
            </span>
          ) : (
            <div className="conv-agent-picker">
              <label className="conv-agent-label" htmlFor="agent-select">Agent</label>
              <select
                id="agent-select"
                className="conv-agent-select"
                value={selectedAgentId ?? ''}
                onChange={e => setSelectedAgentId(e.target.value)}
                disabled={sending}
              >
                {agents.map(a => (
                  <option key={a.agent_id} value={a.agent_id}>
                    {a.name} ({a.model})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {selectedAgent && (
          <div className="conv-header-right">
            <span className="conv-agent-role">{selectedAgent.role}</span>
            {sessionsLoading && (
              <span className="conv-sessions-loading">loading sessions…</span>
            )}
          </div>
        )}
      </div>

      {/* Error banner */}
      {sendError && (
        <div className="conv-error-banner">
          <span>⚠</span>
          {sendError}
          <button className="conv-error-dismiss" onClick={() => setSendError(null)}>✕</button>
        </div>
      )}

      {/* Message list */}
      <MessageList
        messages={messages}
        visibleCount={visibleCount}
        agentName={selectedAgent?.name ?? 'Agent'}
        loading={msgsLoading}
        sending={sending}
        onLoadMore={handleLoadMore}
      />

      {/* Input bar */}
      <MessageInput
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSessionSelect={setActiveSessionId}
        onNewSession={handleNewSession}
        onSend={handleSend}
        sending={sending}
        disabled={!selectedAgentId || agentsLoading}
      />
    </div>
  );
}
