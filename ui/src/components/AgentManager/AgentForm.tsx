import { useState, useEffect } from 'react';
import type { AgentConfig, PersonaProfile } from '../../types';
import './AgentForm.css';

const MODEL_OPTIONS = [
  'llama3:8b',
  'llama3:70b',
  'llama3.1:8b',
  'llama3.1:70b',
  'mistral:7b',
  'mistral:latest',
  'gpt-4o',
  'gpt-4o-mini',
  'gpt-3.5-turbo',
  'claude-3-5-sonnet',
  'claude-3-haiku',
];

interface AgentFormProps {
  agent?: AgentConfig;
  personas: PersonaProfile[];
  onSave: (data: Partial<AgentConfig>) => void;
  onCancel: () => void;
  saving?: boolean;
}

const EMPTY: Partial<AgentConfig> = {
  name: '',
  role: '',
  model: 'llama3:8b',
  persona_id: '',
  max_tokens: 2000,
  system_prompt: '',
  memory_enabled: false,
};

export function AgentForm({ agent, personas, onSave, onCancel, saving }: AgentFormProps) {
  const [form, setForm] = useState<Partial<AgentConfig>>(agent ?? EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    setForm(agent ?? EMPTY);
    setErrors({});
  }, [agent]);

  const set = (key: keyof AgentConfig, value: unknown) => {
    setForm(prev => ({ ...prev, [key]: value }));
    setErrors(prev => ({ ...prev, [key]: '' }));
  };

  const validate = (): boolean => {
    const next: Record<string, string> = {};
    if (!form.name?.trim()) next.name = 'Name is required.';
    if (!form.model?.trim()) next.model = 'Model is required.';
    if (!form.max_tokens || form.max_tokens < 1)
      next.max_tokens = 'Max tokens must be at least 1.';
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validate()) onSave(form);
  };

  const isEdit = Boolean(agent);

  return (
    <div className="agent-form-overlay" onClick={e => e.target === e.currentTarget && onCancel()}>
      <div className="agent-form-modal">
        <div className="agent-form-header">
          <h2 className="agent-form-title">{isEdit ? 'Edit Agent' : 'New Agent'}</h2>
          <button className="agent-form-close" onClick={onCancel} aria-label="Close">✕</button>
        </div>

        <form className="agent-form-body" onSubmit={handleSubmit} noValidate>
          {/* Name */}
          <div className={`form-group ${errors.name ? 'has-error' : ''}`}>
            <label className="form-label">
              Name <span className="required">*</span>
            </label>
            <input
              className="form-input"
              type="text"
              placeholder="e.g. Research Assistant"
              value={form.name ?? ''}
              onChange={e => set('name', e.target.value)}
              maxLength={80}
            />
            {errors.name && <p className="form-error">{errors.name}</p>}
          </div>

          {/* Role */}
          <div className="form-group">
            <label className="form-label">Role</label>
            <input
              className="form-input"
              type="text"
              placeholder="e.g. Answers questions about research papers"
              value={form.role ?? ''}
              onChange={e => set('role', e.target.value)}
              maxLength={160}
            />
          </div>

          {/* Model + Max Tokens row */}
          <div className="form-row">
            <div className={`form-group ${errors.model ? 'has-error' : ''}`}>
              <label className="form-label">
                Model <span className="required">*</span>
              </label>
              <select
                className="form-select"
                value={form.model ?? 'llama3:8b'}
                onChange={e => set('model', e.target.value)}
              >
                {MODEL_OPTIONS.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
              {errors.model && <p className="form-error">{errors.model}</p>}
            </div>

            <div className={`form-group ${errors.max_tokens ? 'has-error' : ''}`}>
              <label className="form-label">
                Max Tokens <span className="required">*</span>
              </label>
              <input
                className="form-input"
                type="number"
                min={1}
                max={128000}
                step={100}
                value={form.max_tokens ?? 2000}
                onChange={e => set('max_tokens', parseInt(e.target.value, 10) || 0)}
              />
              {errors.max_tokens && <p className="form-error">{errors.max_tokens}</p>}
            </div>
          </div>

          {/* Persona picker */}
          <div className="form-group">
            <label className="form-label">Persona</label>
            <select
              className="form-select"
              value={form.persona_id ?? ''}
              onChange={e => set('persona_id', e.target.value || undefined)}
            >
              <option value="">— None —</option>
              {personas.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <p className="form-hint">
              Attaches a saved persona's system prompt and model settings to this agent.
            </p>
          </div>

          {/* System prompt */}
          <div className="form-group">
            <label className="form-label">System Prompt</label>
            <textarea
              className="form-textarea"
              placeholder="Optional override. Leave blank to inherit the persona's system prompt."
              rows={5}
              value={form.system_prompt ?? ''}
              onChange={e => set('system_prompt', e.target.value)}
            />
          </div>

          {/* Memory toggle */}
          <div className="form-group form-group-inline">
            <label className="form-toggle" htmlFor="memory-toggle">
              <input
                id="memory-toggle"
                type="checkbox"
                checked={form.memory_enabled ?? false}
                onChange={e => set('memory_enabled', e.target.checked)}
              />
              <span className="toggle-track">
                <span className="toggle-thumb" />
              </span>
              <span className="toggle-label">Enable memory</span>
            </label>
            <p className="form-hint">
              When on, the agent keeps a rolling message history across invocations.
            </p>
          </div>

          {/* Footer */}
          <div className="agent-form-footer">
            <button type="button" className="btn btn-secondary" onClick={onCancel}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Create Agent'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
