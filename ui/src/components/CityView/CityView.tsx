import axios from 'axios';
import { useCallback, useEffect, useMemo, useState } from 'react';
import './CityView.css';

type FamilySummary = {
  id: string;
  name: string;
  description?: string | null;
  default_district: string;
  is_active: boolean;
};

type FamilyMember = {
  id: string;
  agent_id: string;
  parent_member_id: string | null;
  role_in_family: string;
  role_label: string | null;
  tool_tags: string[];
  agent?: { agent_id: string; name: string; persona_id?: string | null } | null;
};

type FamilyDetail = FamilySummary & {
  members: FamilyMember[];
  lineage: { nodes: FamilyMember[]; edges: Array<{ from: string; to: string }> };
  policy?: Record<string, unknown>;
};

type Artifact = {
  id: string;
  path: string;
  version: number;
  size_bytes: number;
  created_by_agent_id: string | null;
  created_at: string | null;
};

type Run = {
  id: string;
  tool: string;
  status: string;
  stdout?: string | null;
  stderr?: string | null;
  duration_ms?: number | null;
  started_by_agent_id: string | null;
  created_at: string | null;
};

type CityEvent = {
  id: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string | null;
};

type Job = {
  id: string;
  family_id: string;
  goal: string;
  district: string;
  status: string;
  result_summary?: string | null;
  artifact_count?: number;
  run_count?: number;
  event_count?: number;
};

type WedgeResult = {
  success: boolean;
  family: FamilyDetail;
  job: Job;
  artifacts: Artifact[];
  runs: Run[];
  events: CityEvent[];
  contributions: Array<Record<string, unknown>>;
};

const api = axios.create({ baseURL: '/api/v1', headers: { 'Content-Type': 'application/json' } });

const ROLE_COLORS: Record<string, string> = {
  coordinator: '#0f766e',
  analyst: '#0369a1',
  creative: '#b45309',
  executor: '#15803d',
  empath: '#be185d',
  builder: '#4338ca',
  parent: '#0f766e',
  child: '#64748b',
};

function roleColor(role: string | null | undefined) {
  if (!role) return '#64748b';
  return ROLE_COLORS[role] ?? '#64748b';
}

function shortId(id: string | null | undefined) {
  if (!id) return '—';
  return id.slice(0, 8);
}

export function CityView() {
  const [families, setFamilies] = useState<FamilySummary[]>([]);
  const [family, setFamily] = useState<FamilyDetail | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [events, setEvents] = useState<CityEvent[]>([]);
  const [goal, setGoal] = useState('Build hello.py in the commons and run it; siblings leave notes.');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusLine, setStatusLine] = useState<string | null>(null);

  const agentNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const m of family?.members ?? []) {
      map[m.agent_id] = m.agent?.name ?? m.role_label ?? shortId(m.agent_id);
    }
    return map;
  }, [family]);

  const loadFamilies = useCallback(async () => {
    const { data } = await api.get<FamilySummary[]>('/city/families');
    setFamilies(data);
  }, []);

  const selectFamily = useCallback(async (id: string) => {
    const { data } = await api.get<FamilyDetail>(`/city/families/${id}`);
    setFamily(data);
    setJob(null);
    setArtifacts([]);
    setRuns([]);
    setEvents([]);
  }, []);

  const refreshJobViews = useCallback(async (jobId: string) => {
    const [jobRes, arts, runRes, evRes] = await Promise.all([
      api.get<Job>(`/city/jobs/${jobId}`),
      api.get<Artifact[]>(`/city/jobs/${jobId}/artifacts`),
      api.get<Run[]>(`/city/jobs/${jobId}/runs`),
      api.get<CityEvent[]>(`/city/jobs/${jobId}/events`),
    ]);
    setJob(jobRes.data);
    setArtifacts(arts.data);
    setRuns(runRes.data);
    setEvents(evRes.data);
  }, []);

  useEffect(() => {
    loadFamilies().catch(() => setFamilies([]));
  }, [loadFamilies]);

  const onSeed = async () => {
    setLoading(true);
    setError(null);
    setStatusLine(null);
    try {
      const { data } = await api.post<FamilyDetail>('/city/wedge/seed', {
        name: `Wedge City ${new Date().toLocaleTimeString()}`,
      });
      setFamily(data);
      await loadFamilies();
      setStatusLine(`Seeded family with ${data.members.length} members.`);
    } catch (err) {
      setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const onStartJob = async () => {
    if (!family) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.post<Job>('/city/jobs', {
        family_id: family.id,
        goal,
        district: 'build',
      });
      setJob(data);
      await refreshJobViews(data.id);
      setStatusLine('Job started (pending). Run the wedge demo to build & execute.');
    } catch (err) {
      setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const onWedgeRun = async () => {
    setLoading(true);
    setError(null);
    setStatusLine(null);
    try {
      const { data } = await api.post<WedgeResult>('/city/wedge/run', {
        family_id: family?.id,
        goal,
      });
      setFamily(data.family);
      setJob(data.job);
      setArtifacts(data.artifacts);
      setRuns(data.runs);
      setEvents(data.events);
      await loadFamilies();
      setStatusLine(
        data.success
          ? 'Wedge demo succeeded — siblings wrote notes; executor built and ran hello.py.'
          : 'Wedge demo finished with failures — check runs.',
      );
    } catch (err) {
      setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="city-view">
      <header className="city-header">
        <div>
          <h1>City</h1>
          <p className="city-sub">
            Communal agents — families, shared commons, build and run. Phase 3 wedge demo.
          </p>
        </div>
        <div className="city-actions">
          <button type="button" className="btn ghost" onClick={onSeed} disabled={loading}>
            Seed family
          </button>
          <button type="button" className="btn primary" onClick={onWedgeRun} disabled={loading}>
            {loading ? 'Running…' : 'Run wedge demo'}
          </button>
        </div>
      </header>

      {error && <div className="city-banner error">{String(error)}</div>}
      {statusLine && <div className="city-banner ok">{statusLine}</div>}

      <div className="city-layout">
        <aside className="city-sidebar">
          <h2>Families</h2>
          <ul className="family-list">
            {families.map((f) => (
              <li key={f.id}>
                <button
                  type="button"
                  className={family?.id === f.id ? 'active' : ''}
                  onClick={() => selectFamily(f.id)}
                >
                  <span>{f.name}</span>
                  <span className="muted">{f.default_district}</span>
                </button>
              </li>
            ))}
            {families.length === 0 && <li className="muted">No families yet — seed one.</li>}
          </ul>
        </aside>

        <section className="city-main">
          <div className="panel">
            <div className="panel-head">
              <h2>Roster {family ? `· ${family.name}` : ''}</h2>
              {family && (
                <span className="pill">{family.members.length} agents</span>
              )}
            </div>
            {!family && <p className="muted">Select or seed a family to see lineage.</p>}
            {family && (
              <div className="roster-grid">
                {family.members.map((m) => (
                  <article
                    key={m.id}
                    className="roster-card"
                    style={{ borderTopColor: roleColor(m.role_label || m.role_in_family) }}
                  >
                    <h3>{m.agent?.name ?? 'Agent'}</h3>
                    <div className="role-tag">{m.role_label || m.role_in_family}</div>
                    <div className="meta">
                      {m.role_in_family}
                      {m.parent_member_id ? ` · child of ${shortId(m.parent_member_id)}` : ' · root'}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2>Job</h2>
              {job && <span className={`pill status-${job.status}`}>{job.status}</span>}
            </div>
            <label className="goal-label" htmlFor="city-goal">
              Goal
            </label>
            <textarea
              id="city-goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              rows={3}
            />
            <div className="row-actions">
              <button type="button" className="btn ghost" onClick={onStartJob} disabled={!family || loading}>
                Start job only
              </button>
              <button type="button" className="btn primary" onClick={onWedgeRun} disabled={loading}>
                Build & run (wedge)
              </button>
            </div>
            {job && (
              <p className="job-meta">
                {job.goal}
                <br />
                <span className="muted">
                  job {shortId(job.id)} · artifacts {job.artifact_count ?? artifacts.length} · runs{' '}
                  {job.run_count ?? runs.length}
                </span>
              </p>
            )}
          </div>

          <div className="split">
            <div className="panel">
              <h2>Artifacts</h2>
              <table className="city-table">
                <thead>
                  <tr>
                    <th>Path</th>
                    <th>By</th>
                    <th>Ver</th>
                  </tr>
                </thead>
                <tbody>
                  {artifacts.map((a) => (
                    <tr key={a.id}>
                      <td>
                        <code>{a.path}</code>
                      </td>
                      <td>{agentNameById[a.created_by_agent_id ?? ''] ?? shortId(a.created_by_agent_id)}</td>
                      <td>{a.version}</td>
                    </tr>
                  ))}
                  {artifacts.length === 0 && (
                    <tr>
                      <td colSpan={3} className="muted">
                        No artifacts yet
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="panel">
              <h2>Runs</h2>
              <table className="city-table">
                <thead>
                  <tr>
                    <th>Tool</th>
                    <th>By</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.id}>
                      <td>{r.tool}</td>
                      <td>{agentNameById[r.started_by_agent_id ?? ''] ?? shortId(r.started_by_agent_id)}</td>
                      <td>
                        <span className={`pill status-${r.status}`}>{r.status}</span>
                      </td>
                    </tr>
                  ))}
                  {runs.length === 0 && (
                    <tr>
                      <td colSpan={3} className="muted">
                        No runs yet
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
              {runs.some((r) => r.stdout) && (
                <pre className="stdout">
                  {runs
                    .filter((r) => r.status === 'succeeded' && r.stdout)
                    .map((r) => r.stdout)
                    .join('\n')}
                </pre>
              )}
            </div>
          </div>
        </section>

        <aside className="city-events">
          <h2>Events</h2>
          <ul className="event-feed">
            {events.map((e) => (
              <li key={e.id}>
                <div className="event-type">{e.event_type}</div>
                <div className="muted">{e.created_at ? new Date(e.created_at).toLocaleTimeString() : ''}</div>
              </li>
            ))}
            {events.length === 0 && <li className="muted">Events appear after a job runs.</li>}
          </ul>
        </aside>
      </div>
    </div>
  );
}
