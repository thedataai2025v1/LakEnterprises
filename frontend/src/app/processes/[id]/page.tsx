'use client';

import React, { useEffect, useState, use } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api-client';
import { WorkflowState, WorkflowTraceEvent, WorkflowSLAMetrics } from '@/types/api';
import { ProcessTimeline } from '@/components/workflow/process-timeline';
import { WorkflowStepsPanel } from '@/components/workflow/workflow-steps-panel';
import { ProcessActions } from '@/components/workflow/process-actions';
import { ArrowLeft, RefreshCw, AlertTriangle, CheckCircle2, ShieldCheck, Activity } from 'lucide-react';
import Link from 'next/link';

export default function ProcessDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const resolvedParams = use(params);
  const processId = resolvedParams.id;

  const [state, setState] = useState<WorkflowState | null>(null);
  const [events, setEvents] = useState<WorkflowTraceEvent[]>([]);
  const [sla, setSla] = useState<WorkflowSLAMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [isPolling, setIsPolling] = useState(true);

  const fetchWorkflowData = async () => {
    try {
      const [stRes, evRes, slaRes] = await Promise.allSettled([
        api.getWorkflowState(processId),
        api.getWorkflowEvents(processId),
        api.getWorkflowSLA(processId),
      ]);

      if (stRes.status === 'fulfilled') setState(stRes.value);
      if (evRes.status === 'fulfilled') setEvents(evRes.value || []);
      if (slaRes.status === 'fulfilled') setSla(slaRes.value);
    } catch (err) {
      console.warn('Failed to fetch workflow data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkflowData();

    // 3-second polling interval for active workflow monitoring
    const interval = setInterval(() => {
      if (isPolling) {
        fetchWorkflowData();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [processId, isPolling]);

  const handleDecision = async (
    decision: 'APPROVED' | 'REJECTED' | 'ESCALATED',
    notes: string
  ) => {
    await api.decideWorkflowApproval(processId, decision, notes);
    await fetchWorkflowData();
  };

  const isAwaiting = state?.status === 'AWAITING_APPROVAL' || 
    (state?.current_step || '').includes('approval');

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Breadcrumb & Control Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-3">
          <Link
            href="/processes"
            className="p-2 text-slate-400 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
            title="Back to Processes"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                {state?.title || `Workflow #${processId.substring(0, 10)}`}
              </h2>
              <span className={`px-2.5 py-0.5 rounded text-xs font-bold uppercase tracking-wider ${
                state?.status === 'COMPLETED' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                isAwaiting ? 'bg-amber-50 text-amber-700 border border-amber-200 animate-pulse' :
                'bg-sky-50 text-sky-700 border border-sky-200'
              }`}>
                {state?.status || 'RUNNING'}
              </span>
            </div>
            <p className="text-xs font-mono text-slate-400 mt-0.5">
              Process ID: {processId}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsPolling(!isPolling)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border flex items-center gap-1.5 transition-colors ${
              isPolling
                ? 'bg-sky-50 border-sky-200 text-sky-700'
                : 'bg-slate-100 border-slate-200 text-slate-600'
            }`}
          >
            <Activity className={`w-3.5 h-3.5 ${isPolling ? 'animate-pulse text-sky-600' : ''}`} />
            {isPolling ? 'Live Polling Active' : 'Polling Paused'}
          </button>

          <button
            onClick={fetchWorkflowData}
            className="p-2 text-slate-500 hover:text-slate-900 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 shadow-sm transition-colors"
            title="Refresh Now"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Grid: Steps Panel (Left) & Actions + Timeline (Right) */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column: 13-node Stepper */}
        <div className="lg:col-span-1 space-y-6">
          <WorkflowStepsPanel
            state={state}
            sla={sla}
            isPolling={isPolling}
            onRefresh={fetchWorkflowData}
          />

          {/* Context / Metadata Card */}
          {state?.context && (
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-2">
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                Initial Workflow Context
              </h4>
              <pre className="text-xs font-mono bg-slate-50 p-3 rounded-lg border border-slate-100 overflow-x-auto text-slate-700">
                {JSON.stringify(state.context, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Right Column: Governance Actions + Interactive Timeline */}
        <div className="lg:col-span-2 space-y-6">
          <ProcessActions
            processId={processId}
            isAwaitingApproval={isAwaiting}
            riskLevel={state?.risk_level || 'HIGH'}
            amount={state?.context?.amount}
            onDecision={handleDecision}
          />

          <ProcessTimeline
            events={events}
            currentNode={state?.current_step}
          />
        </div>
      </div>
    </div>
  );
}
