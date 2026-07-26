import { useMemo } from 'react';

export type GraphMember = {
  id: string;
  agent_id: string;
  parent_member_id: string | null;
  role_in_family: string;
  role_label: string | null;
  agent?: { name: string } | null;
};

export type GraphPulse = {
  agentId: string;
  kind: 'write' | 'run' | 'spawn' | 'merge';
  at: number;
};

type Props = {
  members: GraphMember[];
  pulses?: GraphPulse[];
  width?: number;
  height?: number;
};

const ROLE_COLORS: Record<string, string> = {
  coordinator: '#0f766e',
  analyst: '#0369a1',
  creative: '#b45309',
  executor: '#15803d',
  empath: '#be185d',
  builder: '#4338ca',
};

function colorFor(role: string | null | undefined) {
  return ROLE_COLORS[role ?? ''] ?? '#475569';
}

/** Layout parent on top row, children evenly on bottom — no external graph lib. */
export function CityGraph({ members, pulses = [], width = 640, height = 280 }: Props) {
  const layout = useMemo(() => {
    const parents = members.filter((m) => m.role_in_family === 'parent' || !m.parent_member_id);
    const children = members.filter((m) => !parents.includes(m));
    const nodes: Array<GraphMember & { x: number; y: number }> = [];

    const topY = 70;
    const botY = 200;
    const pad = 70;

    parents.forEach((p, i) => {
      const span = parents.length + 1;
      nodes.push({
        ...p,
        x: (width * (i + 1)) / span,
        y: topY,
      });
    });

    children.forEach((c, i) => {
      const span = Math.max(children.length + 1, 2);
      nodes.push({
        ...c,
        x: pad + ((width - pad * 2) * (i + 1)) / span,
        y: botY,
      });
    });

    const byMemberId = Object.fromEntries(nodes.map((n) => [n.id, n]));
    const edges = children
      .filter((c) => c.parent_member_id && byMemberId[c.parent_member_id] && byMemberId[c.id])
      .map((c) => ({
        from: byMemberId[c.parent_member_id!],
        to: byMemberId[c.id],
      }));

    return { nodes, edges };
  }, [members, width]);

  const pulseByAgent = useMemo(() => {
    const now = Date.now();
    const map: Record<string, GraphPulse> = {};
    for (const p of pulses) {
      if (now - p.at > 4000) continue;
      const prev = map[p.agentId];
      if (!prev || p.at >= prev.at) map[p.agentId] = p;
    }
    return map;
  }, [pulses]);

  if (members.length === 0) {
    return <div className="city-graph empty">No agents to graph yet.</div>;
  }

  return (
    <svg
      className="city-graph"
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height={height}
      role="img"
      aria-label="Family lineage graph"
    >
      <defs>
        <filter id="softGlow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {layout.edges.map((e, i) => (
        <line
          key={`e-${i}`}
          className="city-edge"
          x1={e.from.x}
          y1={e.from.y + 22}
          x2={e.to.x}
          y2={e.to.y - 22}
        />
      ))}

      {layout.nodes.map((n) => {
        const pulse = pulseByAgent[n.agent_id];
        const fill = colorFor(n.role_label || n.role_in_family);
        const label = n.agent?.name ?? n.role_label ?? 'agent';
        return (
          <g key={n.id} transform={`translate(${n.x}, ${n.y})`}>
            {pulse && (
              <circle
                className={`city-pulse pulse-${pulse.kind}`}
                r={34}
                fill="none"
                stroke={fill}
              />
            )}
            <circle className="city-node" r={22} fill={fill} filter={pulse ? 'url(#softGlow)' : undefined} />
            <text className="city-node-label" textAnchor="middle" y={4}>
              {(n.role_label || n.role_in_family || '?').slice(0, 3).toUpperCase()}
            </text>
            <text className="city-node-name" textAnchor="middle" y={40}>
              {label.length > 14 ? `${label.slice(0, 12)}…` : label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
