'use client';

import React, { useState } from 'react';
import { useAuth } from '@/context/auth-context';
import { 
  CheckCircle2, 
  XCircle, 
  ArrowUpRight, 
  ShieldAlert, 
  Clock, 
  AlertCircle 
} from 'lucide-react';

interface ProcessActionsProps {
  processId: string;
  isAwaitingApproval: boolean;
  riskLevel?: string;
  amount?: number;
  onDecision: (decision: 'APPROVED' | 'REJECTED' | 'ESCALATED', notes: string) => Promise<void>;
  className?: string;
}

export const ProcessActions: React.FC<ProcessActionsProps> = ({
  processId,
  isAwaitingApproval,
  riskLevel = 'HIGH',
  amount,
  onDecision,
  className = '',
}) => {
  const { user, hasRole } = useAuth();
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [activeModal, setActiveModal] = useState<'APPROVE' | 'REJECT' | 'ESCALATE' | null>(null);

  const canApprove = hasRole(['analyst', 'admin']);
  const canEscalate = hasRole(['analyst', 'admin']);

  const handleSubmit = async (decision: 'APPROVED' | 'REJECTED' | 'ESCALATED') => {
    setSubmitting(true);
    try {
      await onDecision(decision, notes);
      setActiveModal(null);
      setNotes('');
    } catch (err: any) {
      alert(`Decision submission failed: ${err?.message || 'Unknown error'}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={`bg-white rounded-xl border border-slate-200 p-6 shadow-sm ${className}`}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-100">
        <div>
          <h3 className="text-base font-bold text-slate-900">Governance & Approval Actions</h3>
          <p className="text-xs text-slate-500">
            Enforce human-in-the-loop policies before autonomous execution resumes.
          </p>
        </div>

        {isAwaitingApproval && (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-100 text-amber-800 border border-amber-300 animate-bounce">
            <AlertCircle className="w-3.5 h-3.5" />
            Decision Required
          </span>
        )}
      </div>

      {/* Exposure / Risk Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-5 p-3.5 bg-slate-50 rounded-lg border border-slate-100 text-xs">
        <div>
          <span className="text-slate-400 block mb-0.5">Dispute Exposure</span>
          <span className="font-extrabold text-slate-900 text-sm">
            ${amount ? amount.toLocaleString() : 'N/A'}
          </span>
        </div>
        <div>
          <span className="text-slate-400 block mb-0.5">Assessed Risk</span>
          <span className={`font-bold ${riskLevel === 'HIGH' ? 'text-rose-600' : 'text-emerald-600'}`}>
            {riskLevel}
          </span>
        </div>
        <div>
          <span className="text-slate-400 block mb-0.5">Reviewer Role</span>
          <span className="font-semibold text-slate-700 capitalize">
            {user?.role || 'Analyst'}
          </span>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          disabled={!isAwaitingApproval || !canApprove || submitting}
          onClick={() => setActiveModal('APPROVE')}
          className="flex-1 min-w-[130px] flex items-center justify-center gap-2 py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-bold shadow-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <CheckCircle2 className="w-4 h-4" />
          <span>Approve & Resume</span>
        </button>

        <button
          disabled={!isAwaitingApproval || !canApprove || submitting}
          onClick={() => setActiveModal('REJECT')}
          className="flex-1 min-w-[130px] flex items-center justify-center gap-2 py-2.5 px-4 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-sm font-bold shadow-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <XCircle className="w-4 h-4" />
          <span>Reject & Halt</span>
        </button>

        <button
          disabled={!isAwaitingApproval || !canEscalate || submitting}
          onClick={() => setActiveModal('ESCALATE')}
          className="flex-1 min-w-[130px] flex items-center justify-center gap-2 py-2.5 px-4 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-sm font-bold shadow-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ArrowUpRight className="w-4 h-4" />
          <span>Escalate to Senior</span>
        </button>
      </div>

      {!canApprove && (
        <p className="mt-3 text-xs text-rose-500 font-medium">
          * Read-only role (Viewer). Switch to Analyst or Admin to submit governance decisions.
        </p>
      )}

      {/* Decision Confirmation Modal */}
      {activeModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6 space-y-4">
            <h4 className="text-base font-bold text-slate-900 flex items-center gap-2">
              {activeModal === 'APPROVE' && <CheckCircle2 className="w-5 h-5 text-emerald-600" />}
              {activeModal === 'REJECT' && <XCircle className="w-5 h-5 text-rose-600" />}
              {activeModal === 'ESCALATE' && <ArrowUpRight className="w-5 h-5 text-amber-600" />}
              Confirm Decision: {activeModal}
            </h4>

            <p className="text-xs text-slate-500 leading-relaxed">
              {activeModal === 'APPROVE' &&
                'Approving this dispute will resume the workflow graph and automatically execute resolution tools (ERP disbursement or ticket update).'}
              {activeModal === 'REJECT' &&
                'Rejecting will abort autonomous tool execution and record this refusal in the permanent audit ledger.'}
              {activeModal === 'ESCALATE' &&
                'Escalating will transfer the approval request to the next seniority tier (Manager/Director/Executive) with an updated SLA deadline.'}
            </p>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Audit Justification Notes (Optional)
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add operational notes or regulatory reference for this decision..."
                rows={3}
                className="w-full p-2.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={() => handleSubmit(activeModal === 'APPROVE' ? 'APPROVED' : activeModal === 'REJECT' ? 'REJECTED' : 'ESCALATED')}
                className={`px-4 py-2 text-xs font-bold text-white rounded-lg shadow-sm transition-colors ${
                  activeModal === 'APPROVE'
                    ? 'bg-emerald-600 hover:bg-emerald-500'
                    : activeModal === 'REJECT'
                    ? 'bg-rose-600 hover:bg-rose-500'
                    : 'bg-amber-600 hover:bg-amber-500'
                }`}
              >
                {submitting ? 'Submitting...' : `Submit ${activeModal}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
