'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import { useAuth } from '@/context/auth-context';
import { ProcessInstance, ApprovalRequest, DocumentMetadata } from '@/types/api';
import { 
  Activity, 
  CheckCircle, 
  Clock, 
  FileText, 
  AlertTriangle, 
  ArrowUpRight,
  TrendingUp,
  ShieldCheck
} from 'lucide-react';

export default function DashboardPage() {
  const { user } = useAuth();
  const [processes, setProcesses] = useState<ProcessInstance[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadDashboardData() {
      try {
        const [procList, apprList, docList] = await Promise.allSettled([
          api.listProcesses(),
          api.listApprovals(),
          api.listDocuments(),
        ]);

        if (procList.status === 'fulfilled') setProcesses(procList.value || []);
        if (apprList.status === 'fulfilled') setApprovals(apprList.value || []);
        if (docList.status === 'fulfilled') setDocuments(docList.value || []);
      } catch (err) {
        console.warn('Dashboard fetch error', err);
      } finally {
        setLoading(false);
      }
    }
    loadDashboardData();
  }, []);

  const pendingApprovalsCount = approvals.filter(a => a.status === 'PENDING').length;

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Welcome Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
            Welcome back, {user ? user.username : 'Analyst'}!
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Enterprise Agentic Orchestrator and Decision Governance System.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/processes"
            className="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white text-sm font-semibold rounded-lg shadow-sm transition-colors"
          >
            Explore Processes
          </Link>
          <Link
            href="/approvals"
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-semibold rounded-lg border border-slate-200 transition-colors"
          >
            Review Approvals
          </Link>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Active Processes</p>
            <p className="text-2xl font-extrabold text-slate-900 mt-1">{processes.length}</p>
            <span className="text-xs text-emerald-600 flex items-center gap-1 mt-1 font-medium">
              <TrendingUp className="w-3.5 h-3.5" /> Synchronized
            </span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-sky-50 text-sky-600 flex items-center justify-center">
            <Activity className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Pending Approvals</p>
            <p className="text-2xl font-extrabold text-amber-600 mt-1">{pendingApprovalsCount}</p>
            <span className="text-xs text-amber-600 flex items-center gap-1 mt-1 font-medium">
              <Clock className="w-3.5 h-3.5" /> Action required
            </span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
            <AlertTriangle className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Indexed Documents</p>
            <p className="text-2xl font-extrabold text-slate-900 mt-1">{documents.length}</p>
            <span className="text-xs text-sky-600 flex items-center gap-1 mt-1 font-medium">
              <FileText className="w-3.5 h-3.5" /> Vector + Hybrid
            </span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <FileText className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Guardrails & Security</p>
            <p className="text-2xl font-extrabold text-emerald-600 mt-1">100%</p>
            <span className="text-xs text-emerald-600 flex items-center gap-1 mt-1 font-medium">
              <ShieldCheck className="w-3.5 h-3.5" /> Active scrubbers
            </span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <ShieldCheck className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Two Column Section: Recent Processes and Pending Actions */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Processes */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100 flex items-center justify-between">
            <h3 className="font-bold text-slate-900 text-base">Recent Enterprise Workflows</h3>
            <Link href="/processes" className="text-xs font-semibold text-sky-600 hover:text-sky-700 flex items-center gap-1">
              View all <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <div className="divide-y divide-slate-100">
            {processes.length === 0 ? (
              <p className="p-6 text-sm text-slate-400 text-center">No active process records found.</p>
            ) : (
              processes.slice(0, 5).map((proc) => (
                <div key={proc.id} className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
                  <div>
                    <p className="text-sm font-semibold text-slate-800">{proc.title || `Process #${proc.id.substring(0, 8)}`}</p>
                    <p className="text-xs text-slate-400 mt-0.5">ID: {proc.id}</p>
                  </div>
                  <span className={`px-2.5 py-1 rounded text-xs font-semibold uppercase tracking-wider ${
                    proc.status === 'COMPLETED' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                    proc.status === 'AWAITING_APPROVAL' ? 'bg-amber-50 text-amber-700 border border-amber-200' :
                    'bg-slate-100 text-slate-700 border border-slate-200'
                  }`}>
                    {proc.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Pending Approvals */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100 flex items-center justify-between">
            <h3 className="font-bold text-slate-900 text-base">Pending Human Escalations</h3>
            <Link href="/approvals" className="text-xs font-semibold text-sky-600 hover:text-sky-700 flex items-center gap-1">
              Review queue <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <div className="divide-y divide-slate-100">
            {approvals.length === 0 ? (
              <p className="p-6 text-sm text-slate-400 text-center">No pending approval requests in queue.</p>
            ) : (
              approvals.slice(0, 5).map((appr) => (
                <div key={appr.id} className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      Dispute Amount: <span className="text-sky-600 font-bold">${appr.amount?.toLocaleString() || 'N/A'}</span>
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5">Tier: {appr.escalation_tier || 'TIER_1_ANALYST'}</p>
                  </div>
                  <span className={`px-2.5 py-1 rounded text-xs font-semibold uppercase tracking-wider ${
                    appr.status === 'APPROVED' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                    appr.status === 'REJECTED' ? 'bg-rose-50 text-rose-700 border border-rose-200' :
                    'bg-amber-50 text-amber-700 border border-amber-200'
                  }`}>
                    {appr.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
