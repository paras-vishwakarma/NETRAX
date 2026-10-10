// Pure helpers for the NetraX knowledge graph. Adapted to the real backend (GraphResponse):
//   node: { id, label, entity_type: 'PERSON'|'PHONE'|'LOCATION'|..., properties: { icon, color, ... } }
//   edge: { id, source, target, relationship_type, properties: { confidence, verification_status,
//           source_document_id, source_record_id, extraction_method?, ...record details } }
// Nothing is invented: missing values stay "not provided" / "unknown".

import type { GraphResponse } from '../../types';

export const NODE_R = 14;

// Edge confidence buckets (real backend values range roughly 0.65 - 0.95). Tune here.
export const LEVEL_THRESHOLDS = { high: 0.85, medium: 0.7 };
export type Level = 'high' | 'medium' | 'low' | 'unknown';
export const LEVEL_COLOR: Record<Level, string> = { high: '#ef4444', medium: '#f59e0b', low: '#22c55e', unknown: '#64748b' };
export const LEVEL_LABEL: Record<Level, string> = {
  high: `High (≥${Math.round(LEVEL_THRESHOLDS.high * 100)}%)`,
  medium: `Medium (${Math.round(LEVEL_THRESHOLDS.medium * 100)}–${Math.round(LEVEL_THRESHOLDS.high * 100) - 1}%)`,
  low: `Low (<${Math.round(LEVEL_THRESHOLDS.medium * 100)}%)`,
  unknown: 'No confidence value',
};

export type RoleKey = 'topLead' | 'theftOrigin' | 'lastSpotted';
export const ROLE_ORDER: RoleKey[] = ['topLead', 'theftOrigin', 'lastSpotted'];
export const ROLE_META: Record<RoleKey, { color: string; label: string }> = {
  topLead: { color: '#ef4444', label: 'Highest-priority AI lead' },
  theftOrigin: { color: '#22c55e', label: 'Theft origin' },
  lastSpotted: { color: '#3b82f6', label: 'Last spotted' },
};
export const PATH_COLOR = '#ec4899';

export type Origin = 'structured' | 'inferred' | 'unspecified';

export interface GNode {
  id: string;
  name: string;
  entityType: string;
  kind: string; // legend label
  emoji: string;
  flagRoles: RoleKey[];
  details: [string, string][];
  x?: number; y?: number; fx?: number; fy?: number; vx?: number; vy?: number;
}

export interface GLink {
  id: string;
  source: string | GNode;
  target: string | GNode;
  relType: string;
  typeLabel: string;
  emoji: string;
  confidence: number | null;
  level: Level;
  verification: string;
  method: string;
  origin: Origin;
  rows: [string, string][];
  curvature: number;
}

export interface NormalizedGraph {
  nodes: GNode[];
  links: GLink[];
  adjacency: Map<string, Set<string>>;
  skipped: number;
  signature: string;
}

export const esc = (v: unknown): string =>
  String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));

const prettify = (s: string): string => s.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase().replace(/^./, (c) => c.toUpperCase());

// ---- node presentation ----------------------------------------------------------------------
const TYPE_EMOJI: Record<string, { emoji: string; kind: string }> = {
  PERSON: { emoji: '👤', kind: 'Person' },
  VEHICLE: { emoji: '🚗', kind: 'Vehicle' },
  PHONE: { emoji: '📞', kind: 'Phone' },
  ACCOUNT: { emoji: '💰', kind: 'Account' },
};

export function nodePresentation(entityType: string, label: string, props: Record<string, any>): { emoji: string; kind: string } {
  const t = (entityType || '').toUpperCase();
  // The backend has no MALL / WAREHOUSE types: these are LOCATION or ORGANIZATION nodes, so we
  // recognise them from the entity's own name.
  if (t === 'LOCATION' || t === 'ORGANIZATION') {
    if (/\b(mall|plaza|shopping|supermarket)\b/i.test(label)) return { emoji: '🏬', kind: 'Mall' };
    if (/\b(warehouse|godown|depot)\b/i.test(label)) return { emoji: '🏭', kind: 'Warehouse' };
  }
  if (TYPE_EMOJI[t]) return TYPE_EMOJI[t];
  return { emoji: typeof props?.icon === 'string' && props.icon ? props.icon : '●', kind: prettify(t || 'Entity') };
}

const REL_EMOJI: Record<string, string> = { CALLED: '📞', TRANSFERRED_TO: '💰' };

function flagRoles(props: Record<string, any>): RoleKey[] {
  // Only if a backend one day provides these flags. The current API does not.
  const out: RoleKey[] = [];
  if (props?.is_theft_origin === true || props?.theft_origin === true) out.push('theftOrigin');
  if (props?.is_last_spotted === true || props?.last_spotted === true) out.push('lastSpotted');
  if (props?.is_top_lead === true || props?.top_lead === true) out.push('topLead');
  return out;
}

const NODE_SKIP = new Set(['color', 'icon', 'shape', 'is_theft_origin', 'theft_origin', 'is_last_spotted', 'last_spotted', 'is_top_lead', 'top_lead']);
const EDGE_SKIP = new Set(['confidence', 'verification_status', 'source_document_id', 'source_record_id', 'extraction_method']);

function scalarRows(props: Record<string, any>, skip: Set<string>, max: number): [string, string][] {
  const rows: [string, string][] = [];
  Object.entries(props || {}).forEach(([k, v]) => {
    if (rows.length >= max || skip.has(k) || v === null || v === undefined || v === '' || typeof v === 'object') return;
    rows.push([prettify(k), String(v).slice(0, 90)]);
  });
  return rows;
}

// ---- edge classification ---------------------------------------------------------------------
const STRUCTURED_METHODS = new Set(['CDR_PARSE', 'FINANCIAL_PARSE', 'DOCUMENT', 'MANUAL']);

export function edgeOrigin(method: string, props: Record<string, any>): Origin {
  const m = (method || '').toUpperCase();
  if (STRUCTURED_METHODS.has(m)) return 'structured';
  if (/CO_OCCURRENCE|LLM|\bAI\b|INFER|NER|MODEL|HEURISTIC/.test(m) || props?.inferred_from) return 'inferred';
  return 'unspecified';
}

export function levelOf(confidence: number | null): Level {
  if (confidence === null) return 'unknown';
  if (confidence >= LEVEL_THRESHOLDS.high) return 'high';
  if (confidence >= LEVEL_THRESHOLDS.medium) return 'medium';
  return 'low';
}

const endId = (v: unknown): string | undefined => {
  if (v && typeof v === 'object') return (v as { id?: string }).id;
  return v === undefined || v === null ? undefined : String(v);
};
export const linkEndId = endId;

export function normalizeGraph(data: GraphResponse | null | undefined): NormalizedGraph {
  const rawNodes = Array.isArray(data?.nodes) ? data!.nodes : [];
  const rawEdges = Array.isArray(data?.edges) ? data!.edges : [];

  const nodes: GNode[] = [];
  const seen = new Set<string>();
  rawNodes.forEach((n) => {
    if (n?.id === undefined || n?.id === null) return;
    const id = String(n.id);
    if (seen.has(id)) return;
    seen.add(id);
    const props = (n.properties || {}) as Record<string, any>;
    const name = n.label ? String(n.label) : id;
    const pres = nodePresentation(n.entity_type, name, props);
    nodes.push({
      id, name, entityType: n.entity_type || 'ENTITY', kind: pres.kind, emoji: pres.emoji,
      flagRoles: flagRoles(props), details: scalarRows(props, NODE_SKIP, 6),
    });
  });

  const pairs = new Map<string, GLink[]>();
  const links: GLink[] = [];
  let skipped = 0;
  rawEdges.forEach((e, i) => {
    const s = endId(e?.source);
    const t = endId(e?.target);
    if (s === undefined || t === undefined || !seen.has(s) || !seen.has(t)) { skipped += 1; return; }
    const props = (e.properties || {}) as Record<string, any>;
    const rawConf = props.confidence;
    const confidence = typeof rawConf === 'number' && Number.isFinite(rawConf) ? Math.min(1, Math.max(0, rawConf)) : null;
    const method = typeof props.extraction_method === 'string' ? props.extraction_method : '';
    const rel = e.relationship_type || e.label || '';
    const rows: [string, string][] = [];
    if (props.source_record_id) rows.push(['Source record', String(props.source_record_id)]);
    if (props.source_document_id) rows.push(['Source document', String(props.source_document_id).slice(0, 8) + '…']);
    rows.push(...scalarRows(props, EDGE_SKIP, 6));
    const link: GLink = {
      id: String(e.id ?? `${s}|${t}|${i}`), source: s, target: t,
      relType: rel, typeLabel: rel ? prettify(rel) : 'Relationship (type not provided)',
      emoji: REL_EMOJI[rel] || '', confidence, level: levelOf(confidence),
      verification: typeof props.verification_status === 'string' ? props.verification_status : '',
      method, origin: edgeOrigin(method, props), rows, curvature: 0,
    };
    const key = s < t ? `${s}\u0000${t}` : `${t}\u0000${s}`;
    if (!pairs.has(key)) pairs.set(key, []);
    pairs.get(key)!.push(link);
    links.push(link);
  });

  // Fan out parallel / reciprocal edges so they never draw on top of each other.
  pairs.forEach((group) => {
    if (group.length < 2) return;
    group.forEach((l, i) => {
      const dir = (l.source as string) < (l.target as string) ? 1 : -1;
      l.curvature = (i - (group.length - 1) / 2) * 0.3 * dir;
    });
  });

  const adjacency = new Map<string, Set<string>>(nodes.map((n) => [n.id, new Set<string>()]));
  links.forEach((l) => { adjacency.get(l.source as string)!.add(l.target as string); adjacency.get(l.target as string)!.add(l.source as string); });

  const signature = nodes.map((n) => `${n.id}:${n.entityType}:${n.name}:${n.flagRoles.join('+')}`).join('|') + '#'
    + links.map((l) => `${l.id}:${l.source}>${l.target}:${l.relType}:${l.level}:${l.origin}`).join('|');

  return { nodes, links, adjacency, skipped, signature };
}

// ---- layouts ---------------------------------------------------------------------------------
export type LayoutName = 'force' | 'circle' | 'grid' | 'concentric';

const GOLDEN = 2.399963229728653;

/** Deterministic positions: identical on every load. 'force' only seeds; the others are fixed. */
export function applyLayout(nodes: GNode[], layout: LayoutName): void {
  const n = nodes.length;
  const pin = (node: GNode, x: number, y: number) => { node.x = x; node.y = y; node.fx = x; node.fy = y; };
  if (layout === 'circle') {
    const r = Math.max(120, n * 24);
    nodes.forEach((node, i) => pin(node, r * Math.cos((2 * Math.PI * i) / n), r * Math.sin((2 * Math.PI * i) / n)));
  } else if (layout === 'grid') {
    const cols = Math.ceil(Math.sqrt(n));
    nodes.forEach((node, i) => pin(node, (i % cols) * 100 - ((cols - 1) * 50), Math.floor(i / cols) * 100 - ((Math.ceil(n / cols) - 1) * 50)));
  } else if (layout === 'concentric') {
    const groups = new Map<string, GNode[]>();
    nodes.forEach((node) => { if (!groups.has(node.entityType)) groups.set(node.entityType, []); groups.get(node.entityType)!.push(node); });
    let ring = 0;
    groups.forEach((members) => {
      const r = Math.max(110 * (ring + 1), members.length * 26);
      members.forEach((node, i) => pin(node, ring === 0 && members.length === 1 ? 0 : r * Math.cos((2 * Math.PI * i) / members.length), ring === 0 && members.length === 1 ? 0 : r * Math.sin((2 * Math.PI * i) / members.length)));
      ring += 1;
    });
  } else {
    nodes.forEach((node, i) => {
      const r = 46 * Math.sqrt(i + 0.5);
      node.x = r * Math.cos(i * GOLDEN);
      node.y = r * Math.sin(i * GOLDEN);
    });
  }
}

// ---- tooltips (HTML strings; every dynamic value is escaped) ----------------------------------
export function nodeTooltipHtml(node: GNode, roles?: Set<RoleKey>): string {
  const badges = ROLE_ORDER.filter((r) => roles?.has(r))
    .map((r) => `<span class="nx-tip-badge" style="--c:${ROLE_META[r].color}">${esc(ROLE_META[r].label)}</span>`).join('');
  const rows = node.details.map(([k, v]) => `<div><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('');
  const note = roles?.has('topLead') ? '<p class="nx-tip-note">AI-generated lead for investigator review. Not a finding of guilt.</p>' : '';
  return `<div class="nx-tip"><div class="nx-tip-title">${node.emoji} ${esc(node.name)}</div>`
    + `<div class="nx-tip-sub">${esc(node.kind)}${node.name !== node.id ? ` · ID ${esc(node.id.slice(0, 8))}…` : ''}</div>`
    + (badges ? `<div class="nx-tip-badges">${badges}</div>` : '')
    + (rows ? `<div class="nx-tip-rows">${rows}</div>` : '') + note + '</div>';
}

export function linkTooltipHtml(link: GLink, nameOf: (id: string) => string): string {
  const s = nameOf(endId(link.source) as string);
  const t = nameOf(endId(link.target) as string);
  const basis = link.origin === 'structured' ? `Structured record (${link.method})`
    : link.origin === 'inferred' ? `Inferred, not from a direct record${link.method ? ` (${link.method})` : ''}`
      : link.method ? `Not classified (${link.method})` : 'Basis not provided';
  const conf = link.confidence === null ? 'Not provided' : `${Math.round(link.confidence * 100)}%`;
  const ver = link.verification ? prettify(link.verification) : 'Not provided';
  const evidence = link.rows.map(([k, v]) => `<div><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('')
    || '<div><span>Evidence</span><b>Not provided</b></div>';
  return `<div class="nx-tip"><div class="nx-tip-title">${link.emoji ? `${link.emoji} ` : ''}${esc(link.typeLabel)}</div>`
    + `<div class="nx-tip-sub">${esc(s)} → ${esc(t)}</div>`
    + '<div class="nx-tip-rows">'
    + `<div><span>Confidence</span><b style="color:${LEVEL_COLOR[link.level]}">${esc(conf)}</b></div>`
    + `<div><span>Status</span><b>${esc(ver)}</b></div>`
    + `<div><span>Basis</span><b>${esc(basis)}</b></div>${evidence}</div>`
    + (link.origin === 'inferred' ? '<p class="nx-tip-note">Inferred automatically. Verify before acting on it.</p>' : '') + '</div>';
}

export function withAlpha(hex: string, a: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}
