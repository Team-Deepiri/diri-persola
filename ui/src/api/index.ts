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

export default api;
