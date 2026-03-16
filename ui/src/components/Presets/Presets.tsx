import { Preset } from '../../types';
import './Presets.css';

interface PresetsProps {
  presets: Record<string, Preset>;
  onSelect: (presetId: string) => void;
  activePreset: string | null;
}

export function Presets({ presets, onSelect, activePreset }: PresetsProps) {
  return (
    <div className="presets-section">
      <h3 className="presets-title">Quick Presets</h3>
      <div className="presets-grid">
        {Object.entries(presets).map(([id, preset]) => (
          <button
            key={id}
            className={`preset-btn ${activePreset === id ? 'active' : ''}`}
            onClick={() => onSelect(id)}
          >
            {preset.name}
          </button>
        ))}
      </div>
    </div>
  );
}
