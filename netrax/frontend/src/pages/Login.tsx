import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Shield, Lock, User, Eye, EyeOff, Key,
  CheckCircle2, AlertTriangle, ArrowRight,
  Fingerprint, Sparkles, Terminal
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('demo123');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as any)?.from?.pathname || '/dashboard';

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        'Authentication failed. Please verify credentials (admin / demo123).';
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickDemoLogin = async () => {
    setUsername('admin');
    setPassword('demo123');
    setError(null);
    setIsSubmitting(true);

    try {
      await login('admin', 'demo123');
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Quick demo login failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-[#0B0F17] relative overflow-hidden px-4 py-8 select-none">
      {/* Dynamic Cyan & Obsidian Glows */}
      <div className="absolute -top-32 -left-32 w-96 h-96 bg-[#00D2FF]/15 rounded-full blur-[100px] pointer-events-none" />
      <div className="absolute -bottom-32 -right-32 w-96 h-96 bg-[#0EA5E9]/20 rounded-full blur-[100px] pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] h-[550px] bg-[#38BDF8]/10 rounded-full blur-[140px] pointer-events-none" />

      {/* Cyber Grid Pattern */}
      <div
        className="absolute inset-0 opacity-[0.05] pointer-events-none"
        style={{
          backgroundImage: `linear-gradient(to right, #00D2FF 1px, transparent 1px), linear-gradient(to bottom, #00D2FF 1px, transparent 1px)`,
          backgroundSize: '28px 28px',
        }}
      />

      {/* Main Login Card */}
      <div className="w-full max-w-md relative z-10">
        <div className="relative bg-[#0E1624] border border-[#162638] rounded-2xl p-8 shadow-2xl shadow-black/80 overflow-hidden">
          {/* Top Cyan Accent Line */}
          <div className="absolute top-0 left-0 right-0 h-[3px] bg-gradient-to-r from-[#00D2FF] via-[#38BDF8] to-[#0EA5E9]" />

          {/* Header & Logo */}
          <div className="text-center mb-7">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[#0C2433] p-3 shadow-lg shadow-[#00D2FF]/20 mb-3 border border-[#00D2FF]/40">
              <Shield className="w-8 h-8 text-[#00D2FF]" />
            </div>

            <div className="flex items-center justify-center gap-2 mb-1">
              <h1 className="text-2xl font-extrabold text-white tracking-tight">
                NETRA<span className="text-[#00D2FF]">-X</span>
              </h1>
              <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-md bg-[#0C2433] text-[#38BDF8] border border-[#00D2FF]/40">
                PORTAL
              </span>
            </div>
            <p className="text-xs text-slate-400 font-medium">
              Multi-Source Intelligence & Criminal Link Analysis System
            </p>
          </div>

          {/* Demo Admin Card & 1-Click Action */}
          <div className="mb-6 p-4 rounded-xl bg-[#0A101C] border border-[#162638]">
            <div className="flex items-start justify-between gap-3 mb-2.5">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#00D2FF]" />
                <span className="text-xs font-semibold text-slate-200">
                  Single Demo Admin Account
                </span>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono font-medium">
                Active
              </span>
            </div>

            <div className="text-[11px] text-slate-300 space-y-1 mb-3 bg-[#070A10] p-2.5 rounded-lg border border-[#141E2D] font-mono">
              <div className="flex justify-between">
                <span className="text-slate-400">Admin ID:</span>
                <span className="text-[#38BDF8] font-bold">admin</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Password:</span>
                <span className="text-white font-bold">demo123</span>
              </div>
              <div className="flex justify-between pt-1 border-t border-[#141E2D]">
                <span className="text-slate-400">Role:</span>
                <span className="text-slate-200">Superintendent</span>
              </div>
            </div>

            <button
              type="button"
              onClick={handleQuickDemoLogin}
              disabled={isSubmitting}
              className="btn-primary w-full justify-between"
            >
              <Fingerprint className="w-4 h-4" />
              <span>1-Click Demo Login</span>
              <ArrowRight className="w-3.5 h-3.5 ml-auto" />
            </button>
          </div>

          {/* Divider */}
          <div className="relative my-5 text-center">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[#162638]" />
            </div>
            <span className="relative px-3 bg-[#0E1624] text-[11px] text-slate-400 font-medium uppercase tracking-wider">
              Or Manual Sign-In
            </span>
          </div>

          {/* Error Alert */}
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-950/40 border border-red-500/40 flex items-start gap-2.5 text-xs text-red-300">
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Manual Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Username */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Admin Username / Badge ID
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <User className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="admin"
                  className="nx-input pl-10"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="nx-input pl-10 pr-10 font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-200 transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary w-full justify-center mt-2"
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-slate-900/30 border-t-slate-900 rounded-full animate-spin" />
                  <span>Verifying Clearance...</span>
                </>
              ) : (
                <>
                  <Key className="w-4 h-4" />
                  <span>Authorize & Enter System</span>
                </>
              )}
            </button>
          </form>

          {/* Security Footer */}
          <div className="mt-6 pt-4 border-t border-[#162638] flex items-center justify-between text-[11px] text-slate-400">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>TLS 256-Bit Guard</span>
            </div>
            <div className="flex items-center gap-1 font-mono text-[10px] text-slate-400">
              <Terminal className="w-3 h-3 text-[#38BDF8]" />
              <span>ID: NX-ADMIN-001</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
