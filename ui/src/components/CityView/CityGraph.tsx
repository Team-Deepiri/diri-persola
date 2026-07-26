import { useMemo, useState } from 'react';

export type GraphMember = {
  id: string;
  agent_id: string;
  parent_member_id: string | null;
  role_in_family: string;
  role_label: string | null;
  family_id?: string;
  district?: string;
  knob_overrides?: Record<string, number>;
  personality?: {
    fingerprint?: string | null;
    top_traits?: Array<{ knob: string; value: number }>;
  };
  agent?: { name: string; model?: string } | null;
};

export type GraphPulse = {
  agentId: string;
  kind: 'write' | 'run' | 'spawn' | 'merge';
  at: number;
};

export type GraphFamily = {
  id: string;
  name: string;
  default_district: string;
  members: GraphMember[];
};

type Props = {
  /** Single-family mode (legacy wedge) */
  members?: GraphMember[];
  /** Multi-family city mode (Phase 6) */
  families?: GraphFamily[];
  pulses?: GraphPulse[];
  selectedAgentId?: string | null;
  onSelectAgent?: (member: GraphMember | null) => void;
  /** Phase 7 — show only these districts (empty = all) */
  districtFilter?: string[];
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

const DISTRICT_COLORS: Record<string, string> = {
  build: '#0f766e',
  viz: '#7c3aed',
  research: '#0369a1',
  ops: '#b45309',
};

const DISTRICTS = ['build', 'viz', 'research', 'ops'] as const;

function colorFor(role: string | null | undefined) {
  return ROLE_COLORS[role ?? ''] ?? '#475569';
}

function hueFromFingerprint(fp: string | null | undefined): string | null {
  if (!fp) return null;
  let h = 0;
  for (let i = 0; i < fp.length; i++) h = (h * 31 + fp.charCodeAt(i)) % 360;
  return `hsl(${h} 55% 42%)`;
}

type LaidOut = GraphMember & { x: number; y: number; familyName: string; district: string };

/** Interactive city graph — district columns, family clusters, click-to-inspect. */
export function CityGraph({
  members = [],
  families,
  pulses = [],
  selectedAgentId,
  onSelectAgent,
  districtFilter,
  width = 960,
  height = 520,
}: Props) {
  const [hoverId, setHoverId] = useState<string | null>(null);

  const layout = useMemo(() => {
    const nodes: LaidOut[] = [];
    const edges: Array<{ from: LaidOut; to: LaidOut }> = [];
    const filterSet =
      districtFilter && districtFilter.length > 0 ? new Set(districtFilter) : null;

    const cityFamilies: GraphFamily[] =
      families && families.length > 0
        ? families.filter((f) => !filterSet || filterSet.has(f.default_district))
        : members.length > 0
          ? [
              {
                id: 'single',
                name: 'Family',
                default_district: 'build',
                members,
              },
            ]
          : [];

    if (cityFamilies.length === 0) return { nodes, edges, districtBands: [] as Array<{ d: string; x: number; w: number }> };

    const visibleDistricts = DISTRICTS.filter(
      (d) => !filterSet || filterSet.has(d),
    );
    const padX = 36;
    const padY = 48;
    const colW = (width - padX * 2) / Math.max(visibleDistricts.length, 1);
    const districtBands = visibleDistricts.map((d, i) => ({
      d,
      x: padX + i * colW,
      w: colW,
    }));

    const byDistrict: Record<string, GraphFamily[]> = {
      build: [],
      viz: [],
      research: [],
      ops: [],
    };
    for (const f of cityFamilies) {
      const d = (DISTRICTS as readonly string[]).includes(f.default_district)
        ? f.default_district
        : 'build';
      byDistrict[d].push(f);
    }

    for (const band of districtBands) {
      const fams = byDistrict[band.d];
      if (!fams.length) continue;
      const slotH = (height - padY * 2) / fams.length;

      fams.forEach((fam, fi) => {
        const cx = band.x + band.w / 2;
        const cy = padY + slotH * (fi + 0.5);
        const parents = fam.members.filter((m) => m.role_in_family === 'parent' || !m.parent_member_id);
        const children = fam.members.filter((m) => !parents.includes(m));
        const local: LaidOut[] = [];

        parents.forEach((p, i) => {
          const n: LaidOut = {
            ...p,
            family_id: fam.id,
            district: band.d,
            familyName: fam.name,
            x: cx + (i - (parents.length - 1) / 2) * 28,
            y: cy - 28,
          };
          local.push(n);
          nodes.push(n);
        });

        const ringR = Math.min(52, 18 + children.length * 3.2);
        children.forEach((c, i) => {
          const angle = -Math.PI / 2 + (i / Math.max(children.length, 1)) * Math.PI * 2;
          const n: LaidOut = {
            ...c,
            family_id: fam.id,
            district: band.d,
            familyName: fam.name,
            x: cx + Math.cos(angle) * ringR,
            y: cy + 10 + Math.sin(angle) * ringR * 0.72,
          };
          local.push(n);
          nodes.push(n);
        });

        const byId = Object.fromEntries(local.map((n) => [n.id, n]));
        for (const c of children) {
          if (c.parent_member_id && byId[c.parent_member_id] && byId[c.id]) {
            edges.push({ from: byId[c.parent_member_id], to: byId[c.id] });
          }
        }
      });
    }

    return { nodes, edges, districtBands };
  }, [families, members, width, height, districtFilter]);

  const pulseByAgent = useMemo(() => {
    const now = Date.now();
    const map: Record<string, GraphPulse> = {};
    for (const p of pulses) {
      if (now - p.at > 5000) continue;
      const prev = map[p.agentId];
      if (!prev || p.at >= prev.at) map[p.agentId] = p;
    }
    return map;
  }, [pulses]);

  const hoverNode = layout.nodes.find((n) => n.agent_id === hoverId) ?? null;
  const nodeR = layout.nodes.length > 60 ? 9 : layout.nodes.length > 30 ? 12 : 18;

  if (layout.nodes.length === 0) {
    return <div className="city-graph empty">No agents to graph yet — awaken the city or seed a family.</div>;
  }

  return (
    <div className="city-graph-wrap">
      <svg
        className="city-graph interactive"
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label="Interactive communal city graph"
        onClick={() => onSelectAgent?.(null)}
      >
        <defs>
          <filter id="softGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <radialGradient id="districtWash" cx="50%" cy="40%" r="70%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#e2e8f0" stopOpacity="0.15" />
          </radialGradient>
        </defs>

        {layout.districtBands.map((band) => (
          <g key={band.d}>
            <rect
              x={band.x + 4}
              y={16}
              width={band.w - 8}
              height={height - 28}
              rx={14}
              fill="url(#districtWash)"
              stroke={DISTRICT_COLORS[band.d]}
              strokeOpacity={0.35}
            />
            <text
              x={band.x + band.w / 2}
              y={34}
              textAnchor="middle"
              className="district-label"
              fill={DISTRICT_COLORS[band.d]}
            >
              {band.d.toUpperCase()}
            </text>
          </g>
        ))}

        {layout.edges.map((e, i) => (
          <line
            key={`e-${i}`}
            className="city-edge"
            x1={e.from.x}
            y1={e.from.y}
            x2={e.to.x}
            y2={e.to.y}
          />
        ))}

        {layout.nodes.map((n) => {
          const pulse = pulseByAgent[n.agent_id];
          const selected = selectedAgentId === n.agent_id;
          const hovered = hoverId === n.agent_id;
          const fill =
            hueFromFingerprint(n.personality?.fingerprint) ?? colorFor(n.role_label || n.role_in_family);
          return (
            <g
              key={n.id}
              transform={`translate(${n.x}, ${n.y})`}
              className={`city-node-group${selected ? ' selected' : ''}${hovered ? ' hovered' : ''}`}
              onClick={(ev) => {
                ev.stopPropagation();
                onSelectAgent?.(n);
              }}
              onMouseEnter={() => setHoverId(n.agent_id)}
              onMouseLeave={() => setHoverId(null)}
              style={{ cursor: 'pointer' }}
            >
              {pulse && (
                <circle className={`city-pulse pulse-${pulse.kind}`} r={nodeR + 10} fill="none" stroke={fill} />
              )}
              {selected && <circle r={nodeR + 5} fill="none" stroke="#0f172a" strokeWidth={2} />}
              <circle
                className="city-node"
                r={selected || hovered ? nodeR + 2 : nodeR}
                fill={fill}
                filter={pulse || selected ? 'url(#softGlow)' : undefined}
              />
              {nodeR >= 12 && (
                <text className="city-node-label" textAnchor="middle" y={4} fontSize={nodeR > 14 ? 9 : 7}>
                  {(n.role_label || n.role_in_family || '?').slice(0, 3).toUpperCase()}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {hoverNode && (
        <div
          className="city-tooltip"
          style={{
            left: `${Math.min(92, Math.max(4, (hoverNode.x / width) * 100))}%`,
            top: `${Math.min(88, Math.max(4, (hoverNode.y / height) * 100))}%`,
          }}
        >
          <strong>{hoverNode.agent?.name ?? 'Agent'}</strong>
          <div>
            {hoverNode.role_label || hoverNode.role_in_family} · {hoverNode.district}
          </div>
          <div className="muted">{hoverNode.familyName}</div>
          {hoverNode.personality?.top_traits?.slice(0, 3).map((t) => (
            <div key={t.knob} className="trait">
              {t.knob} {(t.value * 100).toFixed(0)}%
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
