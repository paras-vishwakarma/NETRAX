import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FolderOpen, Plus, X, Loader2, FileText, ArrowRight, Trash2, AlertTriangle } from 'lucide-react';
import { listCases, createCase, deleteCase } from '../services/api';
import { useNavigate } from 'react-router-dom';
import type { Case } from '../types';

export default function Cases() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [caseToDelete, setCaseToDelete] = useState<Case | null>(null);
  const [form, setForm] = useState({ case_number: '', title: '', description: '' });

  const { data, isLoading } = useQuery({
    queryKey: ['cases'],
    queryFn: listCases,
  });

  const mutation = useMutation({
    mutationFn: createCase,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases'] });
      setShowCreate(false);
      setForm({ case_number: '', title: '', description: '' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (caseId: string) => deleteCase(caseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      setCaseToDelete(null);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.case_number || !form.title) return;
    mutation.mutate(form);
  };

  return (
    <div className="space-y-6 animate-fade-in max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#0E1624] p-6 rounded-2xl border border-[#162638] shadow-md">
        <div>
          <h1 className="text-2xl font-bold text-white">Investigation Cases</h1>
          <p className="text-slate-400 text-sm mt-1">
            Organize evidence, suspects, and knowledge graphs by investigation case
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>
          <Plus className="w-4 h-4" /> Create Case
        </button>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => setShowCreate(false)}
        >
          <div
            className="bg-[#0E1624] rounded-2xl p-6 w-full max-w-md shadow-2xl border border-[#162638] animate-slide-up"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-white">Create New Case</h2>
              <button
                onClick={() => setShowCreate(false)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                  Case Number
                </label>
                <input
                  className="nx-input"
                  placeholder="e.g., CASE-2026-001"
                  value={form.case_number}
                  onChange={(e) => setForm({ ...form, case_number: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                  Title
                </label>
                <input
                  className="nx-input"
                  placeholder="e.g., Operation Nightwatch Cyber Fraud"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                  Description
                </label>
                <textarea
                  className="nx-input min-h-[90px] resize-none"
                  placeholder="Case objectives, suspect summaries, and scope..."
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </div>
              {mutation.isError && (
                <p className="text-red-400 text-xs font-medium">
                  {(mutation.error as any)?.response?.data?.detail || 'Failed to create case'}
                </p>
              )}
              <div className="flex gap-3 pt-2">
                <button type="submit" className="btn-primary flex-1 justify-center" disabled={mutation.isPending}>
                  {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  Save Case
                </button>
                <button type="button" className="btn-secondary" onClick={() => setShowCreate(false)}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {caseToDelete && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => setCaseToDelete(null)}
        >
          <div
            className="bg-[#0E1624] rounded-2xl p-6 w-full max-w-md shadow-2xl border border-[#162638] animate-slide-up"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 text-red-400 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-950/60 border border-red-800/40 flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-white">Delete Investigation Case</h2>
                <p className="text-xs text-slate-400">This action cannot be undone.</p>
              </div>
            </div>

            <p className="text-sm text-slate-300 mb-6 leading-relaxed">
              Are you sure you want to delete case <span className="font-bold text-white">{caseToDelete.case_number} ({caseToDelete.title})</span>? All uploaded documents, extracted entities, and knowledge graph relationships associated with this case will be permanently deleted.
            </p>

            <div className="flex gap-3 justify-end">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setCaseToDelete(null)}
                disabled={deleteMutation.isPending}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-danger flex items-center gap-2"
                onClick={() => deleteMutation.mutate(caseToDelete.id)}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                Delete Case
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cases List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-[#38BDF8]" />
        </div>
      ) : data?.cases && data.cases.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {data.cases.map((c) => (
            <div
              key={c.id}
              className="glass-card p-5 cursor-pointer group hover:border-[#00D2FF]/50 flex flex-col justify-between relative"
              onClick={() => navigate(`/documents?case=${c.id}`)}
            >
              <div>
                <div className="flex items-start justify-between mb-3">
                  <div className="w-10 h-10 rounded-xl bg-[#0C2433] flex items-center justify-center group-hover:bg-[#0E3248] transition-colors border border-[#00D2FF]/30">
                    <FolderOpen className="w-5 h-5 text-[#38BDF8]" />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase tracking-wider font-bold px-2.5 py-0.5 rounded-full bg-emerald-950/60 text-emerald-400 border border-emerald-800/40">
                      {c.status}
                    </span>
                    <button
                      title="Delete Case"
                      className="p-1 text-slate-400 hover:text-red-400 hover:bg-red-950/40 rounded-lg transition-colors"
                      onClick={(e) => {
                        e.stopPropagation();
                        setCaseToDelete(c);
                      }}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div className="text-xs font-mono font-bold text-[#38BDF8] mb-0.5">
                  {c.case_number}
                </div>
                <h3 className="font-bold text-white text-base group-hover:text-[#00D2FF] transition-colors">
                  {c.title}
                </h3>
                {c.description && (
                  <p className="text-slate-400 text-xs mt-2 line-clamp-2 leading-relaxed">
                    {c.description}
                  </p>
                )}
              </div>

              <div className="flex items-center justify-between mt-5 pt-3 border-t border-[#162638]">
                <div className="flex items-center gap-1.5 text-xs text-slate-300 font-medium">
                  <FileText className="w-3.5 h-3.5 text-slate-400" />
                  {c.document_count} documents
                </div>
                <div className="flex items-center gap-1 text-xs font-semibold text-[#38BDF8] group-hover:translate-x-0.5 transition-transform">
                  <span>Explore</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-20 bg-[#0E1624] rounded-2xl border border-[#162638] p-8">
          <FolderOpen className="w-12 h-12 mx-auto mb-4 text-slate-500" />
          <p className="text-lg font-bold text-white">No investigation cases found</p>
          <p className="text-sm text-slate-400 mt-1">Create your first case to start linking evidence and entities.</p>
          <button className="btn-primary mt-4 inline-flex items-center gap-2" onClick={() => setShowCreate(true)}>
            <Plus className="w-4 h-4" /> Create Case
          </button>
        </div>
      )}
    </div>
  );
}
