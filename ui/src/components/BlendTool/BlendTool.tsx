import { useState, useEffect, type ChangeEvent } from 'react';
import { personasApi, knobsApi } from '../../api';
import type { PersonaProfile, KnobDefinition } from '../../types';
import { PANELS, PANEL_COLORS, PANEL_ICONS, type PanelName } from '../../types';
import './BlendTool.css';

function blendKnobs(
  a: Record<string, number>,
  b: Record<string, number>,
  ratio: number,
): Record<string, number> {
  const result: Record<string, number> = {};
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const key of keys) {
    const va = a[key] ?? 0.5;
    const vb = b[key] ?? 0.5;
    result[key] = Math.round((va * (1 - ratio) + vb * ratio) * 1000) / 1000;
  }
  return result;
}

export function BlendTool() {
  const [personas, setPersonas] = useState<PersonaProfile[]>([]);
  const [knobDefs, setKnobDefs] = useState<KnobDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [persona1Id, setPersona1Id] = useState<string>('');
  const [persona2Id, setPersona2Id] = useState<string>('');
  const [ratio, setRatio] = useState(0.5);
  const [blendName, setBlendName] = useState('');
  const [saving, setSaving] = useState(false);
  const [savedPersona, setSavedPersona] = useState<PersonaProfile | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([personasApi.list(), knobsApi.getKnobs()])
      .then(([pRes, kRes]) => {
        setPersonas(pRes.data);
        setKnobDefs(kRes.data.knobs);
      })
      .catch(err => console.error('BlendTool load error:', err))
      .finally(() => setLoading(false));
  }, []);

  const persona1 = personas.find((p: PersonaProfile) => p.id === persona1Id);
  const persona2 = personas.find((p: PersonaProfile) => p.id === persona2Id);
  const canPreview = !!persona1 && !!persona2 && persona1Id !== persona2Id;
  const blended = canPreview ? blendKnobs(persona1.knobs, persona2.knobs, ratio) : null;

  const pct = (ratio * 100).toFixed(0);
  const aPct = (100 - Number(pct)).toFixed(0);

  const handleSave = async () => {
    if (!canPreview || !blended || !blendName.trim()) return;
    setSaving(true);
    setSaveError(null);
    setSavedPersona(null);
    try {
      const payload: Partial<PersonaProfile> = {
        name: blendName.trim(),
        description: `Blend of "${persona1!.name}" (${aPct}%) and "${persona2!.name}" (${pct}%)`,
        ...blended,
        model: persona1!.model || 'llama3:8b',
        temperature: persona1!.temperature ?? 0.7,
        max_tokens: persona1!.max_tokens ?? 2000,
      };
      const res = await personasApi.create(payload);
      setSavedPersona(res.data);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save persona');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setSavedPersona(null);
    setSaveError(null);
    setBlendName('');
  };

  if (loading) {
    return (
      <div className="blend-tool page-container">
        <div className="blend-loading">Loading personas…</div>
      </div>
    );
  }

  if (personas.length < 2) {
    return (
      <div className="blend-tool page-container">
        <div className="blend-empty">
          <div className="blend-empty-icon">🎭</div>
          <p>You need at least two saved personas to use the blend tool.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="blend-tool page-container">
      <div className="blend-header">
        <div>
          <h1 className="blend-title">Persona Blend</h1>
          <p className="blend-subtitle">Mix two personas to create a new one</p>
        </div>
      </div>

      {/* Selectors */}
      <div className="blend-selectors">
        <div className="blend-selector-card blend-selector-a">
          <div className="blend-selector-label">Persona A</div>
          <select
            className="blend-select"
            value={persona1Id}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => {
              setPersona1Id(e.target.value);
              handleReset();
            }}
          >
            <option value="">— choose persona —</option>
            {personas.map((p: PersonaProfile) => (
              <option key={p.id} value={p.id} disabled={p.id === persona2Id}>
                {p.name}
              </option>
            ))}
          </select>
          {persona1 && (
            <p className="blend-selector-desc">{persona1.description}</p>
          )}
        </div>

        <div className="blend-connector">
          <div className="blend-connector-icon">⇄</div>
        </div>

        <div className="blend-selector-card blend-selector-b">
          <div className="blend-selector-label">Persona B</div>
          <select
            className="blend-select"
            value={persona2Id}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => {
              setPersona2Id(e.target.value);
              handleReset();
            }}
          >
            <option value="">— choose persona —</option>
            {personas.map((p: PersonaProfile) => (
              <option key={p.id} value={p.id} disabled={p.id === persona1Id}>
                {p.name}
              </option>
            ))}
          </select>
          {persona2 && (
            <p className="blend-selector-desc">{persona2.description}</p>
          )}
        </div>
      </div>

      {/* Ratio slider */}
      {canPreview && (
        <div className="blend-ratio-section">
          <div className="blend-ratio-labels">
            <span className="blend-ratio-label-a">
              {persona1.name} <span className="blend-ratio-pct">{aPct}%</span>
            </span>
            <span className="blend-ratio-label-b">
              <span className="blend-ratio-pct">{pct}%</span> {persona2.name}
            </span>
          </div>
          <input
            type="range"
            className="blend-slider"
            min={0}
            max={1}
            step={0.01}
            value={ratio}
            onChange={(e: ChangeEvent<HTMLInputElement>) => {
              setRatio(Number(e.target.value));
              handleReset();
            }}
          />
          <div className="blend-ratio-ticks">
            <span>A only</span>
            <span>Equal</span>
            <span>B only</span>
          </div>
        </div>
      )}

      {/* Knob preview */}
      {canPreview && blended && (
        <div className="blend-preview-section">
          <h2 className="blend-preview-title">Blended Preview</h2>
          <div className="blend-panels-grid">
            {PANELS.map(panel => {
              const panelKnobs = knobDefs.filter(k => k.panel === panel);
              if (panelKnobs.length === 0) return null;
              return (
                <div key={panel} className="blend-panel">
                  <div className="blend-panel-header">
                    <span className="blend-panel-icon">{PANEL_ICONS[panel as PanelName]}</span>
                    <span className="blend-panel-name">{panel}</span>
                  </div>
                  <div className="blend-panel-knobs">
                    {panelKnobs.map(knob => {
                      const val = blended[knob.key] ?? 0.5;
                      const a1 = persona1!.knobs[knob.key] ?? 0.5;
                      const b1 = persona2!.knobs[knob.key] ?? 0.5;
                      return (
                        <div key={knob.key} className="blend-knob-row">
                          <div className="blend-knob-header">
                            <span className="blend-knob-name">{knob.name}</span>
                            <span className="blend-knob-value">{val.toFixed(2)}</span>
                          </div>
                          <div className="blend-knob-track">
                            {/* Ghost markers for A and B */}
                            <div
                              className="blend-knob-ghost blend-knob-ghost-a"
                              style={{ left: `${a1 * 100}%` }}
                              title={`A: ${a1.toFixed(2)}`}
                            />
                            <div
                              className="blend-knob-ghost blend-knob-ghost-b"
                              style={{ left: `${b1 * 100}%` }}
                              title={`B: ${b1.toFixed(2)}`}
                            />
                            <div
                              className="blend-knob-fill"
                              style={{
                                width: `${val * 100}%`,
                                background: PANEL_COLORS[panel as PanelName],
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Save section */}
      {canPreview && (
        <div className="blend-save-section">
          {savedPersona ? (
            <div className="blend-saved-banner">
              <span>✓ Saved as <strong>{savedPersona.name}</strong></span>
              <button
                type="button"
                className="btn btn-secondary blend-save-again"
                onClick={handleReset}
              >
                Blend another
              </button>
            </div>
          ) : (
            <div className="blend-save-form">
              <input
                type="text"
                className="blend-name-input"
                placeholder="Name for new persona…"
                value={blendName}
                onChange={(e: ChangeEvent<HTMLInputElement>) => setBlendName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSave()}
              />
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleSave}
                disabled={saving || !blendName.trim()}
              >
                {saving ? (
                  <>
                    <span className="btn-spinner" />
                    Saving…
                  </>
                ) : (
                  'Save as New Persona'
                )}
              </button>
            </div>
          )}
          {saveError && <p className="blend-save-error">{saveError}</p>}
        </div>
      )}
    </div>
  );
}
