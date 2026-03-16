import axios from 'axios';
import type { 
  PersonaProfile, 
  AgentConfig, 
  KnobsResponse, 
  PresetsResponse,
  BlendRequest,
  InvokeRequest,
  InvokeResponse 
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
  invoke: (id: string, request: InvokeRequest) => 
    api.post<InvokeResponse>(`/agents/${id}/invoke`, request),
};

export default api;
