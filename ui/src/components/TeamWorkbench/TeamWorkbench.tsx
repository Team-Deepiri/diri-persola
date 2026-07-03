import { useEffect, useState } from 'react';
import axios from 'axios';
import './TeamWorkbench.css';

type Personality = {
  role: string;
  name: string;
  tagline: string;
  strengths: string[];
  collaboration_style: string;
};

type WorkflowStep = {
  role: string;
  task: string;
  output: string;
};

type TeamInvokeResponse = {
  session_id: string;
  response: string;
  personalities_used: string[];
  delegation_plan: { specialists: string[]; scores: Record<string, number> };
  workflow: { steps: WorkflowStep[] };
};

const api = axios.create({ baseURL: '/api/v1', headers: { 'Content-Type': 'application/json' } });

export function TeamWorkbench() {
  const [personalities, setPersonalities] = useState<Personality[]>([]);
  const [task, setTask] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TeamInvokeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Personality[]>('/teams/personalities').then((r) => setPersonalities(r.data)).catch(() => {});
  }, []);

  const runTeam = async () => {
    if (!task.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.post<TeamInvokeResponse>('/teams/invoke', {
        task,
        session_id: sessionId,
      });
      setResult(data);
      setSessionId(data.session_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Team invoke failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="team-workbench page-container">
      <header className="team-header">
        <h1>Team Orchestration</h1>
        <p>Multi-personality agents delegate, run tools in parallel, and synthesize like a human team.</p>
      </header>

      <section className="team-personalities">
        <h2>Personalities</h2>
        <div className="personality-grid">
          {personalities.map((p) => (
            <article key={p.role} className="personality-card">
              <h3>{p.name}</h3>
              <p className="tagline">{p.tagline}</p>
              <p className="style">{p.collaboration_style}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="team-run">
        <h2>Run team workflow</h2>
        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="Describe a task for the team to tackle together..."
          rows={4}
        />
        <button type="button" onClick={runTeam} disabled={loading || !task.trim()}>
          {loading ? 'Running team...' : 'Invoke team'}
        </button>
        {sessionId && <p className="session-id">Session: {sessionId}</p>}
        {error && <p className="error">{error}</p>}
      </section>

      {result && (
        <section className="team-result">
          <h2>Coordinator synthesis</h2>
          <pre className="response">{result.response}</pre>
          <h3>Delegation</h3>
          <p>Specialists: {result.delegation_plan.specialists.join(', ')}</p>
          <h3>Workflow steps</h3>
          <ol>
            {result.workflow.steps.map((step, i) => (
              <li key={`${step.role}-${i}`}>
                <strong>{step.role}</strong>: {step.output.slice(0, 240)}
                {step.output.length > 240 ? '…' : ''}
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

export default TeamWorkbench;
