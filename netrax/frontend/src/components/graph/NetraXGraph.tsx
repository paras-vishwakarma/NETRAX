import {
  forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState,
  type ReactNode,
} from 'react';
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d';
import type { GraphResponse } from '../../types';
import {
  NODE_R, LEVEL_COLOR, LEVEL_LABEL, ROLE_META, ROLE_ORDER, PATH_COLOR,
  normalizeGraph, applyLayout, nodeTooltipHtml, linkTooltipHtml, linkEndId, withAlpha,
  type GNode, type GLink, type LayoutName, type RoleKey,
} from './graphUtils';
import './NetraXGraph.css';

export type { LayoutName };

const EMOJI_FONT = '"Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",sans-serif';

export interface NetraXGraphHandle {
  focusNode: (id: string) => boolean;
  fitView: () => void;
  zoomBy: (factor: number) => void;
  toggleFullscreen: () => void;
  exportPng: () => string | null;
  clearSelection: () => void;
}

export interface SelectedNodeInfo { id: string; label: string; type: string }

interface Props {
  data?: GraphResponse | null;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  layout?: LayoutName;
  /** Optional real-data highlights: theft origin (green), last spotted (blue), top AI lead (red). */
  highlights?: { theftOriginId?: string | null; lastSpottedId?: string | null; topLeadId?: string | null };
  /** Node to highlight and centre (e.g. the entity behind a clicked lead). */
  focusNodeId?: string | null;
  /** Change this value to re-focus the same node. */
  focusToken?: unknown;
  /** Shortest-path result to highlight in pink. */
  pathHighlight?: { nodeIds: string[]; edgeIds: string[] } | null;
  hideEmptyState?: boolean;
  onNodeSelect?: (node: SelectedNodeInfo | null) => void;
  onFullscreenChange?: (isFull: boolean) => void;
  className?: string;
  /** Overlays (controls, drawers) rendered INSIDE the graph container so fullscreen includes them. */
  children?: ReactNode;
}

// Small deterministic "no overlap" force (keeps node + ring footprints apart).
function collideForce(radius: number) {
  let nodes: any[] = [];
  const force: any = () => {
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = nodes[i]; const b = nodes[j];
        let dx = b.x - a.x; let dy = b.y - a.y;
        if (dx === 0 && dy === 0) { dx = (i - j) * 0.01; dy = (j - i) * 0.013; }
        const d = Math.hypot(dx, dy);
        const min = radius * 2;
        if (d < min) {
          const k = ((min - d) / d) * 0.5;
          a.vx -= dx * k; a.vy -= dy * k; b.vx += dx * k; b.vy += dy * k;
        }
      }
    }
  };
  force.initialize = (n: any[]) => { nodes = n; };
  return force;
}

const NetraXGraph = forwardRef<NetraXGraphHandle, Props>(function NetraXGraph(
  {
    data, loading = false, error = null, onRetry, layout = 'force', highlights, focusNodeId, focusToken,
    pathHighlight, hideEmptyState = false, onNodeSelect, onFullscreenChange, className = '', children,
  },
  ref,
) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<ForceGraphMethods<any, any> | undefined>(undefined);
  const settledRef = useRef(false);
  const pendingFocus = useRef<string | null>(null);
  const sigRef = useRef<{ key: string; graph: { nodes: GNode[]; links: GLink[] } }>({ key: '', graph: { nodes: [], links: [] } });
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [nativeFull, setNativeFull] = useState(false);
  const [cssFull, setCssFull] = useState(false);

  // ---- data: the same graph object is reused unless content or layout really changed ----
  const normalized = useMemo(() => normalizeGraph(data), [data]);
  const key = `${normalized.signature}@${layout}`;
  if (sigRef.current.key !== key) {
    const nodes = normalized.nodes.map((n) => ({ ...n })); // fresh copies: the library mutates them
    applyLayout(nodes, layout);
    sigRef.current = { key, graph: { nodes, links: normalized.links.map((l) => ({ ...l })) } };
  }
  const graphData = sigRef.current.graph;
  const { adjacency } = normalized;
  const nodeIndex = useMemo(() => new Map(graphData.nodes.map((n) => [n.id, n])), [graphData]);
  const nameOf = useCallback((id: string) => nodeIndex.get(id)?.name ?? String(id), [nodeIndex]);

  const theftId = highlights?.theftOriginId;
  const spottedId = highlights?.lastSpottedId;
  const leadId = highlights?.topLeadId;
  const roleMap = useMemo(() => {
    const m = new Map<string, Set<RoleKey>>();
    const add = (id: string | null | undefined, r: RoleKey) => {
      if (!id) return;
      if (!m.has(String(id))) m.set(String(id), new Set());
      m.get(String(id))!.add(r);
    };
    graphData.nodes.forEach((n) => n.flagRoles.forEach((r) => add(n.id, r)));
    add(theftId, 'theftOrigin'); add(spottedId, 'lastSpotted'); add(leadId, 'topLead');
    return m;
  }, [graphData, theftId, spottedId, leadId]);

  const pathNodes = useMemo(() => new Set(pathHighlight?.nodeIds ?? []), [pathHighlight]);
  const pathEdges = useMemo(() => new Set(pathHighlight?.edgeIds ?? []), [pathHighlight]);
  const hasPath = pathNodes.size > 0;

  // ---- container size (handles sidebar changes, window resize and fullscreen) ----
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize((p) => (Math.abs(p.w - width) < 1 && Math.abs(p.h - height) < 1 ? p : { w: Math.floor(width), h: Math.floor(height) }));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const ready = size.w > 0 && size.h > 0 && graphData.nodes.length > 0;

  // ---- forces: spread out + never overlap (set before the first layout runs) ----
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    (fg.d3Force('charge') as any)?.strength(-340).distanceMax(600);
    (fg.d3Force('link') as any)?.distance(135).strength(0.4);
    fg.d3Force('collide', collideForce(NODE_R + 18));
  }, [ready, graphData]);

  useEffect(() => { settledRef.current = false; }, [graphData]);
  useEffect(() => { if (selectedId && !nodeIndex.has(selectedId)) setSelectedId(null); }, [nodeIndex, selectedId]);

  // ---- view helpers ----
  const fitView = useCallback((ms = 400) => { fgRef.current?.zoomToFit(ms, 60); }, []);
  const zoomBy = useCallback((f: number) => { const fg = fgRef.current; if (fg) fg.zoom(fg.zoom() * f, 250); }, []);

  const emitSelect = useCallback((id: string | null) => {
    const n = id ? nodeIndex.get(id) : null;
    onNodeSelect?.(n ? { id: n.id, label: n.name, type: n.entityType } : null);
  }, [nodeIndex, onNodeSelect]);

  const focusNode = useCallback((id: string) => {
    const k = String(id);
    const node = nodeIndex.get(k);
    if (!node) return false;
    setSelectedId(k);
    emitSelect(k);
    const fg = fgRef.current;
    if (fg && settledRef.current && node.x !== undefined && node.y !== undefined) {
      fg.centerAt(node.x, node.y, 600);
      fg.zoom(Math.max(fg.zoom(), 2.2), 600);
      pendingFocus.current = null;
    } else {
      pendingFocus.current = k; // layout not finished yet; applied when it is
    }
    return true;
  }, [nodeIndex, emitSelect]);

  const clearSelection = useCallback(() => { setSelectedId(null); onNodeSelect?.(null); }, [onNodeSelect]);

  const exportPng = useCallback((): string | null => {
    const canvas = wrapRef.current?.querySelector('canvas');
    if (!canvas) return null;
    const out = document.createElement('canvas');
    out.width = canvas.width; out.height = canvas.height;
    const ctx = out.getContext('2d');
    if (!ctx) return null;
    ctx.fillStyle = '#0a0e1a';
    ctx.fillRect(0, 0, out.width, out.height);
    ctx.drawImage(canvas, 0, 0);
    return out.toDataURL('image/png');
  }, []);

  useEffect(() => {
    if (!focusNodeId) return;
    focusNode(focusNodeId);
  }, [focusNodeId, focusToken, focusNode]);

  // Layout finished: freeze every node so nothing moves or shakes afterwards.
  const onEngineStop = useCallback(() => {
    graphData.nodes.forEach((n) => { if (n.x !== undefined && n.y !== undefined) { n.fx = n.x; n.fy = n.y; } });
    if (settledRef.current) return;
    settledRef.current = true;
    if (pendingFocus.current) focusNode(pendingFocus.current);
    else fitView(300);
  }, [graphData, focusNode, fitView]);

  // Re-fit when the container changes size (sidebar, window, fullscreen) unless a node is focused.
  useEffect(() => {
    if (!settledRef.current || selectedId) return undefined;
    const t = setTimeout(() => fitView(200), 220);
    return () => clearTimeout(t);
  }, [size.w, size.h]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- fullscreen (native API with a CSS fallback) ----
  useEffect(() => {
    const h = () => setNativeFull(document.fullscreenElement === wrapRef.current);
    document.addEventListener('fullscreenchange', h);
    return () => document.removeEventListener('fullscreenchange', h);
  }, []);
  useEffect(() => {
    if (!cssFull) return undefined;
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') setCssFull(false); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [cssFull]);
  const toggleFullscreen = useCallback(async () => {
    const el = wrapRef.current;
    if (!el) return;
    if (document.fullscreenElement) { await document.exitFullscreen().catch(() => undefined); return; }
    if (cssFull) { setCssFull(false); return; }
    if (el.requestFullscreen) {
      try { await el.requestFullscreen(); return; } catch { /* use the CSS fallback */ }
    }
    setCssFull(true);
  }, [cssFull]);
  const isFull = nativeFull || cssFull;
  useEffect(() => { onFullscreenChange?.(isFull); }, [isFull]); // eslint-disable-line react-hooks/exhaustive-deps

  useImperativeHandle(ref, () => ({ focusNode, fitView: () => fitView(400), zoomBy, toggleFullscreen, exportPng, clearSelection }),
    [focusNode, fitView, zoomBy, toggleFullscreen, exportPng, clearSelection]);

  // ---- drawing ----
  const isDim = useCallback((id: string) => {
    if (hasPath) return !pathNodes.has(id);
    return selectedId !== null && id !== selectedId && !adjacency.get(selectedId)?.has(id);
  }, [hasPath, pathNodes, selectedId, adjacency]);
  const isIncident = useCallback((l: GLink) => selectedId !== null && (linkEndId(l.source) === selectedId || linkEndId(l.target) === selectedId), [selectedId]);

  const drawNode = useCallback((node: any, ctx: CanvasRenderingContext2D) => {
    const roles = roleMap.get(node.id);
    ctx.save();
    ctx.globalAlpha = isDim(node.id) ? 0.28 : 1;
    let ring = NODE_R + 3;
    ROLE_ORDER.forEach((k) => {
      if (!roles?.has(k)) return;
      ctx.beginPath();
      ctx.arc(node.x, node.y, ring, 0, 2 * Math.PI);
      ctx.lineWidth = 3;
      ctx.strokeStyle = ROLE_META[k].color;
      if (k === 'topLead') { ctx.shadowColor = ROLE_META[k].color; ctx.shadowBlur = 14; }
      ctx.stroke();
      ctx.shadowBlur = 0;
      ring += 4;
    });
    if (pathNodes.has(node.id)) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, ring, 0, 2 * Math.PI);
      ctx.lineWidth = 3.5;
      ctx.strokeStyle = PATH_COLOR;
      ctx.stroke();
      ring += 4;
    }
    ctx.beginPath();
    ctx.arc(node.x, node.y, NODE_R, 0, 2 * Math.PI);
    ctx.fillStyle = '#0b1b33';
    ctx.fill();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = node.id === selectedId ? '#67e8f9' : 'rgba(34,211,238,0.5)';
    ctx.stroke();
    if (node.id === selectedId) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, ring, 0, 2 * Math.PI);
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#67e8f9';
      ctx.shadowColor = '#22d3ee';
      ctx.shadowBlur = 12;
      ctx.stroke();
    }
    ctx.shadowBlur = 0;
    ctx.font = `${Math.round(NODE_R * 1.25)}px ${EMOJI_FONT}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(node.emoji, node.x, node.y + 1);
    ctx.restore();
  }, [roleMap, isDim, selectedId, pathNodes]);

  const paintPointer = useCallback((node: any, color: string, ctx: CanvasRenderingContext2D) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x, node.y, NODE_R + 6, 0, 2 * Math.PI);
    ctx.fill();
  }, []);

  const linkColor = useCallback((l: any) => {
    if (hasPath) return pathEdges.has(l.id) ? PATH_COLOR : withAlpha(LEVEL_COLOR[l.level as keyof typeof LEVEL_COLOR], 0.18);
    return withAlpha(LEVEL_COLOR[l.level as keyof typeof LEVEL_COLOR], selectedId && !isIncident(l) ? 0.22 : 0.95);
  }, [hasPath, pathEdges, selectedId, isIncident]);
  const linkWidth = useCallback((l: any) => (l.level === 'high' ? 3.2 : 2.4) + (isIncident(l) || pathEdges.has(l.id) ? 1.2 : 0), [isIncident, pathEdges]);

  const onNodeClick = useCallback((node: any) => {
    const next = selectedId === node.id ? null : (node.id as string);
    setSelectedId(next);
    emitSelect(next);
  }, [selectedId, emitSelect]);

  // ---- legend (only what exists in the data) ----
  const legend = useMemo(() => {
    const kinds = new Map<string, string>();
    graphData.nodes.forEach((n) => { if (!kinds.has(n.kind)) kinds.set(n.kind, n.emoji); });
    const roles = new Set<RoleKey>();
    roleMap.forEach((set, id) => { if (nodeIndex.has(id)) set.forEach((r) => roles.add(r)); });
    return {
      kinds: [...kinds.entries()],
      roles: ROLE_ORDER.filter((r) => roles.has(r)),
      inferred: graphData.links.some((l) => l.origin === 'inferred'),
      structured: graphData.links.some((l) => l.origin === 'structured'),
    };
  }, [graphData, roleMap, nodeIndex]);

  const errorText = error ? ((error as any)?.response?.data?.detail
    || (error as any)?.message || (typeof error === 'string' ? error : 'Something went wrong.')) : '';
  const hasNodes = graphData.nodes.length > 0;
  const cls = ['nx-graph', isFull && 'nx-graph--full', cssFull && 'nx-graph--css-full', className].filter(Boolean).join(' ');

  return (
    <div ref={wrapRef} className={cls}>
      <div className="nx-graph__canvas">
        {ready && (
          <ForceGraph2D
            ref={fgRef as any}
            width={size.w}
            height={size.h}
            graphData={graphData as any}
            backgroundColor="rgba(0,0,0,0)"
            nodeRelSize={1}
            nodeVal={NODE_R * NODE_R}
            nodeCanvasObjectMode={() => 'replace'}
            nodeCanvasObject={drawNode}
            nodePointerAreaPaint={paintPointer}
            nodeLabel={(n: any) => nodeTooltipHtml(n as GNode, roleMap.get(n.id))}
            linkLabel={(l: any) => linkTooltipHtml(l as GLink, nameOf)}
            linkColor={linkColor}
            linkWidth={linkWidth}
            linkLineDash={(l: any) => (l.origin === 'inferred' ? [7, 5] : null)}
            linkCurvature={(l: any) => l.curvature}
            linkDirectionalArrowLength={11}
            linkDirectionalArrowRelPos={1}
            linkDirectionalArrowColor={linkColor}
            linkHoverPrecision={6}
            enableNodeDrag={false}
            warmupTicks={300}
            cooldownTicks={0}
            d3VelocityDecay={0.4}
            autoPauseRedraw={false}
            onEngineStop={onEngineStop}
            onNodeClick={onNodeClick}
            onBackgroundClick={clearSelection}
            minZoom={0.15}
            maxZoom={8}
          />
        )}
      </div>

      {hasNodes && (
        <div className="nx-graph__legend">
          <div className="nx-legend-row">
            {legend.kinds.map(([kind, emoji]) => <span key={kind}>{emoji} {kind}</span>)}
          </div>
          {legend.roles.length > 0 && (
            <div className="nx-legend-row">
              {legend.roles.map((r) => <span key={r}><i className="nx-ring" style={{ borderColor: ROLE_META[r].color }} />{ROLE_META[r].label}</span>)}
            </div>
          )}
          <div className="nx-legend-row">
            {(['high', 'medium', 'low', 'unknown'] as const).map((k) => <span key={k}><i className="nx-line" style={{ background: LEVEL_COLOR[k] }} />{LEVEL_LABEL[k]}</span>)}
          </div>
          {(legend.inferred || legend.structured) && (
            <div className="nx-legend-row">
              {legend.structured && <span><i className="nx-line" style={{ background: '#cbd5e1' }} />Structured record (solid)</span>}
              {legend.inferred && <span><i className="nx-line nx-line--dash" />Inferred, unverified (dashed)</span>}
            </div>
          )}
          <p className="nx-legend-note">Links are leads for investigator review, not findings of guilt.</p>
        </div>
      )}

      {normalized.skipped > 0 && hasNodes && (
        <div className="nx-graph__notice">{normalized.skipped} relationship{normalized.skipped > 1 ? 's' : ''} not shown (missing endpoints).</div>
      )}

      {children}

      {loading && (
        <div className={`nx-graph__overlay ${hasNodes ? 'nx-graph__overlay--light' : ''}`} role="status" aria-live="polite">
          <span className="nx-spinner" aria-hidden="true" />Loading knowledge graph…
        </div>
      )}

      {!loading && !!error && (
        <div className={hasNodes ? 'nx-graph__banner' : 'nx-graph__overlay'} role="alert">
          <div className="nx-graph__msg">
            <strong>Could not load the knowledge graph</strong>
            <span>{String(errorText)}</span>
            {onRetry && <button type="button" onClick={onRetry}>Try again</button>}
          </div>
        </div>
      )}

      {!loading && !error && !hasNodes && !hideEmptyState && (
        <div className="nx-graph__overlay" role="status">
          <div className="nx-graph__msg"><strong>No entities to show yet</strong><span>The API returned an empty graph.</span></div>
        </div>
      )}
    </div>
  );
});

export default NetraXGraph;
