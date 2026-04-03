import { useState, useEffect, useCallback } from 'react';
import { agentsApi, personasApi } from '../../api';
import type { AgentConfig, PersonaProfile } from '../../types';
import { AgentList } from './AgentList';
import { AgentForm } from './AgentForm';
import { AgentCard } from './AgentCard';
import './AgentManager.css';

type View = 'list' | 'cards';

export function AgentManager() {
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [personas, setPersonas] = useState<PersonaProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<View>('list');

  // Form state
  const [formOpen, setFormOpen] = useState(false);
  const [editingAgent, setEditingAgent] = useState<AgentConfig | undefined>(undefined);
  const [saving, setSaving] = useState(false);

  // Invoked agent (for card view from list)
  const [invokedAgent, setInvokedAgent] = useState<AgentConfig | null>(null);

  const personaMap = Object.fromEntries(personas.map(p => [p.id, p.name]));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [agentsRes, personasRes] = await Promise.all([
        agentsApi.list(),
        personasApi.list(),
      ]);
      setAgents(agentsRes.data);
      setPersonas(personasRes.data);
    } catch (err) {
      console.error('Failed to load agents/personas:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = () => {
    setEditingAgent(undefined);
    setFormOpen(true);
  };

  const handleEdit = (agent: AgentConfig) => {
    setEditingAgent(agent);
    setFormOpen(true);
    setInvokedAgent(null);
  };

  const handleSave = async (data: Partial<AgentConfig>) => {
    setSaving(true);
    try {
      if (editingAgent) {
        // No update endpoint in current API — re-create or ignore; use create optimistically
        await agentsApi.create({ ...editingAgent, ...data });
      } else {
        await agentsApi.create(data);
      }
      setFormOpen(false);
      await load();
    } catch (err) {
      console.error('Failed to save agent:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (agentId: string) => {
    if (!window.confirm('Delete this agent? This cannot be undone.')) return;
    // Optimistic removal — API delete endpoint not in current spec, so we update local state only
    setAgents(prev => prev.filter(a => a.agent_id !== agentId));
    if (invokedAgent?.agent_id === agentId) setInvokedAgent(null);
  };

  const handleInvokeFromList = (agent: AgentConfig) => {
    setInvokedAgent(agent);
  };

  return (
    <div className="agent-manager">
      <div className="agent-manager-toolbar">
        <div className="view-toggle">
          <button
            className={`view-btn ${view === 'list' ? 'active' : ''}`}
            onClick={() => setView('list')}
            title="Table view"
          >
            ☰ Table
          </button>
          <button
            className={`view-btn ${view === 'cards' ? 'active' : ''}`}
            onClick={() => setView('cards')}
            title="Card view"
          >
            ⊞ Cards
          </button>
        </div>
      </div>

      {view === 'list' ? (
        <>
          <AgentList
            agents={agents}
            personas={personas}
            loading={loading}
            onEdit={handleEdit}
            onInvoke={handleInvokeFromList}
            onCreate={handleCreate}
            onDelete={handleDelete}
          />

          {/* Inline invocation card shown below the table */}
          {invokedAgent && (
            <div className="agent-manager-invoke-panel">
              <div className="invoke-panel-label">
                Invoking: <strong>{invokedAgent.name}</strong>
                <button
                  className="invoke-panel-close"
                  onClick={() => setInvokedAgent(null)}
                >
                  ✕
                </button>
              </div>
              <AgentCard
                agent={invokedAgent}
                personaName={invokedAgent.persona_id ? personaMap[invokedAgent.persona_id] : undefined}
                onEdit={() => handleEdit(invokedAgent)}
              />
            </div>
          )}
        </>
      ) : (
        <div className="agent-cards-section">
          <div className="agent-cards-header">
            <h2 className="agent-list-title">Agents</h2>
            <button className="btn btn-primary" onClick={handleCreate}>
              + New Agent
            </button>
          </div>

          {loading ? (
            <div className="agent-cards-empty">Loading agents…</div>
          ) : agents.length === 0 ? (
            <div className="agent-cards-empty">
              <p>No agents yet.</p>
              <button className="btn btn-primary" onClick={handleCreate}>
                Create your first agent
              </button>
            </div>
          ) : (
            <div className="agent-cards-grid">
              {agents.map(agent => (
                <AgentCard
                  key={agent.agent_id}
                  agent={agent}
                  personaName={agent.persona_id ? personaMap[agent.persona_id] : undefined}
                  onEdit={() => handleEdit(agent)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {formOpen && (
        <AgentForm
          agent={editingAgent}
          personas={personas}
          onSave={handleSave}
          onCancel={() => setFormOpen(false)}
          saving={saving}
        />
      )}
    </div>
  );
}
