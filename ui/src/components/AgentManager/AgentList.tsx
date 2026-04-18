import type { AgentConfig, PersonaProfile } from '../../types';
import './AgentList.css';

interface AgentListProps {
  agents: AgentConfig[];
  personas: PersonaProfile[];
  loading: boolean;
  onEdit: (agent: AgentConfig) => void;
  onInvoke: (agent: AgentConfig) => void;
  onCreate: () => void;
  onDelete: (agentId: string) => void;
}

export function AgentList({
  agents,
  personas,
  loading,
  onEdit,
  onInvoke,
  onCreate,
  onDelete,
}: AgentListProps) {
  const personaMap = Object.fromEntries(personas.map(p => [p.id, p.name]));

  return (
    <div className="agent-list">
      <div className="agent-list-header">
        <div>
          <h2 className="agent-list-title">Agents</h2>
          <p className="agent-list-subtitle">
            {agents.length} agent{agents.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        <button className="btn btn-primary" onClick={onCreate}>
          + New Agent
        </button>
      </div>

      {loading ? (
        <div className="agent-list-empty">Loading agents…</div>
      ) : agents.length === 0 ? (
        <div className="agent-list-empty">
          <p>No agents yet.</p>
          <button className="btn btn-primary" onClick={onCreate}>
            Create your first agent
          </button>
        </div>
      ) : (
        <div className="agent-table-wrapper">
          <table className="agent-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Role</th>
                <th>Model</th>
                <th>Persona</th>
                <th>Max Tokens</th>
                <th>Memory</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {agents.map(agent => (
                <tr key={agent.agent_id} className="agent-row">
                  <td className="agent-name-cell">
                    <span className="agent-avatar">
                      {agent.name.charAt(0).toUpperCase()}
                    </span>
                    <span>{agent.name}</span>
                  </td>
                  <td className="agent-role-cell">{agent.role || '—'}</td>
                  <td>
                    <span className="agent-model-badge">{agent.model}</span>
                  </td>
                  <td className="agent-persona-cell">
                    {agent.persona_id
                      ? personaMap[agent.persona_id] ?? agent.persona_id
                      : <span className="text-muted">None</span>}
                  </td>
                  <td className="agent-tokens-cell">{agent.max_tokens.toLocaleString()}</td>
                  <td>
                    <span className={`agent-memory-badge ${agent.memory_enabled ? 'on' : 'off'}`}>
                      {agent.memory_enabled ? 'On' : 'Off'}
                    </span>
                  </td>
                  <td>
                    <span className="agent-status-badge active">Active</span>
                  </td>
                  <td className="agent-actions-cell">
                    <button
                      className="btn btn-invoke"
                      onClick={() => onInvoke(agent)}
                      title="Invoke agent"
                    >
                      ▶ Invoke
                    </button>
                    <button
                      className="btn btn-edit"
                      onClick={() => onEdit(agent)}
                      title="Edit agent"
                    >
                      Edit
                    </button>
                    <button
                      className="btn btn-delete"
                      onClick={() => onDelete(agent.agent_id)}
                      title="Delete agent"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
