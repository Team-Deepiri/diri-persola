export interface KnobDefinition {
  key: string;
  name: string;
  description: string;
  min_value: number;
  max_value: number;
  default: number;
  panel: string;
  step: number;
}

export interface PersonaProfile {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  creativity: number;
  humor: number;
  formality: number;
  verbosity: number;
  empathy: number;
  confidence: number;
  openness: number;
  conscientiousness: number;
  extraversion: number;
  agreeableness: number;
  neuroticism: number;
  reasoning_depth: number;
  step_by_step: number;
  creativity_in_reasoning: number;
  synthetics: number;
  abstraction: number;
  patterns: number;
  accuracy: number;
  reliability: number;
  caution: number;
  consistency: number;
  self_correction: number;
  transparency: number;
  system_prompt: string;
  model: string;
  temperature: number;
  max_tokens: number;
  knobs: Record<string, number>;
  communication_style: CommunicationStyle;
  personality_traits: PersonalityTraits;
  cognitive_style: CognitiveStyle;
  reliability_profile: ReliabilityProfile;
  model_settings: ModelSettings;
}

export interface CommunicationStyle {
  creativity: number;
  humor: number;
  formality: number;
  verbosity: number;
  empathy: number;
  confidence: number;
}

export interface PersonalityTraits {
  openness: number;
  conscientiousness: number;
  extraversion: number;
  agreeableness: number;
  neuroticism: number;
}

export interface CognitiveStyle {
  reasoning_depth: number;
  step_by_step: number;
  creativity_in_reasoning: number;
  synthetics: number;
  abstraction: number;
  patterns: number;
}

export interface ReliabilityProfile {
  accuracy: number;
  reliability: number;
  caution: number;
  consistency: number;
  self_correction: number;
  transparency: number;
}

export interface ModelSettings {
  system_prompt: string;
  model: string;
  temperature: number;
  max_tokens: number;
}

export interface AgentTool {
  name: string;
  enabled: boolean;
  description: string;
  config: Record<string, unknown>;
}

export interface AgentMemoryPolicy {
  enabled: boolean;
  session_scope: string;
  history_window: number;
}

export interface AgentConfig {
  agent_id: string;
  name: string;
  role: string;
  model: string;
  temperature: number;
  max_tokens: number;
  system_prompt: string;
  persona_id?: string;
  tools: string[];
  memory_enabled: boolean;
  session_id?: string;
  tool_configs: AgentTool[];
  memory_policy: AgentMemoryPolicy;
}

export interface Preset {
  name: string;
  description: string;
  knobs: Record<string, number>;
}

export interface PresetsResponse {
  presets: Record<string, Preset>;
}

export interface KnobsResponse {
  knobs: KnobDefinition[];
  panels: string[];
}

export interface BlendRequest {
  persona1_id: string;
  persona2_id: string;
  ratio: number;
}

export interface InvokeRequest {
  message: string;
  history?: Array<{ role: string; content: string }>;
}

export interface InvokeResponse {
  agent_id: string;
  response: string;
  message: string;
}

export const PANELS = ['Creativity', 'Personality', 'Thinking', 'Reliability'] as const;
export type PanelName = typeof PANELS[number];

export const PANEL_ICONS: Record<PanelName, string> = {
  Creativity: '✨',
  Personality: '👤',
  Thinking: '🧠',
  Reliability: '🎯',
};

export const PANEL_COLORS: Record<PanelName, string> = {
  Creativity: 'linear-gradient(135deg, #f59e0b, #ef4444)',
  Personality: 'linear-gradient(135deg, #ec4899, #8b5cf6)',
  Thinking: 'linear-gradient(135deg, #06b6d4, #3b82f6)',
  Reliability: 'linear-gradient(135deg, #10b981, #14b8a6)',
};
