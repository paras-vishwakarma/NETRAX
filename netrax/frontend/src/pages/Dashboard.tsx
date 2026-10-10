import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  FileText, Search, Shield,
  FolderOpen, ArrowRight, Loader2, GitMerge, Users,
  Network, ChevronRight,
  Database, Zap
} from 'lucide-react';
import { getPhase2DashboardStats, getRecentDocuments } from '../services/api';
import { formatDate, formatFileSize, getProcessingStatusColor } from '../utils';
import { PROCESSING_STATUSES } from '../types';
import logoImg from '../assets/logo.png';

export default function Dashboard() {
  const navigate = useNavigate();

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['phase2-dashboard-stats'],
    queryFn: getPhase2DashboardStats,
    refetchInterval: 5000,
  });

  const { data: recentDocs, isLoading: docsLoading } = useQuery({
    queryKey: ['recent-documents'],
    queryFn: getRecentDocuments,
    refetchInterval: 5000,
  });

  const unifiedMetrics = [
    {
      label: 'Active Cases',
      value: stats?.total_cases ?? 0,
      icon: FolderOpen,
      accent: '#00D2FF',
      desc: 'Active case investigations',
      onClick: () => navigate('/cases'),
    },
    {
      label: 'Ingested Documents',
      value: stats?.total_documents ?? 0,
      icon: FileText,
      accent: '#38BDF8',
      desc: 'FIRs, CDRs, and reports',
      onClick: () => navigate('/documents'),
    },
    {
      label: 'Extracted Entities',
      value: stats?.total_entities ?? 0,
      icon: Search,
      accent: '#0EA5E9',
      desc: 'Persons, phones, locations',
      onClick: () => navigate('/review'),
    },
    {
      label: 'Verified Entities',
      value: stats?.verified_entities ?? 0,
      icon: Shield,
      accent: '#10B981',
      desc: 'Analyst-confirmed entities',
      onClick: () => navigate('/review'),
    },
    {
      label: 'Canonical Profiles',
      value: stats?.canonical_entities ?? 0,
      icon: Users,
      accent: '#38BDF8',
      desc: 'Deduplicated master entities',
      onClick: () => navigate('/canonical'),
    },
    {
      label: 'Graph Link Nodes',
      value: stats?.graph_nodes ?? 0,
      icon: Network,
      accent: '#A855F7',
      desc: 'Nodes in knowledge network',
      onClick: () => navigate('/graph'),
    },
  ];

  const pipelineStages = [
    {
      step: '01',
      title: 'Evidence Ingestion',
      desc: 'Upload FIRs, CDRs, Financial CSVs, Surveillance PDFs',
      icon: FileText,
      to: '/upload',
      btnText: 'Ingest File',
    },
    {
      step: '02',
      title: 'Entity Extraction & Verification',
      desc: 'Automatic regex/NER extraction and analyst review',
      icon: Shield,
      to: '/review',
      btnText: 'Verify Entities',
    },
    {
      step: '03',
      title: 'Entity Resolution & Merge',
      desc: 'Cross-document fuzzy matching & canonical clustering',
      icon: GitMerge,
      to: '/resolution',
      btnText: 'Resolve Matches',
    },
    {
      step: '04',
      title: 'Knowledge Graph Analysis',
      desc: 'Interactive Cytoscape link graph and multi-hop paths',
      icon: Network,
      to: '/graph',
      btnText: 'Open Graph',
    },
  ];

  return (
    <div className="space-y-8 animate-fade-in max-w-7xl mx-auto">
      {/* Unified Command Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#0E1624] p-6 rounded-2xl border border-[#162638] shadow-md">
        <div className="flex items-center gap-4">
          <div className="shrink-0 p-1 bg-[#0C2433] rounded-xl border-2 border-[#00D2FF]/40 shadow-md overflow-hidden flex items-center justify-center">
            <img
              src={logoImg}
              alt="NETRA-X Logo"
              className="h-11 w-14 object-contain rounded-lg"
            />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-white tracking-tight">
                Unified Intelligence Operations Center
              </h1>
              <span className="px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-md bg-[#0C2433] text-[#38BDF8] border border-[#00D2FF]/30">
                Live Pipeline
              </span>
            </div>
            <p className="text-slate-400 mt-1 text-sm">
              End-to-End Criminal Link Analysis & Multi-Source Intelligence System
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/upload')}
            className="btn-secondary flex items-center gap-2 text-xs"
          >
            <FileText className="w-4 h-4 text-[#38BDF8]" />
            Upload Evidence
          </button>
          <button
            onClick={() => navigate('/graph')}
            className="btn-primary flex items-center gap-2 text-xs"
          >
            <Network className="w-4 h-4" />
            Knowledge Graph
          </button>
        </div>
      </div>

      {/* Unified Key Intelligence Metrics */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5 text-[#38BDF8]" />
            Unified System Metrics
          </h2>
          <span className="text-[11px] text-slate-400 font-mono">
            Auto-refresh 5s
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          {unifiedMetrics.map((card) => (
            <div
              key={card.label}
              className="stat-card cursor-pointer p-4"
              style={{ '--accent': card.accent } as React.CSSProperties}
              onClick={card.onClick}
            >
              <div className="flex items-start justify-between gap-2 min-w-0">
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider truncate" title={card.label}>
                    {card.label}
                  </p>
                  <p className="text-2xl font-bold text-white mt-1 font-mono">
                    {statsLoading ? (
                      <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
                    ) : (
                      card.value.toLocaleString()
                    )}
                  </p>
                  <p className="text-[10px] text-slate-400 mt-1 truncate" title={card.desc}>
                    {card.desc}
                  </p>
                </div>
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border mt-0.5"
                  style={{
                    background: `${card.accent}15`,
                    borderColor: `${card.accent}35`,
                  }}
                >
                  <card.icon className="w-4 h-4" style={{ color: card.accent }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* End-to-End Investigation Pipeline Workflow */}
      <div className="bg-[#0E1624] p-6 rounded-2xl border border-[#162638] shadow-md">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-[#00D2FF]" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              End-to-End Investigation Pipeline
            </h2>
          </div>
          <span className="text-xs text-slate-400 font-medium">
            Sequential Intelligence Workflow
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {pipelineStages.map((stage) => (
            <div
              key={stage.step}
              onClick={() => navigate(stage.to)}
              className="p-4 rounded-xl border border-[#162638] bg-[#0A101C] hover:bg-[#121E30] hover:border-[#00D2FF]/50 transition-all cursor-pointer group flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono font-bold text-[#38BDF8] px-1.5 py-0.5 rounded bg-[#0C2433] border border-[#00D2FF]/30">
                    STAGE {stage.step}
                  </span>
                  <stage.icon className="w-4 h-4 text-slate-400 group-hover:text-[#00D2FF] transition-colors" />
                </div>
                <h3 className="text-sm font-bold text-white mb-1">
                  {stage.title}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {stage.desc}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-[#162638] flex items-center justify-between text-xs font-semibold text-[#38BDF8]">
                <span>{stage.btnText}</span>
                <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Dual Section: Pending Resolution Queue & Recent Ingested Evidence */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quick Resolution & Canonical Intelligence Panel */}
        <div className="glass-card p-6 border border-[#162638] lg:col-span-1 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <GitMerge className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-bold text-white">
                  Resolution & Link Summary
                </h3>
              </div>
              <span className="px-2 py-0.5 rounded bg-amber-950/60 text-amber-300 border border-amber-800/40 text-[10px] font-bold">
                {stats?.potential_matches ?? 0} Pending
              </span>
            </div>

            <p className="text-xs text-slate-400 mb-4">
              Cross-document entity matching identifies alias suspects, matching phone numbers, and common bank accounts across distinct FIRs and CDR records.
            </p>

            <div className="space-y-2.5">
              <div className="p-3 rounded-xl bg-[#0A101C] border border-[#162638] flex items-center justify-between text-xs">
                <span className="text-slate-400 font-medium">Canonical Profiles:</span>
                <span className="font-mono font-bold text-white">
                  {stats?.canonical_entities ?? 0}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-[#0A101C] border border-[#162638] flex items-center justify-between text-xs">
                <span className="text-slate-400 font-medium">Verified Link Pairs:</span>
                <span className="font-mono font-bold text-emerald-400">
                  {stats?.verified_relationships ?? 0}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-[#0A101C] border border-[#162638] flex items-center justify-between text-xs">
                <span className="text-slate-400 font-medium">Knowledge Graph Nodes:</span>
                <span className="font-mono font-bold text-cyan-400">
                  {stats?.graph_nodes ?? 0}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-5 pt-4 border-t border-[#162638] flex gap-2">
            <button
              onClick={() => navigate('/resolution')}
              className="btn-secondary w-full justify-center text-xs"
            >
              <GitMerge className="w-3.5 h-3.5 text-amber-400" />
              Review Candidates
            </button>
            <button
              onClick={() => navigate('/graph')}
              className="btn-primary w-full justify-center text-xs"
            >
              <Network className="w-3.5 h-3.5" />
              Analyze Graph
            </button>
          </div>
        </div>

        {/* Recent Ingested Documents Table */}
        <div className="glass-card p-6 border border-[#162638] lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-[#38BDF8]" />
              <h3 className="text-sm font-bold text-white">
                Recent Ingested Evidence
              </h3>
            </div>
            <button
              onClick={() => navigate('/documents')}
              className="text-xs font-semibold text-[#38BDF8] hover:text-[#00D2FF] flex items-center gap-1"
            >
              View all archive <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          {docsLoading ? (
            <div className="flex items-center justify-center p-8 text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin mr-2 text-[#38BDF8]" />
              Loading documents...
            </div>
          ) : recentDocs && recentDocs.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-slate-400 uppercase border-b border-[#162638] bg-[#090F1B]">
                  <tr>
                    <th className="py-2.5 px-3 font-semibold">Evidence File</th>
                    <th className="py-2.5 px-3 font-semibold">Type</th>
                    <th className="py-2.5 px-3 font-semibold">Status</th>
                    <th className="py-2.5 px-3 font-semibold">Size</th>
                    <th className="py-2.5 px-3 font-semibold">Uploaded</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#162638]">
                  {recentDocs.slice(0, 5).map((doc) => {
                    const statusInfo = PROCESSING_STATUSES[doc.processing_status as keyof typeof PROCESSING_STATUSES];
                    return (
                      <tr key={doc.id} className="hover:bg-[#121E30] transition-colors">
                        <td className="py-2.5 px-3 font-semibold text-white max-w-[180px] truncate">
                          {doc.original_filename}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className="px-2 py-0.5 rounded bg-[#0A101C] text-slate-300 font-medium border border-[#162638]">
                            {doc.document_type}
                          </span>
                        </td>
                        <td className="py-2.5 px-3">
                          <span className={`px-2 py-0.5 rounded font-medium ${getProcessingStatusColor(doc.processing_status)}`}>
                            {statusInfo?.icon} {statusInfo?.label || doc.processing_status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-slate-400">{formatFileSize(doc.file_size)}</td>
                        <td className="py-2.5 px-3 text-slate-400">{formatDate(doc.created_at)}</td>
                        <td className="py-2.5 px-3 text-right">
                          <button
                            onClick={() => navigate(`/documents/${doc.id}`)}
                            className="text-[#38BDF8] hover:text-[#00D2FF] font-semibold"
                          >
                            Inspect
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8 text-slate-400 text-xs">
              No evidence documents uploaded yet. Click Upload Evidence to begin.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
