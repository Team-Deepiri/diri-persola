import { useState, useEffect, useRef, type ChangeEvent } from 'react';
import { KnobPanel } from '../KnobPanel';
import { Presets } from '../Presets';
import { knobsApi, presetsApi, personasApi } from '../../api';
import type { KnobDefinition, Preset, PanelName } from '../../types';
import { PANELS } from '../../types';
import './TuningLab.css';

const DEFAULT_KNOBS: Record<string, number> = {
  creativity: 0.5, humor: 0.5, formality: 0.5, verbosity: 0.5, empathy: 0.5, confidence: 0.5,
  openness: 0.5, conscientiousness: 0.5, extraversion: 0.5, agreeableness: 0.5, neuroticism: 0.5,
  reasoning_depth: 0.5, step_by_step: 0.5, creativity_in_reasoning: 0.5, synthetics: 0.5, abstraction: 0.5, patterns: 0.5,
  accuracy: 0.8, reliability: 0.8, caution: 0.5, consistency: 0.8, self_correction: 0.5, transparency: 0.5,
};

export function TuningLab() {
  const [knobs, setKnobs] = useState<KnobDefinition[]>([]);
  const [presets, setPresets] = useState<Record<string, Preset>>({});
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, number>>(DEFAULT_KNOBS);
  const [personaName, setPersonaName] = useState('My Assistant');
  const [personaDescription, setPersonaDescription] = useState('A helpful and versatile AI assistant');
  const [currentPersonaId, setCurrentPersonaId] = useState<string | null>(null);
  const [systemPrompt, setSystemPrompt] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [knobsRes, presetsRes] = await Promise.all([
        knobsApi.getKnobs(),
        presetsApi.list(),
      ]);
      setKnobs(knobsRes.data.knobs);
      setPresets(presetsRes.data.presets);
    } catch (err) {
      console.error('Failed to load data:', err);
    }
  };

  const handleKnobChange = (key: string, value: number) => {
    setValues(prev => ({ ...prev, [key]: value }));
    setActivePreset(null);
  };

  const handlePresetSelect = async (presetId: string) => {
    const preset = presets[presetId];
    if (!preset) return;
    
    setValues(preset.knobs);
    setPersonaName(preset.name);
    setPersonaDescription(preset.description);
    setActivePreset(presetId);
  };

  const handleReset = () => {
    setValues(DEFAULT_KNOBS);
    setPersonaName('My Assistant');
    setPersonaDescription('A helpful and versatile AI assistant');
    setActivePreset(null);
    setSystemPrompt(null);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const persona = {
        name: personaName,
        description: personaDescription,
        ...values,
        model: 'llama3:8b',
        temperature: 0.7,
        max_tokens: 2000,
      };

      if (currentPersonaId) {
        await personasApi.update(currentPersonaId, persona);
      } else {
        const res = await personasApi.create(persona);
        setCurrentPersonaId(res.data.id);
      }
    } catch (err) {
      console.error('Failed to save:', err);
    }
    setSaving(false);
  };

  const handleExport = () => {
    const payload = { name: personaName, description: personaDescription, knobs: values };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `persona-${personaName.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImportFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
      try {
        const data = JSON.parse(ev.target?.result as string);
        if (data.name) setPersonaName(data.name);
        if (data.description) setPersonaDescription(data.description);
        const knobData: Record<string, number> = data.knobs ?? data;
        const merged: Record<string, number> = {};
        for (const key of Object.keys(DEFAULT_KNOBS)) {
          if (typeof knobData[key] === 'number') merged[key] = knobData[key];
        }
        if (Object.keys(merged).length > 0) {
          setValues(prev => ({ ...prev, ...merged }));
          setActivePreset(null);
          setCurrentPersonaId(null);
        }
      } catch {
        console.error('Invalid persona JSON');
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const handlePreview = async () => {
    try {
      const persona = {
        name: personaName,
        description: personaDescription,
        ...values,
        model: 'llama3:8b',
        temperature: 0.7,
        max_tokens: 2000,
      };
      const res = await personasApi.create(persona);
      const promptRes = await personasApi.getSystemPrompt(res.data.id);
      setSystemPrompt(promptRes.data.system_prompt);
    } catch (err) {
      console.error('Failed to preview:', err);
    }
  };

  return (
    <div className="tuning-lab">
      <div className="tuning-header">
        <h1>Tuning Lab</h1>
        <div className="header-actions">
          <button className="btn btn-secondary" onClick={handleExport}>Export</button>
          <button className="btn btn-secondary" onClick={() => importRef.current?.click()}>Import</button>
          <input ref={importRef} type="file" accept=".json" style={{ display: 'none' }} onChange={handleImportFile} />
          <button className="btn btn-secondary" onClick={handleReset}>Reset</button>
          <button className="btn btn-secondary" onClick={handlePreview}>Preview</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      <Presets 
        presets={presets} 
        onSelect={handlePresetSelect}
        activePreset={activePreset}
      />

      <div className="persona-details">
        <input
          type="text"
          className="persona-name-input"
          placeholder="Persona name"
          value={personaName}
          onChange={e => setPersonaName(e.target.value)}
        />
        <textarea
          className="persona-description-input"
          placeholder="Description"
          value={personaDescription}
          onChange={e => setPersonaDescription(e.target.value)}
        />
      </div>

      <div className="panels-grid">
        {PANELS.map(panel => (
          <KnobPanel
            key={panel}
            panel={panel as PanelName}
            knobs={knobs}
            values={values}
            onChange={handleKnobChange}
          />
        ))}
      </div>

      {systemPrompt && (
        <div className="system-prompt-preview">
          <h4>Generated System Prompt</h4>
          <pre>{systemPrompt}</pre>
        </div>
      )}
    </div>
  );
}
