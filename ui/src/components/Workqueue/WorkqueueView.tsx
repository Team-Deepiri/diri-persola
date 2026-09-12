import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import type {
  AuditEvent,
  OrgChartResponse,
  OrgNode,
  WorkBoard,
  WorkTask,
  WorkTaskStatus,
} from '../../types';
import { workqueueApi } from '../../api';
import './WorkqueueView.css';

const COLUMNS: WorkTaskStatus[] = [
  'queued',
  'claimed',
  'in_progress',
  'blocked',
  'done',
  'failed',
];

const STATUS_LABELS: Record<WorkTaskStatus, string> = {
  queued: 'Queued',
  claimed: 'Claimed',
  in_progress: 'In Progress',
  blocked: 'Blocked',
  done: 'Done',
  failed: 'Failed',
};

const EVENT_LABELS: Record<AuditEvent['event_type'], string> = {
  instruction: 'Instruction',
  decision: 'Decision',
  reply: 'Reply',
  status_change: 'Status',
  tool_call: 'Tool call',
};

function errMsg(e: unknown): string {
  if (axios.isAxiosError(e)) {
    return String(e.response?.data?.detail ?? e.message);
  }
  return e instanceof Error ? e.message : 'Request failed';
}

function fmtWhen(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString();
}

export function WorkqueueView() {
  const [org, setOrg] = useState<OrgChartResponse | null>(null);
  const [board, setBoard] = useState<WorkBoard | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [subtask, setSubtask] = useState('');
  const [taskRole, setTaskRole] = useState('');
  const [orgRole, setOrgRole] = useState('');
  const [orgTitle, setOrgTitle] = useState('');
  const [orgReportsTo, setOrgReportsTo] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [orgRes, boardRes, auditRes] = await Promise.all([
        workqueueApi.orgChart(),
        workqueueApi.board(),
        workqueueApi.audit({ limit: 200 }),
      ]);
      setOrg(orgRes.data);
      setBoard(boardRes.data);
      setAudit(auditRes.data);
    } catch (e) {
      setError(errMsg(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const enqueue = async () => {
    if (!subtask.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await workqueueApi.enqueueTask({
        subtask,
        role: taskRole.trim() || undefined,
        origin: 'user',
      });
      setSubtask('');
      setTaskRole('');
      await load();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const tick = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      await workqueueApi.tickTask(id);
      await load();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const upsertNode = async () => {
    if (!orgRole.trim() || !orgTitle.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await workqueueApi.upsertOrgNode({
        role: orgRole.trim(),
        title: orgTitle.trim(),
        reports_to: orgReportsTo.trim() || null,
        email: `${orgRole.trim()}@team.persola.local`,
      });
      setOrgRole('');
      setOrgTitle('');
      setOrgReportsTo('');
      await load();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const deactivateNode = async (role: string) => {
    setBusy(true);
    setError(null);
    try {
      await workqueueApi.deactivateOrgNode(role);
      await load();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const emptyBoard: WorkBoard = {
    queued: [],
    claimed: [],
    in_progress: [],
    blocked: [],
    done: [],
    failed: [],
  };

  const boardData = board ?? emptyBoard;

  return (
    <div className="workqueue-view">
      <header className="workqueue-header">
        <div>
          <h1>Work Queue</h1>
          <p>
            Org chart, kanban task board, and audit trail — tasks fan out from the top of the
            chart and get picked up autonomously by the daemon.
          </p>
        </div>
        <button type="button" className="refresh-btn" onClick={load} disabled={busy}>
          Refresh
        </button>
      </header>

      {error && <p className="error">{error}</p>}

      <div className="workqueue-layout">
        <section className="wq-org panel">
          <h2>Org chart</h2>
          <div className="org-tree">
            {org?.nodes.map((node: OrgNode) => (
              <div key={node.role} className={`org-node${node.active ? '' : ' inactive'}`}>
                <div className="org-node-head">
                  <strong>{node.title}</strong>
                  <span className="org-role">{node.role}</span>
                  {!node.active && <span className="org-inactive-tag">inactive</span>}
                </div>
                <p className="org-reports">
                  {node.reports_to ? `→ reports to ${node.reports_to}` : '→ top of chart'}
                </p>
                <button
                  type="button"
                  className="mini-btn"
                  onClick={() => deactivateNode(node.role)}
                  disabled={busy}
                >
                  Deactivate
                </button>
              </div>
            ))}
            {org && org.nodes.length === 0 && <p className="empty">No nodes yet.</p>}
          </div>

          <div className="wq-form">
            <input
              value={orgRole}
              onChange={(e) => setOrgRole(e.target.value)}
              placeholder="role (e.g. researcher)"
            />
            <input
              value={orgTitle}
              onChange={(e) => setOrgTitle(e.target.value)}
              placeholder="title"
            />
            <input
              value={orgReportsTo}
              onChange={(e) => setOrgReportsTo(e.target.value)}
              placeholder="reports to (optional)"
            />
            <button type="button" onClick={upsertNode} disabled={busy}>
              Add / update node
            </button>
          </div>
        </section>

        <section className="wq-board panel">
          <h2>Task board</h2>
          <div className="wq-form enqueue-row">
            <input
              value={subtask}
              onChange={(e) => setSubtask(e.target.value)}
              placeholder="Describe the task to queue…"
              onKeyDown={(e) => {
                if (e.key === 'Enter') enqueue();
              }}
            />
            <input
              value={taskRole}
              onChange={(e) => setTaskRole(e.target.value)}
              placeholder="role (default: top of chart)"
            />
            <button type="button" onClick={enqueue} disabled={busy || !subtask.trim()}>
              Enqueue
            </button>
          </div>

          <div className="board-columns">
            {COLUMNS.map((status) => (
              <div key={status} className={`board-column col-${status}`}>
                <h3>
                  {STATUS_LABELS[status]}
                  <span className="count">{boardData[status].length}</span>
                </h3>
                <div className="column-cards">
                  {boardData[status].map((task: WorkTask) => (
                    <article key={task.task_id} className="task-card">
                      <div className="task-head">
                        <span className="task-role">{task.role}</span>
                        <span className="task-id">{task.task_id.slice(0, 8)}</span>
                      </div>
                      <p className="task-subtask">{task.subtask}</p>
                      {task.error && <p className="task-error">{task.error}</p>}
                      {task.result && (
                        <p className="task-result">{task.result.slice(0, 200)}</p>
                      )}
                      <div className="task-foot">
                        <span className="task-when">{fmtWhen(task.created_at)}</span>
                        {status === 'queued' && (
                          <button
                            type="button"
                            className="mini-btn"
                            onClick={() => tick(task.task_id)}
                            disabled={busy}
                          >
                            Tick now
                          </button>
                        )}
                      </div>
                    </article>
                  ))}
                  {boardData[status].length === 0 && (
                    <p className="empty">No tasks</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="wq-audit panel">
          <h2>Audit trail</h2>
          <ol className="audit-timeline">
            {audit.map((event) => (
              <li key={event.event_id} className={`audit-event type-${event.event_type}`}>
                <div className="audit-head">
                  <span className="audit-type">{EVENT_LABELS[event.event_type]}</span>
                  <span className="audit-when">{fmtWhen(event.at)}</span>
                </div>
                <p className="audit-summary">{event.summary}</p>
                <p className="audit-meta">
                  {event.actor}
                  {event.recipient ? ` → ${event.recipient}` : ''}
                  {event.task_id ? ` · task ${event.task_id.slice(0, 8)}` : ''}
                </p>
              </li>
            ))}
            {audit.length === 0 && <p className="empty">No events yet.</p>}
          </ol>
        </section>
      </div>
    </div>
  );
}

export default WorkqueueView;
