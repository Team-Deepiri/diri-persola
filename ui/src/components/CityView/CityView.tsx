import axios from 'axios';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CityGraph, type GraphFamily, type GraphMember, type GraphPulse } from './CityGraph';
import './CityView.css';

type FamilySummary = {
  id: string;
  name: string;
  description?: string | null;
  default_district: string;
  is_active: boolean;
};

type FamilyMember = GraphMember & {
  tool_tags?: string[];
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
  id?: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string | null;
  family_id?: string | null;
  job_id?: string | null;
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

type CitySnapshot = {
  families: FamilyDetail[];
  family_count: number;
  agent_count: number;
  distinct_personalities: number;
  districts: Record<string, number>;
  events: CityEvent[];
  target_agents: number;
  progress: number;
};

type AwakenResult = {
  mode: string;
  families: number;
  agents: number;
  meets_hundred_bar: boolean;
  distinct_personalities: number;
  all_personalities_unique: boolean;
  districts: Record<string, number>;
  family_ids: string[];
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

function pulseFromEvent(ev: CityEvent): GraphPulse | null {
  const agentId = (ev.payload?.agent_id as string | undefined) ?? null;
  if (!agentId) return null;
  const t = ev.event_type;
  let kind: GraphPulse['kind'] | null = null;
  if (t === 'artifact.written') kind = 'write';
  else if (t === 'run.started' || t === 'run.finished') kind = 'run';
  else if (t === 'agent.spawned') kind = 'spawn';
  else if (t === 'cohesion.merge' || t === 'viz.pulse' || t === 'city.pulse.finished') kind = 'merge';
  else if (t === 'cohesion.veto' || t === 'city.pulse.started') kind = 'run';
  if (!kind) return null;
  return { agentId, kind, at: Date.now() };
}

function decisionForAgent(
  results: Array<{ agent_id?: string; decision?: string; contributors?: Array<{ agent_id?: string }> }>,
  agentId: string,
): string | undefined {
  for (const r of results) {
    if (r.agent_id === agentId) return r.decision;
    if (r.contributors?.some((c) => c.agent_id === agentId)) return r.decision;
  }
  return undefined;
}

export function CityView() {
  const [families, setFamilies] = useState<FamilySummary[]>([]);
  const [family, setFamily] = useState<FamilyDetail | null>(null);
  const [snapshot, setSnapshot] = useState<CitySnapshot | null>(null);
  const [cityMode, setCityMode] = useState(true);
  const [job, setJob] = useState<Job | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [events, setEvents] = useState<CityEvent[]>([]);
  const [pulses, setPulses] = useState<GraphPulse[]>([]);
  const [live, setLive] = useState(true);
  const [streamMode, setStreamMode] = useState(true);
  const [selected, setSelected] = useState<GraphMember | null>(null);
  const [districtFilter, setDistrictFilter] = useState<string[]>([]);
  const [lastPulse, setLastPulse] = useState<{
    pulsed: number;
    merged: number;
    vetoed: number;
    avg_cohesion: number;
    avg_contributors?: number;
  } | null>(null);
  const [heartbeat, setHeartbeat] = useState(false);
  const [cinema, setCinema] = useState(false);
  const [cinemaLine, setCinemaLine] = useState<string | null>(null);
  const [goal, setGoal] = useState('Build hello.py in the commons and run it; siblings leave notes.');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusLine, setStatusLine] = useState<string | null>(null);
  const cursorRef = useRef<string | null>(null);
  const jobIdRef = useRef<string | null>(null);

  const graphFamilies: GraphFamily[] = useMemo(() => {
    if (cityMode && snapshot?.families?.length) {
      return snapshot.families.map((f) => ({
        id: f.id,
        name: f.name,
        default_district: f.default_district,
        members: f.members,
      }));
    }
    if (family) {
      return [
        {
          id: family.id,
          name: family.name,
          default_district: family.default_district,
          members: family.members,
        },
      ];
    }
    return [];
  }, [cityMode, snapshot, family]);

  const agentNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const f of graphFamilies) {
      for (const m of f.members) {
        map[m.agent_id] = m.agent?.name ?? m.role_label ?? shortId(m.agent_id);
      }
    }
    return map;
  }, [graphFamilies]);

  const loadFamilies = useCallback(async () => {
    const { data } = await api.get<FamilySummary[]>('/city/families');
    setFamilies(data);
  }, []);

  const loadSnapshot = useCallback(async () => {
    const { data } = await api.get<CitySnapshot>('/city/snapshot');
    setSnapshot(data);
    if (data.events?.length) {
      setEvents((prev) => {
        const seen = new Set(prev.map((e) => e.id).filter(Boolean));
        const merged = [...prev];
        for (const ev of data.events) {
          if (ev.id && seen.has(ev.id)) continue;
          if (ev.id) seen.add(ev.id);
          merged.push(ev);
        }
        return merged.slice(-250);
      });
      cursorRef.current = data.events[data.events.length - 1]?.id ?? cursorRef.current;
    }
    return data;
  }, []);

  const ingestEvents = useCallback((incoming: CityEvent[]) => {
    if (!incoming.length) return;
    setEvents((prev) => {
      const seen = new Set(prev.map((e) => e.id).filter(Boolean));
      const merged = [...prev];
      for (const ev of incoming) {
        if (ev.id && seen.has(ev.id)) continue;
        if (ev.id) seen.add(ev.id);
        merged.push(ev);
        const pulse = pulseFromEvent(ev);
        if (pulse) {
          setPulses((p) => [...p.slice(-80), pulse]);
        }
      }
      return merged.slice(-250);
    });
    const last = incoming[incoming.length - 1];
    if (last?.id) cursorRef.current = last.id;
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
    if (evRes.data.length) {
      cursorRef.current = evRes.data[evRes.data.length - 1]?.id ?? null;
    }
  }, []);

  const selectFamily = useCallback(async (id: string) => {
    const { data } = await api.get<FamilyDetail>(`/city/families/${id}`);
    setFamily(data);
    setCityMode(false);
    setJob(null);
    jobIdRef.current = null;
    setArtifacts([]);
    setRuns([]);
    setEvents([]);
    setPulses([]);
    setSelected(null);
    cursorRef.current = null;
  }, []);

  useEffect(() => {
    loadFamilies().catch(() => setFamilies([]));
    loadSnapshot().catch(() => setSnapshot(null));
  }, [loadFamilies, loadSnapshot]);

  // Live updates: prefer EventSource SSE; fall back to ≤1.5s poll
  useEffect(() => {
    if (!live) return;
    const familyId = cityMode ? undefined : family?.id;
    if (!cityMode && !familyId) return;

    let cancelled = false;
    let es: EventSource | null = null;
    let pollId = 0;

    const applyIncoming = (incoming: CityEvent[]) => {
      if (cancelled) return;
      ingestEvents(incoming);
    };

    const pollTick = async () => {
      try {
        const params: Record<string, string> = { limit: '50' };
        if (familyId) params.family_id = familyId;
        if (cursorRef.current) params.after = cursorRef.current;
        // City-wide: poll first family's stream as heartbeat + refresh snapshot lightly
        if (!familyId && snapshot?.families?.[0]?.id) {
          params.family_id = snapshot.families[0].id;
        }
        if (!params.family_id) return;
        const { data } = await api.get<{ events: CityEvent[] }>('/city/events', { params });
        applyIncoming(data.events || []);
        if (jobIdRef.current) {
          const [arts, runRes, jobRes] = await Promise.all([
            api.get<Artifact[]>(`/city/jobs/${jobIdRef.current}/artifacts`),
            api.get<Run[]>(`/city/jobs/${jobIdRef.current}/runs`),
            api.get<Job>(`/city/jobs/${jobIdRef.current}`),
          ]);
          if (!cancelled) {
            setArtifacts(arts.data);
            setRuns(runRes.data);
            setJob(jobRes.data);
          }
        }
      } catch {
        /* keep live */
      }
    };

    if (streamMode && familyId) {
      const q = new URLSearchParams({ family_id: familyId });
      if (cursorRef.current) q.set('after', cursorRef.current);
      es = new EventSource(`/api/v1/city/events/stream?${q.toString()}`);
      es.addEventListener('city', (msg) => {
        try {
          const data = JSON.parse((msg as MessageEvent).data) as CityEvent;
          if (data.event_type?.startsWith('stream.')) return;
          applyIncoming([data]);
        } catch {
          /* ignore bad frames */
        }
      });
      es.onerror = () => {
        es?.close();
        es = null;
        pollId = window.setInterval(pollTick, 1500);
      };
    } else {
      pollTick();
      pollId = window.setInterval(pollTick, 1500);
    }

    // Refresh city snapshot periodically in city mode
    const snapId = cityMode
      ? window.setInterval(() => {
          loadSnapshot().catch(() => undefined);
        }, 4000)
      : 0;

    return () => {
      cancelled = true;
      es?.close();
      if (pollId) window.clearInterval(pollId);
      if (snapId) window.clearInterval(snapId);
    };
  }, [live, streamMode, cityMode, family?.id, snapshot?.families, ingestEvents, loadSnapshot]);

  // Phase 8 — living heartbeat: auto tick the city
  useEffect(() => {
    if (!heartbeat) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const { data } = await api.post<{
          pulse: {
            pulsed: number;
            merged: number;
            vetoed: number;
            avg_cohesion: number;
            avg_contributors?: number;
            results: Array<{ agent_id?: string; decision?: string; contributors?: Array<{ agent_id?: string }> }>;
          };
        }>('/city/heartbeat/tick');
        if (cancelled) return;
        const p = data.pulse;
        setLastPulse({
          pulsed: p.pulsed,
          merged: p.merged,
          vetoed: p.vetoed,
          avg_cohesion: p.avg_cohesion,
          avg_contributors: p.avg_contributors,
        });
        const now = Date.now();
        const ids = p.results.flatMap((r) =>
          (r.contributors?.length ? r.contributors.map((c) => c.agent_id) : [r.agent_id]).filter(
            Boolean,
          ) as string[],
        );
        setPulses((prev) => [
          ...prev.slice(-40),
          ...ids.map((id, i) => ({
            agentId: id,
            kind: 'run' as const,
            at: now - i * 20,
          })),
        ]);
        await loadSnapshot();
        setStatusLine(
          `Heartbeat — ${p.pulsed} families · ${p.merged} merged · coh ${p.avg_cohesion}`,
        );
      } catch {
        /* keep beating */
      }
    };
    tick();
    const id = window.setInterval(tick, 12000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [heartbeat, loadSnapshot]);

  // Phase 9 — cinema district spotlight cycle
  useEffect(() => {
    if (!cinema) return;
    const districts = ['build', 'viz', 'research', 'ops'] as const;
    let i = 0;
    setDistrictFilter([districts[0]]);
    const id = window.setInterval(() => {
      i = (i + 1) % districts.length;
      setDistrictFilter([districts[i]]);
      setCinemaLine(`Spotlight · ${districts[i]} district`);
    }, 2800);
    const stop = window.setTimeout(() => {
      setCinema(false);
      setDistrictFilter([]);
      setCinemaLine(null);
    }, 14000);
    return () => {
      window.clearInterval(id);
      window.clearTimeout(stop);
    };
  }, [cinema]);

  const onSeed = async () => {
    setLoading(true);
    setError(null);
    setStatusLine(null);
    try {
      const { data } = await api.post<FamilyDetail>('/city/wedge/seed', {
        name: `Wedge City ${new Date().toLocaleTimeString()}`,
      });
      setFamily(data);
      setCityMode(false);
      cursorRef.current = null;
      await loadFamilies();
      await loadSnapshot();
      setStatusLine(`Seeded family with ${data.members.length} members — watch the graph.`);
    } catch (err) {
      setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const onAwaken = async () => {
    setLoading(true);
    setError(null);
    setStatusLine(null);
    setCityMode(true);
    try {
      const { data } = await api.post<AwakenResult>('/city/scale/awaken');
      await loadFamilies();
      const snap = await loadSnapshot();
      setStatusLine(
        data.meets_hundred_bar
          ? `City awakened — ${data.agents} agents, ${data.distinct_personalities} distinct personalities across ${data.families} families.`
          : `Awaken finished with ${data.agents} agents (target 100).`,
      );
      if (snap?.events?.length) {
        const now = Date.now();
        setPulses(
          snap.events
            .map((e, i) => {
              const p = pulseFromEvent(e);
              return p ? { ...p, at: now - (snap.events.length - i) * 40 } : null;
            })
            .filter(Boolean) as GraphPulse[],
        );
      }
    } catch (err) {
      setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const onPulse = async () => {
    setLoading(true);
    setError(null);
    setCityMode(true);
    try {
      const { data } = await api.post<{
        pulsed: number;
        merged: number;
        vetoed: number;
        avg_cohesion: number;
        avg_contributors?: number;
        results: Array<{ agent_id?: string; decision?: string; contributors?: Array<{ agent_id?: string }> }>;
      }>('/city/pulse', {
        max_families: 12,
        districts: districtFilter.length ? districtFilter : undefined,
        auto_merge: true,
        multi_contributor: true,
      });
      setLastPulse({
        pulsed: data.pulsed,
        merged: data.merged,
        vetoed: data.vetoed,
        avg_cohesion: data.avg_cohesion,
        avg_contributors: data.avg_contributors,
      });
      const now = Date.now();
      const pulseAgents = data.results.flatMap((r) =>
        (r.contributors?.length
          ? r.contributors.map((c) => c.agent_id)
          : [r.agent_id]
        ).filter(Boolean) as string[],
      );
      setPulses((prev) => [
        ...prev.slice(-40),
        ...pulseAgents.map((id, i) => ({
          agentId: id,
          kind: (decisionForAgent(data.results, id) === 'veto' ? 'merge' : 'run') as GraphPulse['kind'],
          at: now - i * 30,
        })),
      ]);
      await loadSnapshot();
      await loadFamilies();
      setStatusLine(
        `City pulse — ${data.pulsed} families · ${data.merged} merged · avg ${data.avg_contributors ?? '?'} contributors · cohesion ${data.avg_cohesion}`,
      );
    } catch (err) {
      setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const toggleDistrict = (d: string) => {
    setDistrictFilter((prev) =>
      prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d],
    );
  };

  const onExportAustin = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get('/city/export/austin');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `persola-austin-pack-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setStatusLine(
        `Austin pack exported — ${data.vitals?.agent_count ?? 0} agents, ${data.events?.length ?? 0} events.`,
      );
    } catch (err) {
      setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const onCinema = async () => {
    setCinema(true);
    setCityMode(true);
    setHeartbeat(false);
    setError(null);
    setLoading(true);
    try {
      setCinemaLine('Scanning the skyline…');
      let snap = await loadSnapshot();
      if ((snap?.agent_count ?? 0) < 20) {
        setCinemaLine('Awakening one hundred personalities…');
        await api.post('/city/scale/awaken');
        snap = await loadSnapshot();
        await loadFamilies();
      }
      setCinemaLine('Districts lighting up — pulsing the commons…');
      const { data } = await api.post<{
        pulsed: number;
        merged: number;
        avg_cohesion: number;
        avg_contributors?: number;
        results: Array<{ agent_id?: string; contributors?: Array<{ agent_id?: string }> }>;
      }>('/city/pulse', { max_families: 12, multi_contributor: true, auto_merge: true });
      setLastPulse({
        pulsed: data.pulsed,
        merged: data.merged,
        vetoed: 0,
        avg_cohesion: data.avg_cohesion,
        avg_contributors: data.avg_contributors,
      });
      const now = Date.now();
      const ids = data.results.flatMap((r) =>
        (r.contributors?.length ? r.contributors.map((c) => c.agent_id) : [r.agent_id]).filter(
          Boolean,
        ) as string[],
      );
      setPulses(ids.map((id, i) => ({ agentId: id, kind: 'run' as const, at: now - i * 25 })));
      await loadSnapshot();
      setCinemaLine(
        `Cinema pulse complete — ${data.pulsed} families · cohesion ${data.avg_cohesion}`,
      );
      setStatusLine('Cinema demo finished — export an Austin pack or enable Heartbeat.');
    } catch (err) {
      setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? err.message : String(err));
      setCinemaLine(null);
      setCinema(false);
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
        district: family.default_district || 'build',
      });
      setJob(data);
      jobIdRef.current = data.id;
      await refreshJobViews(data.id);
      setStatusLine('Job started — live events will pulse the graph.');
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
      setCityMode(false);
      setJob(data.job);
      jobIdRef.current = data.job.id;
      setArtifacts(data.artifacts);
      setRuns(data.runs);
      setEvents(data.events);
      if (data.events.length) {
        cursorRef.current = data.events[data.events.length - 1]?.id ?? null;
        const now = Date.now();
        setPulses(
          data.events
            .map((e, i) => {
              const p = pulseFromEvent(e);
              return p ? { ...p, at: now - (data.events.length - i) * 80 } : null;
            })
            .filter(Boolean) as GraphPulse[],
        );
      }
      await loadFamilies();
      await loadSnapshot();
      setStatusLine(
        data.success
          ? 'Wedge demo succeeded — graph pulses show who built and ran.'
          : 'Wedge demo finished with failures — check runs.',
      );
    } catch (err) {
      setError(axios.isAxiosError(err) ? err.response?.data?.detail ?? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const progressPct = Math.round((snapshot?.progress ?? 0) * 100);

  return (
    <div className="city-view">
      <header className="city-header">
        <div>
          <h1>Persola City</h1>
          <p className="city-sub">
            Living society of distinct personalities — districts, families, build/run pulses. Austin
            stream: <code>/api/v1/city/events/stream</code>
          </p>
        </div>
        <div className="city-actions">
          <label className="live-toggle">
            <input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} />
            Live
          </label>
          <label className="live-toggle">
            <input
              type="checkbox"
              checked={streamMode}
              onChange={(e) => setStreamMode(e.target.checked)}
            />
            SSE
          </label>
          <label className="live-toggle">
            <input
              type="checkbox"
              checked={heartbeat}
              onChange={(e) => setHeartbeat(e.target.checked)}
            />
            Heartbeat
          </label>
          <button type="button" className="btn ghost" onClick={() => setCityMode(true)} disabled={loading}>
            City view
          </button>
          <button type="button" className="btn ghost" onClick={onSeed} disabled={loading}>
            Seed family
          </button>
          <button type="button" className="btn accent" onClick={onAwaken} disabled={loading}>
            {loading ? 'Working…' : 'Awaken 100'}
          </button>
          <button type="button" className="btn pulse-btn" onClick={onPulse} disabled={loading}>
            Pulse city
          </button>
          <button type="button" className="btn cinema-btn" onClick={onCinema} disabled={loading || cinema}>
            {cinema ? 'Cinema…' : 'Cinema'}
          </button>
          <button type="button" className="btn ghost" onClick={onExportAustin} disabled={loading}>
            Export Austin
          </button>
          <button type="button" className="btn primary" onClick={onWedgeRun} disabled={loading}>
            Run wedge
          </button>
        </div>
      </header>

      {error && <div className="city-banner error">{String(error)}</div>}
      {statusLine && <div className="city-banner ok">{statusLine}</div>}
      {cinemaLine && <div className="city-banner cinema">{cinemaLine}</div>}

      <div className={`city-stage${cinema ? ' cinema-on' : ''}`}>
      <div className="city-stats">
        <div className="stat">
          <span className="stat-value">{snapshot?.agent_count ?? 0}</span>
          <span className="stat-label">agents</span>
        </div>
        <div className="stat">
          <span className="stat-value">{snapshot?.family_count ?? 0}</span>
          <span className="stat-label">families</span>
        </div>
        <div className="stat">
          <span className="stat-value">{snapshot?.distinct_personalities ?? 0}</span>
          <span className="stat-label">personalities</span>
        </div>
        <div className="stat progress-stat">
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progressPct}%` }} />
          </div>
          <span className="stat-label">
            {lastPulse
              ? `pulse ${lastPulse.merged}/${lastPulse.pulsed} · coh ${lastPulse.avg_cohesion}`
              : `${progressPct}% to 100`}
          </span>
        </div>
      </div>

      <div className="district-filters">
        {(['build', 'viz', 'research', 'ops'] as const).map((d) => (
          <button
            key={d}
            type="button"
            className={`district-chip ${d}${districtFilter.includes(d) || districtFilter.length === 0 ? ' on' : ''}`}
            onClick={() => toggleDistrict(d)}
          >
            {d}
          </button>
        ))}
        {districtFilter.length > 0 && (
          <button type="button" className="district-chip clear" onClick={() => setDistrictFilter([])}>
            all districts
          </button>
        )}
      </div>

      <div className="city-layout">
        <aside className="city-sidebar">
          <h2>Families</h2>
          <ul className="family-list">
            {families.map((f) => (
              <li key={f.id}>
                <button
                  type="button"
                  className={family?.id === f.id && !cityMode ? 'active' : ''}
                  onClick={() => selectFamily(f.id)}
                >
                  <span>{f.name}</span>
                  <span className="muted">{f.default_district}</span>
                </button>
              </li>
            ))}
            {families.length === 0 && <li className="muted">No families yet — awaken or seed.</li>}
          </ul>
        </aside>

        <section className="city-main">
          <div className="panel graph-panel">
            <div className="panel-head">
              <h2>
                {cityMode
                  ? 'Living city · districts'
                  : `Lineage · ${family?.name ?? 'family'}`}
              </h2>
              <span className="pill">
                {graphFamilies.reduce((n, f) => n + f.members.length, 0)} agents
              </span>
            </div>
            <CityGraph
              families={graphFamilies}
              pulses={pulses}
              selectedAgentId={selected?.agent_id ?? null}
              onSelectAgent={setSelected}
              districtFilter={districtFilter}
              height={cityMode ? 560 : 320}
            />
          </div>

          {selected && (
            <div className="panel inspect-panel">
              <div className="panel-head">
                <h2>Inspect</h2>
                <button type="button" className="btn ghost" onClick={() => setSelected(null)}>
                  Clear
                </button>
              </div>
              <div className="inspect-grid">
                <div>
                  <h3>{selected.agent?.name ?? 'Agent'}</h3>
                  <div className="role-tag" style={{ borderColor: roleColor(selected.role_label) }}>
                    {selected.role_label || selected.role_in_family}
                  </div>
                  <p className="muted">
                    {selected.district ?? '—'} · fingerprint{' '}
                    {selected.personality?.fingerprint ?? '—'}
                  </p>
                </div>
                <div className="trait-bars">
                  {(selected.personality?.top_traits ?? Object.entries(selected.knob_overrides ?? {}).map(([knob, value]) => ({ knob, value }))).slice(0, 6).map((t) => (
                    <div key={t.knob} className="trait-bar">
                      <span>{t.knob}</span>
                      <div className="bar-track">
                        <div className="bar-fill" style={{ width: `${Math.round(t.value * 100)}%` }} />
                      </div>
                      <span>{(t.value * 100).toFixed(0)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {!cityMode && (
            <>
              <div className="panel">
                <div className="panel-head">
                  <h2>Roster</h2>
                </div>
                {!family && <p className="muted">Select or seed a family to see lineage.</p>}
                {family && (
                  <div className="roster-grid">
                    {family.members.map((m) => (
                      <article
                        key={m.id}
                        className={`roster-card${selected?.id === m.id ? ' selected' : ''}`}
                        style={{ borderTopColor: roleColor(m.role_label || m.role_in_family) }}
                        onClick={() => setSelected(m)}
                      >
                        <h3>{m.agent?.name ?? 'Agent'}</h3>
                        <div className="role-tag">{m.role_label || m.role_in_family}</div>
                        <div className="meta">
                          {m.personality?.fingerprint
                            ? `fp ${m.personality.fingerprint}`
                            : m.role_in_family}
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
            </>
          )}
        </section>

        <aside className="city-events">
          <h2>Live events</h2>
          <ul className="event-feed">
            {[...events].reverse().map((e, idx) => (
              <li key={e.id ?? `${e.event_type}-${idx}`} className={`ev-${e.event_type.replace('.', '-')}`}>
                <div className="event-type">{e.event_type}</div>
                <div className="muted">{e.created_at ? new Date(e.created_at).toLocaleTimeString() : ''}</div>
              </li>
            ))}
            {events.length === 0 && <li className="muted">Events appear as the city works.</li>}
          </ul>
        </aside>
      </div>
      </div>
    </div>
  );
}
