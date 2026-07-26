import { useMemo, useState } from 'react';
import type { GraphFamily, GraphMember, GraphPulse } from './CityGraph';
import './CityOverview.css';

export type OverviewGeneration = {
  generation: number;
  living: number;
  deceased: number;
  productivity_index: number;
  avg_structured_thinking: number;
  avg_growth: number;
};

export type OverviewFamilyMeta = {
  family_id: string;
  name: string;
  district: string;
  cohesion: number;
  efficiency: number;
  living: number;
  deceased: number;
  goals?: string[];
  dreams?: string[];
};

type Props = {
  families: GraphFamily[];
  familyMeta?: OverviewFamilyMeta[];
  generations?: OverviewGeneration[];
  pulses?: GraphPulse[];
  living?: number;
  deceased?: number;
  continuityOk?: boolean;
  selectedAgentId?: string | null;
  onSelectAgent?: (member: GraphMember | null) => void;
  width?: number;
  height?: number;
};

const DISTRICTS = ['build', 'viz', 'research', 'ops'] as const;
const DISTRICT_COLORS: Record<string, string> = {
  build: '#1a7a6d',
  viz: '#5b4bb4',
  research: '#1d6fa5',
  ops: '#b45309',
};

type Laid = GraphMember & {
  x: number;
  y: number;
  familyName: string;
  district: string;
  cohesion: number;
};

function clamp(n: number, a: number, b: number) {
  return Math.max(a, Math.min(b, n));
}

/** Overall city visualization — one composition of districts, life, and generations. */
export function CityOverview({
  families,
  familyMeta = [],
  generations = [],
  pulses = [],
  living = 0,
  deceased = 0,
  continuityOk,
  selectedAgentId,
  onSelectAgent,
  width = 1100,
  height = 640,
}: Props) {
  const [hoverId, setHoverId] = useState<string | null>(null);
  const cx = width / 2;
  const cy = height / 2 + 8;

  const metaById = useMemo(() => {
    const m: Record<string, OverviewFamilyMeta> = {};
    for (const f of familyMeta) m[f.family_id] = f;
    return m;
  }, [familyMeta]);

  const layout = useMemo(() => {
    const nodes: Laid[] = [];
    const lineage: Array<{ from: Laid; to: Laid }> = [];
    const legacy: Array<{ from: Laid; to: Laid }> = [];

    const byDistrict: Record<string, GraphFamily[]> = {
      build: [],
      viz: [],
      research: [],
      ops: [],
    };
    for (const f of families) {
      const d = (DISTRICTS as readonly string[]).includes(f.default_district)
        ? f.default_district
        : 'build';
      byDistrict[d].push(f);
    }

    // Four district petals around the core
    const petalR = Math.min(width, height) * 0.28;
    DISTRICTS.forEach((d, di) => {
      const angle = -Math.PI / 2 + (di / 4) * Math.PI * 2;
      const px = cx + Math.cos(angle) * petalR;
      const py = cy + Math.sin(angle) * petalR * 0.92;
      const fams = byDistrict[d];
      fams.forEach((fam, fi) => {
        const meta = metaById[fam.id];
        const cohesion = meta?.cohesion ?? 0.5;
        const spread = 38 + fams.length * 6;
        const fAngle = angle + (fi - (fams.length - 1) / 2) * 0.22;
        const fx = px + Math.cos(fAngle) * (fi * 12);
        const fy = py + Math.sin(fAngle) * (fi * 10);

        const livingMembers = fam.members.filter((m) => (m.life_status || 'alive') !== 'deceased');
        const deadMembers = fam.members.filter((m) => (m.life_status || '') === 'deceased');
        const ring = livingMembers.length ? livingMembers : fam.members;
        const local: Laid[] = [];

        ring.forEach((m, i) => {
          const a = -Math.PI / 2 + (i / Math.max(ring.length, 1)) * Math.PI * 2;
          const rr = clamp(16 + ring.length * 2.2, 16, spread);
          const n: Laid = {
            ...m,
            family_id: fam.id,
            district: d,
            familyName: fam.name,
            cohesion,
            x: fx + Math.cos(a) * rr,
            y: fy + Math.sin(a) * rr * 0.78,
          };
          local.push(n);
          nodes.push(n);
        });

        // Deceased slightly outward as ghosts
        deadMembers.forEach((m, i) => {
          if (livingMembers.some((l) => l.id === m.id)) return;
          const a = Math.PI / 2 + (i / Math.max(deadMembers.length, 1)) * Math.PI;
          const n: Laid = {
            ...m,
            family_id: fam.id,
            district: d,
            familyName: fam.name,
            cohesion,
            x: fx + Math.cos(a) * (spread + 8),
            y: fy + Math.sin(a) * (spread * 0.55),
          };
          local.push(n);
          nodes.push(n);
        });

        const byId = Object.fromEntries(local.map((n) => [n.id, n]));
        for (const m of local) {
          if (m.parent_member_id && byId[m.parent_member_id] && byId[m.id]) {
            lineage.push({ from: byId[m.parent_member_id], to: byId[m.id] });
          }
          if (m.successor_of_id && byId[m.successor_of_id] && byId[m.id]) {
            legacy.push({ from: byId[m.successor_of_id], to: byId[m.id] });
          }
        }
        // Fallback legacy inference when successor_of_id missing
        for (const dead of local.filter((n) => (n.life_status || '') === 'deceased')) {
          if (legacy.some((e) => e.from.id === dead.id)) continue;
          const heir = local.find(
            (n) =>
              (n.life_status || 'alive') !== 'deceased' &&
              (n.generation ?? 0) > (dead.generation ?? 0) &&
              (n.role_label === dead.role_label || n.parent_member_id === dead.id),
          );
          if (heir) legacy.push({ from: dead, to: heir });
        }

        void spread;
      });
    });

    return { nodes, lineage, legacy, byDistrict };
  }, [families, metaById, cx, cy, width, height]);

  const pulseByAgent = useMemo(() => {
    const now = Date.now();
    const map: Record<string, GraphPulse> = {};
    for (const p of pulses) {
      if (now - p.at > 5000) continue;
      map[p.agentId] = p;
    }
    return map;
  }, [pulses]);

  const genRing = useMemo(() => {
    const r0 = Math.min(width, height) * 0.42;
    return generations.map((g, i) => {
      const start = -Math.PI / 2 + (i / Math.max(generations.length, 1)) * Math.PI * 2;
      const sweep = (1 / Math.max(generations.length, 1)) * Math.PI * 2 * 0.85;
      return { ...g, r: r0, start, sweep };
    });
  }, [generations, width, height]);

  const hover = layout.nodes.find((n) => n.agent_id === hoverId) ?? null;
  const nodeR = layout.nodes.length > 80 ? 7 : layout.nodes.length > 40 ? 9 : 12;

  if (families.length === 0) {
    return (
      <div className="city-overview empty">
        <div className="overview-empty-copy">
          <span className="brand">Persola</span>
          <p>Awaken the city to see the overall ecosystem — districts, generations, and legacy.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="city-overview">
      <svg
        className="overview-svg"
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label="Overall Persola city ecosystem visualization"
        onClick={() => onSelectAgent?.(null)}
      >
        <defs>
          <radialGradient id="coreGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#f8fafc" stopOpacity="0.95" />
            <stop offset="55%" stopColor="#ccfbf1" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#e2e8f0" stopOpacity="0" />
          </radialGradient>
          <filter id="softBlur" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="3" />
          </filter>
          <linearGradient id="legacyStroke" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#94a3b8" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#0f766e" stopOpacity="0.75" />
          </linearGradient>
        </defs>

        {/* Atmosphere */}
        <rect width={width} height={height} fill="url(#overviewWash)" className="overview-wash" />
        <circle className="breath-ring" cx={cx} cy={cy} r={Math.min(width, height) * 0.2} />
        <circle className="breath-ring delay" cx={cx} cy={cy} r={Math.min(width, height) * 0.28} />

        {/* Generation outer arcs */}
        <g className="gen-orbit">
          {genRing.map((g) => {
            const x1 = cx + Math.cos(g.start) * g.r;
            const y1 = cy + Math.sin(g.start) * g.r;
            const x2 = cx + Math.cos(g.start + g.sweep) * g.r;
            const y2 = cy + Math.sin(g.start + g.sweep) * g.r;
            const large = g.sweep > Math.PI ? 1 : 0;
            const thick = 6 + g.productivity_index * 10;
            return (
              <g key={g.generation}>
                <path
                  d={`M ${x1} ${y1} A ${g.r} ${g.r} 0 ${large} 1 ${x2} ${y2}`}
                  fill="none"
                  stroke="#0f766e"
                  strokeOpacity={0.25 + g.living * 0.02}
                  strokeWidth={thick}
                  strokeLinecap="round"
                />
                <text
                  x={cx + Math.cos(g.start + g.sweep / 2) * (g.r + 18)}
                  y={cy + Math.sin(g.start + g.sweep / 2) * (g.r + 18)}
                  textAnchor="middle"
                  className="gen-label-svg"
                >
                  G{g.generation}
                </text>
              </g>
            );
          })}
        </g>

        {/* District petals */}
        {DISTRICTS.map((d, di) => {
          const angle = -Math.PI / 2 + (di / 4) * Math.PI * 2;
          const petalR = Math.min(width, height) * 0.28;
          const px = cx + Math.cos(angle) * petalR;
          const py = cy + Math.sin(angle) * petalR * 0.92;
          const count = layout.byDistrict[d]?.length ?? 0;
          return (
            <g key={d}>
              <circle
                cx={px}
                cy={py}
                r={58 + count * 4}
                fill={DISTRICT_COLORS[d]}
                fillOpacity={0.08}
                stroke={DISTRICT_COLORS[d]}
                strokeOpacity={0.35}
                strokeWidth={1.5}
              />
              <text
                x={px}
                y={py - 68 - count * 2}
                textAnchor="middle"
                className="district-title"
                fill={DISTRICT_COLORS[d]}
              >
                {d.toUpperCase()}
              </text>
            </g>
          );
        })}

        {/* Core */}
        <circle cx={cx} cy={cy} r={72} fill="url(#coreGlow)" />
        <circle cx={cx} cy={cy} r={54} className="core-disk" />
        <text x={cx} y={cy - 10} textAnchor="middle" className="core-brand">
          Persola
        </text>
        <text x={cx} y={cy + 12} textAnchor="middle" className="core-stat">
          {living} living
        </text>
        <text x={cx} y={cy + 30} textAnchor="middle" className="core-sub">
          {deceased} remembered
          {continuityOk === true ? ' · continuity' : continuityOk === false ? ' · at risk' : ''}
        </text>

        {/* Edges */}
        {layout.lineage.map((e, i) => (
          <line
            key={`lin-${i}`}
            x1={e.from.x}
            y1={e.from.y}
            x2={e.to.x}
            y2={e.to.y}
            className="overview-lineage"
          />
        ))}
        {layout.legacy.map((e, i) => (
          <path
            key={`leg-${i}`}
            d={`M ${e.from.x} ${e.from.y} Q ${cx} ${cy} ${e.to.x} ${e.to.y}`}
            fill="none"
            stroke="url(#legacyStroke)"
            strokeWidth={1.6}
            strokeDasharray="4 4"
            className="legacy-arc"
          />
        ))}

        {/* Agents */}
        {layout.nodes.map((n) => {
          const dead = (n.life_status || 'alive') === 'deceased';
          const pulse = pulseByAgent[n.agent_id];
          const selected = selectedAgentId === n.agent_id;
          const fill = dead ? '#94a3b8' : DISTRICT_COLORS[n.district] || '#475569';
          return (
            <g
              key={n.id}
              transform={`translate(${n.x}, ${n.y})`}
              className={`ov-node${dead ? ' dead' : ''}${selected ? ' selected' : ''}`}
              onClick={(ev) => {
                ev.stopPropagation();
                onSelectAgent?.(n);
              }}
              onMouseEnter={() => setHoverId(n.agent_id)}
              onMouseLeave={() => setHoverId(null)}
            >
              {pulse && !dead && (
                <circle className="ov-pulse" r={nodeR + 8} fill="none" stroke={fill} />
              )}
              <circle
                r={selected ? nodeR + 2 : nodeR}
                fill={fill}
                fillOpacity={dead ? 0.35 : 0.55 + n.cohesion * 0.4}
                stroke={dead ? '#64748b' : '#0f172a'}
                strokeOpacity={dead ? 0.5 : 0.15}
                strokeDasharray={dead ? '3 2' : undefined}
                strokeWidth={selected ? 2 : 1}
              />
              {nodeR >= 9 && (
                <text textAnchor="middle" y={3} className="ov-node-label">
                  {dead ? '†' : (n.role_label || '?').slice(0, 2).toUpperCase()}
                </text>
              )}
              {!dead && (n.generation ?? 0) > 0 && (
                <text textAnchor="middle" y={nodeR + 10} className="ov-gen-badge">
                  G{n.generation}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {hover && (
        <div
          className="overview-tooltip"
          style={{
            left: `${clamp((hover.x / width) * 100, 4, 88)}%`,
            top: `${clamp((hover.y / height) * 100, 4, 86)}%`,
          }}
        >
          <strong>{hover.agent?.name ?? 'Agent'}</strong>
          <div>
            {hover.role_label || hover.role_in_family} · {hover.district} · G{hover.generation ?? 0}
            {(hover.life_status || '') === 'deceased' ? ' · deceased' : ''}
          </div>
          <div className="muted">{hover.familyName}</div>
          {hover.goals?.[0] && <div className="tip-goal">{hover.goals[0]}</div>}
        </div>
      )}

      <div className="overview-legend">
        <span>
          <i className="swatch living" /> living
        </span>
        <span>
          <i className="swatch dead" /> deceased
        </span>
        <span>
          <i className="swatch legacy" /> legacy
        </span>
        <span>outer ring = generations</span>
      </div>
    </div>
  );
}
