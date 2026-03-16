import { KnobDefinition, PanelName, PANEL_ICONS, PANEL_COLORS } from '../../types';
import './KnobPanel.css';

interface KnobPanelProps {
  panel: PanelName;
  knobs: KnobDefinition[];
  values: Record<string, number>;
  onChange: (key: string, value: number) => void;
}

export function KnobPanel({ panel, knobs, values, onChange }: KnobPanelProps) {
  const panelKnobs = knobs.filter(k => k.panel === panel);

  return (
    <div className="knob-panel">
      <div className="panel-header">
        <div 
          className="panel-icon" 
          style={{ background: PANEL_COLORS[panel] }}
        >
          {PANEL_ICONS[panel]}
        </div>
        <div className="panel-info">
          <h2 className="panel-title">{panel}</h2>
          <span className="panel-subtitle">
            {panel === 'Creativity' && 'Communication style'}
            {panel === 'Personality' && 'Behavioral traits'}
            {panel === 'Thinking' && 'Reasoning style'}
            {panel === 'Reliability' && 'Accuracy & trust'}
          </span>
        </div>
      </div>
      
      <div className="knobs-list">
        {panelKnobs.map(knob => (
          <div key={knob.key} className="knob-item">
            <div className="knob-header">
              <label className="knob-label">{knob.name}</label>
              <span className="knob-value">
                {(values[knob.key] ?? knob.default).toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              className="knob-slider"
              min={knob.min_value}
              max={knob.max_value}
              step={knob.step}
              value={values[knob.key] ?? knob.default}
              onChange={e => onChange(knob.key, parseFloat(e.target.value))}
            />
            <p className="knob-description">{knob.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
