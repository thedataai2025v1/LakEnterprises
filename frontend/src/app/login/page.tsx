'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/auth-context';
import { UserRole } from '@/types/api';
import { Shield, CheckCircle2, ArrowRight } from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const { loginAsDemo, loading } = useAuth();
  const [selectedRole, setSelectedRole] = useState<UserRole>('analyst');
  const [error, setError] = useState<string | null>(null);

  const roles: Array<{ role: UserRole; title: string; description: string; permissions: string[] }> = [
    {
      role: 'viewer',
      title: 'Viewer Role',
      description: 'Read-only access to view process timelines, audit logs, and document search results.',
      permissions: ['View Processes', 'Search Documents', 'Inspect Audit Trail'],
    },
    {
      role: 'analyst',
      title: 'Analyst Role (Recommended)',
      description: 'Operational privileges to trigger workflows, run inquiries, and review standard cases.',
      permissions: ['Run Workflows', 'Analyze Documents', 'Tier 1 Escalations', 'Process Management'],
    },
    {
      role: 'admin',
      title: 'Administrator Role',
      description: 'Full supervisory rights: decide executive-level approvals, override guardrails, and access security settings.',
      permissions: ['Executive Approvals', 'SLA Overrides', 'System Diagnostics', 'Full RBAC Access'],
    },
  ];

  const handleLogin = async () => {
    try {
      setError(null);
      await loginAsDemo(selectedRole);
      router.push('/');
    } catch (err: any) {
      setError(err?.message || 'Login failed. Please ensure the backend is running.');
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-10 space-y-8">
      <div className="text-center space-y-3">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-sky-100 text-sky-600 mb-2">
          <Shield className="w-8 h-8" />
        </div>
        <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">
          LakEnterprises Console Access
        </h2>
        <p className="text-sm text-slate-500 max-w-md mx-auto">
          Authenticate using single sign-on or select a verified demo identity to inspect role-based access control (RBAC).
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-700 text-sm rounded-lg">
          {error}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {roles.map((r) => {
          const isSelected = selectedRole === r.role;
          return (
            <div
              key={r.role}
              onClick={() => setSelectedRole(r.role)}
              className={`cursor-pointer rounded-xl p-5 border-2 transition-all relative flex flex-col justify-between ${
                isSelected
                  ? 'border-sky-600 bg-sky-50/50 shadow-md ring-2 ring-sky-600/20'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="font-bold text-slate-900 capitalize text-base">{r.role}</span>
                  {isSelected && <CheckCircle2 className="w-5 h-5 text-sky-600" />}
                </div>
                <p className="text-xs text-slate-600 mb-4 leading-relaxed">{r.description}</p>
              </div>

              <div className="border-t border-slate-100 pt-3">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-2">
                  Capabilities
                </span>
                <ul className="space-y-1">
                  {r.permissions.map((p, idx) => (
                    <li key={idx} className="text-xs text-slate-700 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-sky-500" />
                      {p}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex justify-center pt-4">
        <button
          onClick={handleLogin}
          disabled={loading}
          className="flex items-center gap-2 px-8 py-3 bg-sky-600 hover:bg-sky-500 text-white font-semibold rounded-lg shadow-md transition-colors disabled:opacity-50"
        >
          <span>{loading ? 'Authenticating...' : `Enter Console as ${selectedRole.toUpperCase()}`}</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
