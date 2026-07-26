import axios from 'axios';
import type { 
  PersonaProfile, 
  AgentConfig, 
  KnobsResponse, 
  PresetsResponse,
  BlendRequest,
  InvokeRequest,
  InvokeResponse,
  Session,
  Message,
  StyleAnalysis,
} from '../types';

const API_BASE = '/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

export const knobsApi = {
  getKnobs: () => api.get<KnobsResponse>('/tuning/knobs'),
  validateKnobs: (knobs: Record<string, number>) => 
    api.post('/tuning/validate', knobs),
};

export const personasApi = {
  list: () => api.get<PersonaProfile[]>('/personas'),
  get: (id: string) => api.get<PersonaProfile>(`/personas/${id}`),
  create: (persona: Partial<PersonaProfile>) => 
    api.post<PersonaProfile>('/personas', persona),
  update: (id: string, persona: Partial<PersonaProfile>) => 
    api.put<PersonaProfile>(`/personas/${id}`, persona),
  delete: (id: string) => api.delete(`/personas/${id}`),
  blend: (request: BlendRequest) => 
    api.post<PersonaProfile>('/personas/blend', request),
  getSystemPrompt: (id: string) => 
    api.get<{ system_prompt: string }>(`/personas/${id}/system-prompt`),
  getSampling: (id: string) => 
    api.get<Record<string, unknown>>(`/personas/${id}/sampling`),
  exportPersona: (id: string) =>
    api.get<Blob>(`/personas/${id}/export`, { responseType: 'blob' }),
  importPersona: async (file: File) => {
    const text = await file.text();
    const data = JSON.parse(text) as PersonaProfile;
    return api.post<PersonaProfile>('/personas/import', data);
  },
};

export const presetsApi = {
  list: () => api.get<PresetsResponse>('/presets'),
  apply: (preset: string, personaId: string) => 
    api.post<PersonaProfile>(`/presets/${preset}/apply`, { persona_id: personaId }),
};

export const agentsApi = {
  list: () => api.get<AgentConfig[]>('/agents'),
  get: (id: string) => api.get<AgentConfig>(`/agents/${id}`),
  create: (agent: Partial<AgentConfig>) => 
    api.post<AgentConfig>('/agents', agent),
  update: (id: string, agent: Partial<AgentConfig>) =>
    api.put<AgentConfig>(`/agents/${id}`, agent),
  delete: (id: string) => api.delete(`/agents/${id}`),
  invoke: (id: string, request: InvokeRequest) => 
    api.post<InvokeResponse>(`/agents/${id}/invoke`, request),
};

export const analysisApi = {
  extract: (text: string) =>
    api.post<StyleAnalysis>('/analysis/extract', { text, create_persona: false }),
  extractAndCreate: (text: string, name: string) =>
    api.post<PersonaProfile>('/analysis/extract-and-create', { text, name }),
};

export const sessionsApi = {
  list: (agentId: string) => api.get<Session[]>(`/agents/${agentId}/sessions`),
  listByAgent: (agentId: string) => api.get<Session[]>(`/agents/${agentId}/sessions`),
  getMessages: (sessionId: string) => api.get<Message[]>(`/sessions/${sessionId}/messages`),
};

export const cityApi = {
  listFamilies: () => api.get('/city/families'),
  getFamily: (id: string) => api.get(`/city/families/${id}`),
  snapshot: () => api.get('/city/snapshot'),
  awaken: () => api.post('/city/scale/awaken'),
  pulse: (body: {
    max_families?: number;
    districts?: string[];
    auto_merge?: boolean;
    name_prefix?: string;
    multi_contributor?: boolean;
  } = {}) => api.post('/city/pulse', body),
  conduct: (body: {
    max_families?: number;
    districts?: string[];
    use_llm?: boolean;
    use_langgraph?: boolean;
    auto_merge?: boolean;
    task_template?: string;
  } = {}) => api.post('/city/conduct', body),
  heartbeat: () => api.get('/city/heartbeat'),
  heartbeatTick: () => api.post('/city/heartbeat/tick'),
  ecosystem: () => api.get('/city/ecosystem'),
  lifeTick: (body: { max_families?: number; force_age?: number } = {}) =>
    api.post('/city/life/tick', body),
  exportAustin: () => api.get('/city/export/austin'),
  commonsStatus: (jobId?: string) =>
    api.get('/city/commons/status', { params: jobId ? { job_id: jobId } : {} }),
  cohesionDecide: (jobId: string, body: { action: 'merge' | 'veto'; reason?: string; force?: boolean }) =>
    api.post(`/city/jobs/${jobId}/cohesion/decide`, body),
  scaleProbe: (body: {
    mode?: 'fifty' | 'hundred';
    families?: number;
    agents_per_family?: number;
    run_jobs?: boolean;
    name_prefix?: string;
  } = {}) => api.post('/city/scale/probe', body),
  seedWedge: (name?: string) => api.post('/city/wedge/seed', { name: name ?? 'Wedge City Family' }),
  runWedge: (body: { family_id?: string; goal?: string; family_name?: string } = {}) =>
    api.post('/city/wedge/run', body),
  startJob: (body: { family_id: string; goal: string; district?: string }) =>
    api.post('/city/jobs', body),
  getJob: (id: string) => api.get(`/city/jobs/${id}`),
  listArtifacts: (jobId: string) => api.get(`/city/jobs/${jobId}/artifacts`),
  listRuns: (jobId: string) => api.get(`/city/jobs/${jobId}/runs`),
  listEvents: (jobId: string) => api.get(`/city/jobs/${jobId}/events`),
  pollEvents: (params: { family_id?: string; job_id?: string; after?: string; since?: string; limit?: number }) =>
    api.get('/city/events', { params }),
  eventsStreamUrl: (params: { family_id?: string; job_id?: string; after?: string }) => {
    const q = new URLSearchParams();
    if (params.family_id) q.set('family_id', params.family_id);
    if (params.job_id) q.set('job_id', params.job_id);
    if (params.after) q.set('after', params.after);
    return `/api/v1/city/events/stream?${q.toString()}`;
  },
  listTools: () => api.get('/city/tools'),
};

export default api;