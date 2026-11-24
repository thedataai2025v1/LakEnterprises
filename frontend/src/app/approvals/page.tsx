'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api-client';
import { useAuth } from '@/context/auth-context';
import { ApprovalRequest } from '@/types/api';
import { CheckCircle2, XCircle, AlertCircle, RefreshCw, Clock, DollarSign } from 'lucide-react';

export default function ApprovalsPage() {
  const { hasRole } = useAuth();
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<string | null>(null);

  const fetchApprovals = async () => {
    setLoading(true);
    try {
      const data = await api.listApprovals();
      setApprovals(data || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
  }, []);

  const handleDecision = async (id: string, decision: 'APPROVED' | 'REJECTED') => {
    setActingId(id);
    try {
      await api.decideApproval(id, decision, `Console operator decision: ${decision}`);
      await fetchApprovals();
    } catch (err: any) {
      alert(`Action failed: ${err?.message || 'Unknown error'}`);
    } finally {
      setActingId(null);
    }
  };

  const canDecide = hasRole(['analyst', 'admin']);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Human Approval Queue</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Deterministic governance gates: review, approve, or reject high-risk agent resolutions.
          </p>
        </div>
        <button
          onClick={() => fetchApprovals()}
          className="flex items-center gap-1.5 px-3.5 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 shadow-sm transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Queue
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {approvals.length === 0 ? (
          <div className="col-span-full bg-white p-8 rounded-xl border border-slate-200 text-center text-slate-400">
            No approval requests found in queue.
          </div>
        ) : (
          approvals.map((req) => (
            <div key={req.id} className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-mono text-slate-400">ID: {req.id.substring(0, 8)}...</span>
                  <span className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider ${
                    req.status === 'APPROVED' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                    req.status === 'REJECTED' ? 'bg-rose-50 text-rose-700 border border-rose-200' :
                    'bg-amber-50 text-amber-700 border border-amber-200'
                  }`}>
                    {req.status}
                  </span>
                </div>

                <div className="my-2">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Dispute Exposure</p>
                  <p className="text-2xl font-extrabold text-slate-900 flex items-center gap-1 mt-0.5">
                    <DollarSign className="w-5 h-5 text-sky-600" />
                    {req.amount?.toLocaleString() || '0'}
                  </p>
                </div>

                <div className="space-y-1.5 my-3 text-xs text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-100">
                  <p><strong className="text-slate-800">Tier:</strong> {req.escalation_tier || 'TIER_1_ANALYST'}</p>
                  <p><strong className="text-slate-800">Urgency:</strong> {req.urgency || 'HIGH'}</p>
                  {req.reason && <p><strong className="text-slate-800">Reason:</strong> {req.reason}</p>}
                </div>
              </div>

              {req.status === 'PENDING' && (
                <div className="pt-4 border-t border-slate-100 flex items-center gap-2">
                  <button
                    disabled={!canDecide || actingId === req.id}
                    onClick={() => handleDecision(req.id, 'APPROVED')}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition-colors disabled:opacity-50"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    Approve
                  </button>
                  <button
                    disabled={!canDecide || actingId === req.id}
                    onClick={() => handleDecision(req.id, 'REJECTED')}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-bold transition-colors disabled:opacity-50"
                  >
                    <XCircle className="w-4 h-4" />
                    Reject
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
