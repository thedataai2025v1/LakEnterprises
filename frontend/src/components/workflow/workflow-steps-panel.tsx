'use client';

import React from 'react';
import { WorkflowState, WorkflowSLAMetrics } from '@/types/api';
import { 
  CheckCircle2, 
  Circle, 
  Clock, 
  AlertTriangle, 
  PauseCircle, 
  RefreshCw,
  ShieldCheck,
  TrendingUp,
  Cpu
} from 'lucide-react';

interface WorkflowStepsPanelProps {
  state: WorkflowState | null;
  sla?: WorkflowSLAMetrics | null;
  isPolling?: boolean;
  onRefresh?: () => void;
  className?: string;
}

// Canonical 13-node LangGraph execution sequence
const CANONICAL_STEPS = [
  { key: 'orchestrator_node', label: 'Orchestrator Intake' },
  { key: 'input_guard_node', label: 'Input Guard & Scrubber' },
  { key: 'plan_investigation_node', label: 'Investigation Planner' },
  { key: 'document_analyst_node', label: 'Document Analyst' },
  { key: 'knowledge_retriever_node', label: 'Knowledge Retrieval' },
  { key: 'compliance_check_node', label: 'Compliance Verification' },
  { key: 'risk_evaluation_node', label: 'Risk & Exposure Analysis' },
  { key: 'response_drafter_node', label: 'Response Drafting' },
  { key: 'human_approval_node', label: 'Human Approval Gate' },
  { key: 'escalation_routing_node', label: 'Escalation Router' },
  { key: 'execute_resolution_node', label: 'Resolution Execution' },
  { key: 'audit_recorder_node', label: 'Audit Trail Recording' },
  { key: 'output_guard_node', label: 'Final Output Guard' },
];

export const WorkflowStepsPanel: React.FC<WorkflowStepsPanelProps> = ({
  state,
  sla,
  isPolling = false,
  onRefresh,
  className = '',
}) => {
  const currentStep = (state?.current_step || '').toLowerCase();
  const historyNodes = new Set((state?.history || []).map((h) => h.node.toLowerCase()));
  const isAwaiting = state?.status === 'AWAITING_APPROVAL' || currentStep.includes('approval');
  const isCompleted = state?.status === 'COMPLETED';

  return (
    <div className={`bg-white rounded-xl border border-slate-200 shadow-sm p-6 ${className}`}>
      {/* Header with live polling indicator */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-bold text-slate-900 text-sm">Graph Steps Engine</h3>
            <p className="text-xs text-slate-400">13-Node LangGraph State Machine</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isPolling && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200 animate-pulse">
              <RefreshCw className="w-3 h-3 animate-spin" />
              Live Polling (3s)
            </span>
          )}
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-md transition-colors"
              title="Manual Refresh"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* SLA Metric Card if available */}
      {sla && (
        <div className="mb-5 p-3.5 bg-slate-50 rounded-lg border border-slate-200/80 text-xs">
          <div className="flex items-center justify-between mb-1.5">
            <span className="font-semibold text-slate-700 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-amber-600" />
              SLA Tier: <strong className="uppercase">{sla.tier}</strong>
            </span>
            <span className={`px-2 py-0.5 rounded font-bold uppercase ${
              sla.is_breached ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-700'
            }`}>
              {sla.is_breached ? 'SLA BREACHED' : 'ON SCHEDULE'}
            </span>
          </div>
          <p className="text-slate-500">
            Time Remaining: <span className="font-mono font-bold text-slate-800">{sla.hours_remaining.toFixed(1)} hrs</span> of {sla.max_hours} hrs
          </p>
        </div>
      )}

      {/* Stepper List */}
      <div className="space-y-2">
        {CANONICAL_STEPS.map((step, idx) => {
          const stepKey = step.key.toLowerCase();
          const hasPassed = historyNodes.has(stepKey);
          const isCurrent = currentStep === stepKey;

          let stepStatus = 'pending';
          if (hasPassed) stepStatus = 'completed';
          if (isCurrent) stepStatus = isAwaiting ? 'awaiting' : 'running';

          return (
            <div
              key={step.key}
              className={`flex items-center justify-between px-3.5 py-2.5 rounded-lg border text-xs transition-colors ${
                stepStatus === 'completed'
                  ? 'bg-emerald-50/30 border-emerald-100 text-slate-800'
                  : stepStatus === 'running'
                  ? 'bg-sky-50 border-sky-300 text-sky-900 font-semibold shadow-xs'
                  : stepStatus === 'awaiting'
                  ? 'bg-amber-50 border-amber-300 text-amber-900 font-semibold shadow-xs'
                  : 'bg-white border-slate-100 text-slate-400'
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="font-mono text-[11px] w-4 text-slate-400">
                  {idx + 1}.
                </span>
                <span>{step.label}</span>
              </div>

              <div>
                {stepStatus === 'completed' && (
                  <span className="flex items-center gap-1 text-emerald-600 font-semibold">
                    <CheckCircle2 className="w-4 h-4" />
                    Passed
                  </span>
                )}
                {stepStatus === 'running' && (
                  <span className="flex items-center gap-1 text-sky-600 font-semibold animate-pulse">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    Executing
                  </span>
                )}
                {stepStatus === 'awaiting' && (
                  <span className="flex items-center gap-1 text-amber-600 font-semibold">
                    <PauseCircle className="w-4 h-4" />
                    Awaiting
                  </span>
                )}
                {stepStatus === 'pending' && (
                  <Circle className="w-3.5 h-3.5 text-slate-300" />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
