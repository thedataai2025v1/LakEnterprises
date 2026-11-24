'use client';

import React from 'react';
import { WorkflowTraceEvent } from '@/types/api';
import { CheckCircle2, Clock, AlertTriangle, PlayCircle, ShieldAlert, Cpu } from 'lucide-react';

interface ProcessTimelineProps {
  events: WorkflowTraceEvent[];
  currentNode?: string;
  className?: string;
}

export const ProcessTimeline: React.FC<ProcessTimelineProps> = ({
  events,
  currentNode,
  className = '',
}) => {
  if (!events || events.length === 0) {
    return (
      <div className={`p-8 bg-white rounded-xl border border-slate-200 text-center text-slate-400 ${className}`}>
        <Clock className="w-8 h-8 mx-auto mb-2 text-slate-300 animate-pulse" />
        <p className="text-sm font-medium">No timeline events recorded yet.</p>
        <p className="text-xs text-slate-400 mt-1">Events will appear as graph execution progresses.</p>
      </div>
    );
  }

  const getNodeIcon = (nodeName: string, eventType: string) => {
    if (eventType.includes('ERROR') || eventType.includes('FAIL')) {
      return <ShieldAlert className="w-4 h-4 text-rose-600" />;
    }
    if (nodeName.includes('approval') || nodeName.includes('risk')) {
      return <AlertTriangle className="w-4 h-4 text-amber-600" />;
    }
    if (eventType.includes('END') || eventType.includes('COMPLETE')) {
      return <CheckCircle2 className="w-4 h-4 text-emerald-600" />;
    }
    return <Cpu className="w-4 h-4 text-sky-600" />;
  };

  return (
    <div className={`bg-white rounded-xl border border-slate-200 p-6 shadow-sm ${className}`}>
      <h3 className="text-base font-bold text-slate-900 mb-6 flex items-center justify-between">
        <span>Execution Timeline & Trace</span>
        <span className="text-xs font-mono font-normal text-slate-400">
          {events.length} trace {events.length === 1 ? 'event' : 'events'}
        </span>
      </h3>

      <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
        {events.map((evt, idx) => {
          const isLatest = idx === events.length - 1;
          const isCurrent = currentNode && evt.node_name.toLowerCase() === currentNode.toLowerCase();

          return (
            <div key={evt.event_id || idx} className="relative group">
              {/* Node Dot / Icon Badge */}
              <div
                className={`absolute -left-[30px] top-0.5 w-6 h-6 rounded-full border flex items-center justify-center bg-white shadow-xs transition-all ${
                  isCurrent
                    ? 'border-sky-500 ring-4 ring-sky-100 bg-sky-50'
                    : 'border-slate-300 group-hover:border-slate-400'
                }`}
              >
                {getNodeIcon(evt.node_name, evt.event_type)}
              </div>

              {/* Event Content Card */}
              <div
                className={`p-4 rounded-lg border transition-all ${
                  isCurrent
                    ? 'border-sky-200 bg-sky-50/40 shadow-xs'
                    : 'border-slate-100 bg-slate-50/50 hover:bg-slate-50 hover:border-slate-200'
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-slate-800">
                      {evt.node_name}
                    </span>
                    <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-slate-200 text-slate-700">
                      {evt.event_type}
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">
                    {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : 'N/A'}
                  </span>
                </div>

                {evt.duration_ms !== undefined && (
                  <p className="text-[11px] text-slate-500 font-mono mb-2">
                    Duration: {evt.duration_ms.toFixed(1)} ms
                  </p>
                )}

                {/* Event Payload / Metadata summary */}
                {evt.payload && Object.keys(evt.payload).length > 0 && (
                  <div className="mt-2 text-xs font-mono bg-white p-2.5 rounded border border-slate-200/80 text-slate-700 overflow-x-auto max-h-36">
                    <pre>{JSON.stringify(evt.payload, null, 2)}</pre>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
