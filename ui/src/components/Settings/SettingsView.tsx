import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import './SettingsView.css';

type LLMSettings = {
  provider: string;
  model: string;
  temperature: number;
  max_tokens: number;
  ollama_base_url: string;
  openai_base_url: string;
  openrouter_base_url: string;
  openai_api_key_set: boolean;
  anthropic_api_key_set: boolean;
  gemini_api_key_set: boolean;
  openrouter_api_key_set: boolean;
  catalog: Record<string, string[]>;
};

const PROVIDERS = [
  { id: 'ollama', label: 'Ollama (local)', hint: 'Uses models on your machine' },
  { id: 'openai', label: 'OpenAI', hint: 'GPT models via OpenAI API' },
  { id: 'anthropic', label: 'Anthropic', hint: 'Claude models' },
  { id: 'gemini', label: 'Google Gemini', hint: 'Gemini models' },
  { id: 'openrouter', label: 'OpenRouter', hint: 'Multi-provider gateway' },
] as const;

export function SettingsView() {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [ollamaOk, setOllamaOk] = useState<boolean | null>(null);
  const [provider, setProvider] = useState('ollama');
  const [model, setModel] = useState('');
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(2000);
  const [ollamaBase, setOllamaBase] = useState('http://127.0.0.1:11434');
  const [openaiBase, setOpenaiBase] = useState('');
  const [openrouterBase, setOpenrouterBase] = useState('https://openrouter.ai/api/v1');
  const [openaiKey, setOpenaiKey] = useState('');
  const [anthropicKey, setAnthropicKey] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [openrouterKey, setOpenrouterKey] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [testOut, setTestOut] = useState<string | null>(null);

  const loadModels = useCallback(async (p: string) => {
    const res = await fetch(`/api/v1/settings/llm/models?provider=${encodeURIComponent(p)}`);
    const data = await res.json();
    setModels(data.models || []);
    if (p === 'ollama') setOllamaOk(Boolean(data.available));
  }, []);

  const load = useCallback(async () => {
    setError(null);
    const res = await fetch('/api/v1/settings/llm');
    if (!res.ok) throw new Error(await res.text());
    const data: LLMSettings = await res.json();
    setSettings(data);
    setProvider(data.provider);
    setModel(data.model);
    setTemperature(data.temperature);
    setMaxTokens(data.max_tokens);
    setOllamaBase(data.ollama_base_url);
    setOpenaiBase(data.openai_base_url || '');
    setOpenrouterBase(data.openrouter_base_url || 'https://openrouter.ai/api/v1');
    await loadModels(data.provider);
  }, [loadModels]);

  useEffect(() => {
    load().catch((e) => setError(String(e)));
  }, [load]);

  useEffect(() => {
    loadModels(provider).catch(() => setModels([]));
  }, [provider, loadModels]);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setStatus(null);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        provider,
        model,
        temperature,
        max_tokens: maxTokens,
        ollama_base_url: ollamaBase,
        openai_base_url: openaiBase,
        openrouter_base_url: openrouterBase,
      };
      if (openaiKey.trim()) body.openai_api_key = openaiKey.trim();
      if (anthropicKey.trim()) body.anthropic_api_key = anthropicKey.trim();
      if (geminiKey.trim()) body.gemini_api_key = geminiKey.trim();
      if (openrouterKey.trim()) body.openrouter_api_key = openrouterKey.trim();

      const res = await fetch('/api/v1/settings/llm', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      setOpenaiKey('');
      setAnthropicKey('');
      setGeminiKey('');
      setOpenrouterKey('');
      setStatus(`Saved — active ${provider} / ${model}`);
      await load();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onTest() {
    setBusy(true);
    setTestOut(null);
    setError(null);
    try {
      const res = await fetch('/api/v1/settings/llm/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: 'Reply with exactly: ok' }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
      setTestOut(`${data.provider}/${data.model}: ${data.response}`);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  const catalog = settings?.catalog?.[provider] || [];
  const modelOptions = models.length ? models : catalog;

  return (
    <div className="settings-view">
      <header className="settings-header">
        <div>
          <h1>Settings</h1>
          <p className="settings-sub">
            Choose the LLM provider and model. Local Ollama is the default when it is running.
          </p>
        </div>
        {settings && (
          <div className="settings-active">
            Active: <strong>{settings.provider}</strong> · {settings.model}
          </div>
        )}
      </header>

      {error && <div className="settings-banner error">{error}</div>}
      {status && <div className="settings-banner ok">{status}</div>}
      {testOut && <div className="settings-banner ok">{testOut}</div>}

      <form className="settings-form" onSubmit={onSave}>
        <section className="settings-section">
          <h2>Provider</h2>
          <div className="provider-grid">
            {PROVIDERS.map((p) => (
              <label key={p.id} className={`provider-card${provider === p.id ? ' on' : ''}`}>
                <input
                  type="radio"
                  name="provider"
                  value={p.id}
                  checked={provider === p.id}
                  onChange={() => setProvider(p.id)}
                />
                <span className="provider-label">{p.label}</span>
                <span className="provider-hint">{p.hint}</span>
              </label>
            ))}
          </div>
        </section>

        <section className="settings-section">
          <h2>Model</h2>
          {provider === 'ollama' && (
            <p className="settings-note">
              Ollama at <code>{ollamaBase}</code>{' '}
              {ollamaOk === true ? '· reachable' : ollamaOk === false ? '· unreachable' : ''}
            </p>
          )}
          <div className="settings-row">
            <label>
              Model
              {modelOptions.length > 0 ? (
                <select value={model} onChange={(e) => setModel(e.target.value)}>
                  {!modelOptions.includes(model) && model && (
                    <option value={model}>{model}</option>
                  )}
                  {modelOptions.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              ) : (
                <input value={model} onChange={(e) => setModel(e.target.value)} required />
              )}
            </label>
            <label>
              Or type model id
              <input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="provider/model"
              />
            </label>
          </div>
          <div className="settings-row">
            <label>
              Temperature
              <input
                type="number"
                min={0}
                max={2}
                step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(Number(e.target.value))}
              />
            </label>
            <label>
              Max tokens
              <input
                type="number"
                min={1}
                max={128000}
                value={maxTokens}
                onChange={(e) => setMaxTokens(Number(e.target.value))}
              />
            </label>
          </div>
        </section>

        {provider === 'ollama' && (
          <section className="settings-section">
            <h2>Ollama</h2>
            <label>
              Base URL
              <input value={ollamaBase} onChange={(e) => setOllamaBase(e.target.value)} />
            </label>
          </section>
        )}

        {provider === 'openai' && (
          <section className="settings-section">
            <h2>OpenAI</h2>
            <label>
              API key {settings?.openai_api_key_set ? '(saved — leave blank to keep)' : ''}
              <input
                type="password"
                autoComplete="off"
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
                placeholder="sk-…"
              />
            </label>
            <label>
              Base URL (optional)
              <input
                value={openaiBase}
                onChange={(e) => setOpenaiBase(e.target.value)}
                placeholder="https://api.openai.com/v1"
              />
            </label>
          </section>
        )}

        {provider === 'anthropic' && (
          <section className="settings-section">
            <h2>Anthropic</h2>
            <label>
              API key {settings?.anthropic_api_key_set ? '(saved — leave blank to keep)' : ''}
              <input
                type="password"
                autoComplete="off"
                value={anthropicKey}
                onChange={(e) => setAnthropicKey(e.target.value)}
                placeholder="sk-ant-…"
              />
            </label>
          </section>
        )}

        {provider === 'gemini' && (
          <section className="settings-section">
            <h2>Gemini</h2>
            <label>
              API key {settings?.gemini_api_key_set ? '(saved — leave blank to keep)' : ''}
              <input
                type="password"
                autoComplete="off"
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                placeholder="AIza…"
              />
            </label>
          </section>
        )}

        {provider === 'openrouter' && (
          <section className="settings-section">
            <h2>OpenRouter</h2>
            <label>
              API key {settings?.openrouter_api_key_set ? '(saved — leave blank to keep)' : ''}
              <input
                type="password"
                autoComplete="off"
                value={openrouterKey}
                onChange={(e) => setOpenrouterKey(e.target.value)}
                placeholder="sk-or-…"
              />
            </label>
            <label>
              Base URL
              <input
                value={openrouterBase}
                onChange={(e) => setOpenrouterBase(e.target.value)}
              />
            </label>
          </section>
        )}

        <div className="settings-actions">
          <button type="submit" className="settings-btn primary" disabled={busy}>
            {busy ? 'Saving…' : 'Save'}
          </button>
          <button type="button" className="settings-btn" onClick={onTest} disabled={busy}>
            Test connection
          </button>
        </div>
      </form>
    </div>
  );
}
