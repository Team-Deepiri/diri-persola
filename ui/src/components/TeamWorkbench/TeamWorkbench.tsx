import { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import './TeamWorkbench.css';

type Personality = {
  role: string;
  name: string;
  tagline: string;
  strengths: string[];
  collaboration_style: string;
  system_directive?: string;
};

type WorkflowStep = {
  role: string;
  task: string;
  output: string;
  tool_calls?: Array<Record<string, unknown>>;
  parallel_group?: string | null;
  duration_ms?: number | null;
};

type TeamInvokeResponse = {
  session_id: string;
  response: string;
  personalities_used: string[];
  delegation_plan: { specialists: string[]; scores: Record<string, number>; coordinator?: string };
  workflow: { steps: WorkflowStep[]; status: string };
  tool_results: Array<Record<string, unknown>>;
  runtime_mode?: string;
  runtime?: { langgraph?: boolean; persisted?: boolean };
};

type SessionSummary = {
  session_id: string;
  name: string | null;
  message_count: number;
  updated_at: string | null;
};

type SessionDetail = {
  session_id: string;
  memory_snapshot: Record<string, unknown>;
  memory_entries: Array<{ key: string; value: string; tags: string[]; source_role?: string }>;
  workflows: Array<{
    id: string;
    goal: string;
    status: string;
    final_response?: string;
    personalities_used: string[];
    delegation_plan: TeamInvokeResponse['delegation_plan'];
    tool_results: Array<Record<string, unknown>>;
    steps: WorkflowStep[];
  }>;
};

type RuntimeInfo = {
  langgraph_available: boolean;
  parallel_tools: boolean;
  redis_memory: boolean;
  persistence: string;
};

const api = axios.create({ baseURL: '/api/v1', headers: { 'Content-Type': 'application/json' } });

const ROLE_COLORS: Record<string, string> = {
  coordinator: '#7c3aed',
  analyst: '#0ea5e9',
  creative: '#f59e0b',
  executor: '#10b981',
  empath: '#ec4899',
};

function roleColor(role: string) {
  return ROLE_COLORS[role] ?? '#64748b';
}

export function TeamWorkbench() {
  const [personalities, setPersonalities] = useState<Personality[]>([]);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [task, setTask] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionDetail, setSessionDetail] = useState<SessionDetail | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TeamInvokeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [memoryQuery, setMemoryQuery] = useState('');
  const [memoryHits, setMemoryHits] = useState<Array<Record<string, unknown>>>([]);
  const [useLanggraph, setUseLanggraph] = useState(true);

  const loadSessions = useCallback(async () => {
    try {
      const { data } = await api.get<SessionSummary[]>('/teams/sessions');
      setSessions(data);
    } catch {
      setSessions([]);
    }
  }, []);

  const loadSessionDetail = useCallback(async (id: string) => {
    try {
      const { data } = await api.get<SessionDetail>(`/teams/sessions/${id}`);
      setSessionDetail(data);
    } catch {
      setSessionDetail(null);
    }
  }, []);

  useEffect(() => {
    api.get<Personality[]>('/teams/personalities').then((r) => setPersonalities(r.data)).catch(() => {});
    api.get<RuntimeInfo>('/teams/runtime').then((r) => setRuntime(r.data)).catch(() => {});
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (sessionId) loadSessionDetail(sessionId);
  }, [sessionId, loadSessionDetail, result]);

  const delegationScores = useMemo(() => {
    if (!result?.delegation_plan?.scores) return [];
    return Object.entries(result.delegation_plan.scores).sort((a, b) => b[1] - a[1]);
  }, [result]);

  const runTeam = async () => {
    if (!task.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.post<TeamInvokeResponse>('/teams/invoke', {
        task,
        session_id: sessionId,
        use_langgraph: useLanggraph,
      });
      setResult(data);
      setSessionId(data.session_id);
      await loadSessions();
    } catch (e: unknown) {
      if (axios.isAxiosError(e)) {
        setError(e.response?.data?.detail ?? e.message);
      } else {
        setError(e instanceof Error ? e.message : 'Team invoke failed');
      }
    } finally {
      setLoading(false);
    }
  };

  const searchMemory = async () => {
    if (!sessionId || !memoryQuery.trim()) return;
    const { data } = await api.post<{ results: Array<Record<string, unknown>> }>(
      `/teams/sessions/${sessionId}/memory/search`,
      { query: memoryQuery },
    );
    setMemoryHits(data.results);
  };

  const activeWorkflow = result?.workflow ?? sessionDetail?.workflows?.[0];

  return (
    <div className="team-workbench">
      <header className="team-header">
        <div>
          <h1>Team Workbench</h1>
          <p>Multi-personality orchestration — parallel specialists, tool execution, Redis memory, persisted workflows.</p>
        </div>
        {runtime && (
          <div className="runtime-badges">
            <span className={runtime.langgraph_available ? 'badge on' : 'badge'}>LangGraph {runtime.langgraph_available ? 'on' : 'fallback'}</span>
            <span className="badge on">Parallel tools</span>
            <span className="badge on">{runtime.persistence}</span>
          </div>
        )}
      </header>

      <div className="team-layout">
        <aside className="team-sidebar">
          <h2>Sessions</h2>
          <ul className="session-list">
            {sessions.map((s) => (
              <li key={s.session_id}>
                <button
                  type="button"
                  className={sessionId === s.session_id ? 'active' : ''}
                  onClick={() => setSessionId(s.session_id)}
                >
                  <span className="sid">{s.session_id.slice(0, 8)}…</span>
                  <span className="meta">{s.message_count} msgs</span>
                </button>
              </li>
            ))}
            {!sessions.length && <li className="empty">No sessions yet</li>}
          </ul>
        </aside>

        <main className="team-main">
          <section className="team-personalities">
            <h2>Personalities</h2>
            <div className="personality-grid">
              {personalities.map((p) => (
                <article key={p.role} className="personality-card" style={{ borderTopColor: roleColor(p.role) }}>
                  <h3>{p.name}</h3>
                  <p className="role">{p.role}</p>
                  <p className="tagline">{p.tagline}</p>
                  <ul className="strengths">
                    {p.strengths.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </section>

          <section className="team-run">
            <h2>Run workflow</h2>
            <textarea
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="Describe a task — routing picks specialists, they run in parallel, coordinator synthesizes."
              rows={4}
            />
            <div className="run-controls">
              <label className="toggle">
                <input type="checkbox" checked={useLanggraph} onChange={(e) => setUseLanggraph(e.target.checked)} />
                Use LangGraph runtime
              </label>
              <button type="button" onClick={runTeam} disabled={loading || !task.trim()}>
                {loading ? 'Running team…' : 'Invoke team'}
              </button>
            </div>
            {sessionId && <p className="session-id">Session: {sessionId}</p>}
            {error && <p className="error">{String(error)}</p>}
          </section>

          {result && (
            <section className="team-result">
              <div className="result-header">
                <h2>Coordinator synthesis</h2>
                <span className="mode">{result.runtime_mode ?? 'team'}</span>
              </div>
              <pre className="response">{result.response}</pre>

              {delegationScores.length > 0 && (
                <>
                  <h3>Delegation scores</h3>
                  <div className="score-bars">
                    {delegationScores.map(([role, score]) => (
                      <div key={role} className="score-row">
                        <span>{role}</span>
                        <div className="bar-track">
                          <div className="bar-fill" style={{ width: `${Math.min(100, score * 100)}%`, background: roleColor(role) }} />
                        </div>
                        <span className="score-val">{score.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </section>
          )}

          {activeWorkflow && (
            <section className="workflow-timeline">
              <h2>Workflow timeline</h2>
              <ol>
                {activeWorkflow.steps?.map((step, i) => (
                  <li key={`${step.role}-${i}`} className="timeline-step">
                    <div className="step-head" style={{ borderLeftColor: roleColor(step.role) }}>
                      <strong>{step.role}</strong>
                      {step.parallel_group && <span className="parallel">parallel: {step.parallel_group}</span>}
                    </div>
                    <p className="step-output">{step.output}</p>
                    {step.tool_calls && step.tool_calls.length > 0 && (
                      <details>
                        <summary>{step.tool_calls.length} tool call(s)</summary>
                        <pre>{JSON.stringify(step.tool_calls, null, 2)}</pre>
                      </details>
                    )}
                  </li>
                ))}
              </ol>
            </section>
          )}

          {result?.tool_results && result.tool_results.length > 0 && (
            <section className="tool-results">
              <h2>Tool results</h2>
              <pre>{JSON.stringify(result.tool_results, null, 2)}</pre>
            </section>
          )}
        </main>

        <aside className="memory-panel">
          <h2>Team memory</h2>
          <div className="memory-search">
            <input
              value={memoryQuery}
              onChange={(e) => setMemoryQuery(e.target.value)}
              placeholder="Search memory…"
            />
            <button type="button" onClick={searchMemory} disabled={!sessionId}>
              Search
            </button>
          </div>
          {memoryHits.length > 0 && (
            <ul className="memory-hits">
              {memoryHits.map((hit, i) => (
                <li key={i}>
                  <strong>{String(hit.key)}</strong>
                  <p>{String(hit.value ?? '').slice(0, 200)}</p>
                </li>
              ))}
            </ul>
          )}
          {sessionDetail?.memory_entries?.length ? (
            <ul className="memory-entries">
              {sessionDetail.memory_entries.slice(0, 12).map((m) => (
                <li key={m.key}>
                  <span className="mem-key">{m.key}</span>
                  <span className="mem-role">{m.source_role}</span>
                  <p>{m.value.slice(0, 120)}{m.value.length > 120 ? '…' : ''}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty">Memory populates as specialists run tools.</p>
          )}
        </aside>
      </div>
    </div>
  );
}

export default TeamWorkbench;
