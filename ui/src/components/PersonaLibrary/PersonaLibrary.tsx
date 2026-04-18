import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { personasApi } from '../../api';
import type { PersonaProfile } from '../../types';
import './PersonaLibrary.css';

const BADGE_KNOBS: Array<{ key: keyof PersonaProfile; label: string }> = [
  { key: 'creativity', label: 'Creativity' },
  { key: 'formality', label: 'Formality' },
  { key: 'reasoning_depth', label: 'Reasoning' },
  { key: 'reliability', label: 'Reliability' },
];

function KnobBadge({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  const cls = pct >= 70 ? 'badge-high' : pct >= 40 ? 'badge-mid' : 'badge-low';
  return (
    <div className={`persona-badge ${cls}`}>
      <span className="badge-label">{label}</span>
      <span className="badge-value">{pct}%</span>
    </div>
  );
}

export function PersonaLibrary() {
  const navigate = useNavigate();
  const [personas, setPersonas] = useState<PersonaProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    personasApi.list()
      .then(r => setPersonas(r.data))
      .catch(() => setError('Failed to load personas.'))
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    setError(null);
    try {
      await personasApi.delete(id);
      setPersonas(prev => prev.filter(p => p.id !== id));
    } catch {
      setError('Failed to delete persona.');
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  };

  if (loading) {
    return (
      <div className="persona-library page-container">
        <div className="lib-loading">Loading personas…</div>
      </div>
    );
  }

  return (
    <div className="persona-library page-container">
      <div className="lib-header">
        <div>
          <h1 className="lib-title">Personas</h1>
          <p className="lib-subtitle">
            {personas.length} saved persona{personas.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => navigate('/')}
        >
          + New Persona
        </button>
      </div>

      {error && <p className="lib-error">{error}</p>}

      {personas.length === 0 ? (
        <div className="lib-empty">
          <div className="lib-empty-icon">🧠</div>
          <p>No personas yet. Create one in the Tuning Lab.</p>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate('/')}
          >
            Open Tuning Lab
          </button>
        </div>
      ) : (
        <div className="lib-grid">
          {personas.map(p => (
            <div key={p.id} className="lib-card">
              <div className="lib-card-header">
                <div className="lib-card-avatar">
                  {p.name.charAt(0).toUpperCase()}
                </div>
                <div className="lib-card-meta">
                  <div className="lib-card-name">{p.name}</div>
                  <div className="lib-card-model">{p.model}</div>
                </div>
              </div>

              {p.description && (
                <p className="lib-card-desc">{p.description}</p>
              )}

              <div className="lib-card-badges">
                {BADGE_KNOBS.map(({ key, label }) => (
                  <KnobBadge
                    key={key}
                    label={label}
                    value={typeof p[key] === 'number' ? (p[key] as number) : 0.5}
                  />
                ))}
              </div>

              <div className="lib-card-footer">
                <button
                  type="button"
                  className="btn btn-secondary lib-btn"
                  onClick={() => navigate('/')}
                >
                  Open in Lab
                </button>

                {confirmDeleteId === p.id ? (
                  <div className="lib-confirm-row">
                    <span className="lib-confirm-text">Delete?</span>
                    <button
                      type="button"
                      className="btn btn-danger lib-btn"
                      disabled={deletingId === p.id}
                      onClick={() => handleDelete(p.id)}
                    >
                      {deletingId === p.id ? 'Deleting…' : 'Yes'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary lib-btn"
                      onClick={() => setConfirmDeleteId(null)}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="btn btn-ghost lib-btn"
                    onClick={() => setConfirmDeleteId(p.id)}
                  >
                    Delete
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
