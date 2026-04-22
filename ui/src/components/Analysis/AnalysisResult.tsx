import { useState } from 'react';
import type { AnalysisExtractResponse, KnobDefinition, PersonaProfile } from '../../types';
import { PANELS, PANEL_COLORS, PANEL_ICONS, type PanelName } from '../../types';
import './AnalysisResult.css';

interface AnalysisResultProps {
  result: AnalysisExtractResponse;
  knobDefs: KnobDefinition[];
  onCreatePersona: (name: string) => void;
  onOpenPersona: (persona: PersonaProfile) => void;
  createdPersona: PersonaProfile | null;
  creating: boolean;
}

const CONFIDENCE_LABEL = (c: number) => {
  if (c >= 0.75) return { label: 'High', cls: 'conf-high' };
  if (c >= 0.45) return { label: 'Medium', cls: 'conf-medium' };
  return { label: 'Low', cls: 'conf-low' };
};

export function AnalysisResult({
  result,
  knobDefs,
  onCreatePersona,
  onOpenPersona,
  createdPersona,
  creating,
}: AnalysisResultProps) {
  const [personaName, setPersonaName] = useState('');
  const { label: confLabel, cls: confCls } = CONFIDENCE_LABEL(result.confidence);

  const handleCreate = () => {
    const name = personaName.trim();
    if (!name) return;
    onCreatePersona(name);
  };

  // Knobs grouped by panel
  const knobsByPanel: Record<PanelName, KnobDefinition[]> = {
    Creativity: [],
    Personality: [],
    Thinking: [],
    Reliability: [],
  };
  for (const def of knobDefs) {
    const panel = def.panel as PanelName;
    if (panel in knobsByPanel) {
      knobsByPanel[panel].push(def);
    }
  }

  return (
    <div className="analysis-result">
      {/* ── Header ── */}
      <div className="result-header">
        <div className="result-header-left">
          <h3 className="result-title">Analysis Results</h3>
          <span className={`conf-badge ${confCls}`}>
            {confLabel} confidence — {Math.round(result.confidence * 100)}%
          </span>
        </div>

        {/* Confidence bar */}
        <div className="conf-bar-wrap" title={`Confidence: ${Math.round(result.confidence * 100)}%`}>
          <div
            className={`conf-bar-fill ${confCls}`}
            style={{ width: `${Math.round(result.confidence * 100)}%` }}
          />
        </div>
      </div>

      {/* ── Notes ── */}
      {result.notes && (
        <div className="result-notes">
          <span className="result-notes-icon">💡</span>
          <p className="result-notes-text">{result.notes}</p>
        </div>
      )}

      {/* ── Knob preview panels ── */}
      <div className="result-panels-grid">
        {PANELS.map(panel => {
          const defs = knobsByPanel[panel];
          if (defs.length === 0) return null;
          return (
            <div key={panel} className="result-panel">
              <div className="result-panel-header">
                <span
                  className="result-panel-icon"
                  style={{ background: PANEL_COLORS[panel] }}
                >
                  {PANEL_ICONS[panel]}
                </span>
                <span className="result-panel-title">{panel}</span>
              </div>

              <div className="result-knobs-list">
                {defs.map(def => {
                  const raw = result.knobs[def.key] ?? 0.5;
                  const pct = Math.round(raw * 100);
                  const isHigh = raw >= 0.65;
                  const isLow = raw <= 0.35;
                  return (
                    <div key={def.key} className="result-knob-row">
                      <div className="result-knob-label-row">
                        <span className="result-knob-name">{def.name}</span>
                        <span className={`result-knob-pct ${isHigh ? 'pct-high' : isLow ? 'pct-low' : 'pct-mid'}`}>
                          {pct}%
                        </span>
                      </div>
                      <div className="result-knob-track">
                        <div
                          className="result-knob-fill"
                          style={{
                            width: `${pct}%`,
                            background: PANEL_COLORS[panel],
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

      {/* ── Create Persona section ── */}
      <div className="result-create-section">
        {createdPersona ? (
          <div className="result-created-banner">
            <span className="created-check">✓</span>
            <div className="created-info">
              <span className="created-label">Persona created:</span>
              <strong className="created-name">{createdPersona.name}</strong>
            </div>
            <button
              className="btn btn-secondary"
              onClick={() => onOpenPersona(createdPersona)}
            >
              Open in Tuning Lab →
            </button>
          </div>
        ) : (
          <div className="result-create-form">
            <h4 className="result-create-title">Save as Persona</h4>
            <p className="result-create-subtitle">
              Save these extracted knob values as a persona you can use with agents.
            </p>
            <div className="result-create-row">
              <input
                className="result-persona-name-input"
                type="text"
                placeholder="e.g. My Writing Style"
                value={personaName}
                onChange={e => setPersonaName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleCreate()}
                maxLength={80}
                disabled={creating}
              />
              <button
                className="btn btn-primary"
                onClick={handleCreate}
                disabled={!personaName.trim() || creating}
              >
                {creating ? (
                  <>
                    <span className="btn-spinner" />
                    Creating…
                  </>
                ) : (
                  '+ Create Persona'
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
