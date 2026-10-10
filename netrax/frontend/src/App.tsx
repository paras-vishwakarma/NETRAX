import { BrowserRouter, Routes, Route, NavLink, Navigate, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  LayoutDashboard, Upload, FileText, Shield,
  FolderOpen, Activity, GitMerge, Users,
  Share2, Network, LogOut, UserCheck
} from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Cases from './pages/Cases';
import DocumentUpload from './pages/DocumentUpload';
import Documents from './pages/Documents';
import DocumentDetail from './pages/DocumentDetail';
import EntityReview from './pages/EntityReview';
import EntityResolution from './pages/EntityResolution';
import CanonicalEntities from './pages/CanonicalEntities';
import Relationships from './pages/Relationships';
import KnowledgeGraph from './pages/KnowledgeGraph';
import logoImg from './assets/logo.png';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 10000,
    },
  },
});

function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navSections = [
    {
      title: 'Investigation Workspace',
      links: [
        { to: '/dashboard', icon: LayoutDashboard, label: 'Operations Center' },
        { to: '/cases', icon: FolderOpen, label: 'Investigation Cases' },
      ],
    },
    {
      title: 'Evidence & Ingestion',
      links: [
        { to: '/upload', icon: Upload, label: 'Ingest Evidence' },
        { to: '/documents', icon: FileText, label: 'Document Archive' },
        { to: '/review', icon: Shield, label: 'Entity Verification' },
      ],
    },
    {
      title: 'Intelligence & Graph Network',
      links: [
        { to: '/resolution', icon: GitMerge, label: 'Entity Resolution' },
        { to: '/canonical', icon: Users, label: 'Canonical Profiles' },
        { to: '/relationships', icon: Share2, label: 'Extracted Links' },
        { to: '/graph', icon: Network, label: 'Knowledge Graph' },
      ],
    },
  ];

  return (
    <aside className="sidebar w-64 h-screen shrink-0 sticky top-0 flex flex-col z-30 select-none overflow-y-auto bg-[#070A10] border-r border-[#141E2D]">
      {/* Unified Branding Header */}
      <div className="p-5 border-b border-[#141E2D]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#0C2433] p-0.5 flex items-center justify-center shadow-md border-2 border-[#00D2FF]/40 overflow-hidden shrink-0">
            <img
              src={logoImg}
              alt="NETRA-X Logo"
              className="w-full h-full object-contain rounded-md"
            />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h1 className="text-lg font-bold text-white tracking-tight">
                NETRA<span className="text-[#00D2FF]">-X</span>
              </h1>
              <span className="px-1.5 py-0.2 text-[9px] font-bold rounded bg-[#0C2433] text-[#38BDF8] border border-[#00D2FF]/30 uppercase">
                INTEL
              </span>
            </div>
            <p className="text-[10px] text-[#64748B] font-medium tracking-wider uppercase">
              SURVEILLANCE CORE
            </p>
          </div>
        </div>
      </div>

      {/* Admin User Profile */}
      <div className="px-3.5 pt-3.5 pb-2">
        <div className="p-2.5 rounded-xl bg-[#0D1624] border border-[#162638] flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-[#0C2433] border border-[#00D2FF]/30 flex items-center justify-center shrink-0">
              <UserCheck className="w-4 h-4 text-[#38BDF8]" />
            </div>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-slate-100 truncate">
                {user?.name || 'Officer Sharma'}
              </div>
              <div className="text-[10px] text-slate-400 font-mono tracking-wide truncate">
                {user?.badge || 'Badge #7492 · Sector 12'}
              </div>
            </div>
          </div>
          <button
            onClick={handleLogout}
            title="Sign out of demo admin session"
            className="p-1.5 rounded-lg text-slate-400 hover:text-cyan-400 hover:bg-cyan-500/10 transition-colors shrink-0"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Unified Navigation Structure */}
      <nav className="flex-1 p-3.5 space-y-5">
        {navSections.map((section) => (
          <div key={section.title}>
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-3 mb-1.5">
              {section.title}
            </div>
            <div className="space-y-1">
              {section.links.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    `sidebar-link ${isActive ? 'active' : ''}`
                  }
                >
                  <Icon className="w-[18px] h-[18px]" />
                  {label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Pipeline Status Footer */}
      <div className="p-3.5 border-t border-[#141E2D]">
        <div className="text-[11px] text-slate-400 space-y-1">
          <div className="flex items-center gap-1.5">
            <Activity className="w-3 h-3 text-emerald-400" />
            <span className="text-slate-200 font-medium">Unified Pipeline Online</span>
          </div>
          <p className="text-[10px] text-slate-500">
            Ingestion · NER · Resolution · Graph
          </p>
        </div>
      </div>
    </aside>
  );
}

function MainLayout() {
  return (
    <div className="flex min-h-screen w-full bg-[#0B0F17] text-[#F8FAFC]">
      <Sidebar />
      <main className="flex-1 min-w-0 p-8">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/cases" element={<Cases />} />
          <Route path="/upload" element={<DocumentUpload />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/documents/:id" element={<DocumentDetail />} />
          <Route path="/review" element={<EntityReview />} />
          <Route path="/review/:documentId" element={<EntityReview />} />
          <Route path="/resolution" element={<EntityResolution />} />
          <Route path="/canonical" element={<CanonicalEntities />} />
          <Route path="/relationships" element={<Relationships />} />
          <Route path="/graph" element={<KnowledgeGraph />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <MainLayout />
                </ProtectedRoute>
              }
            />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
