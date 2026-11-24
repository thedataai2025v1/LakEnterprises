'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api-client';
import { ProcessInstance, ProcessTemplate } from '@/types/api';
import { Workflow, Plus, Filter, RefreshCw, ArrowRight, ExternalLink } from 'lucide-react';
import Link from 'next/link';

export default function ProcessesPage() {
  const [processes, setProcesses] = useState<ProcessInstance[]>([]);
  const [templates, setTemplates] = useState<ProcessTemplate[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchProcesses = async () => {
    setLoading(true);
    try {
      const [procList, tplList] = await Promise.allSettled([
        api.listProcesses(),
        api.listTemplates(),
      ]);
      if (procList.status === 'fulfilled') setProcesses(procList.value || []);
      if (tplList.status === 'fulfilled') setTemplates(tplList.value || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProcesses();
  }, []);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Enterprise Processes</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Audit, track, and monitor agentic state machines across departments.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchProcesses()}
            className="flex items-center gap-1.5 px-3.5 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 shadow-sm transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Process Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-4">Title / ID</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Current Step</th>
                <th className="py-3 px-4">Initiator</th>
                <th className="py-3 px-4">Created Date</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {processes.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-400">
                    No process instances found.
                  </td>
                </tr>
              ) : (
                processes.map((proc) => (
                  <tr key={proc.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-4">
                      <Link
                        href={`/processes/${proc.id}`}
                        className="font-semibold text-slate-900 hover:text-sky-600 flex items-center gap-1.5"
                      >
                        {proc.title || 'Enterprise Process'}
                        <ExternalLink className="w-3.5 h-3.5 opacity-60" />
                      </Link>
                      <p className="text-xs text-slate-400 font-mono mt-0.5">{proc.id}</p>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2.5 py-1 rounded text-xs font-semibold uppercase tracking-wider ${
                        proc.status === 'COMPLETED' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                        proc.status === 'AWAITING_APPROVAL' ? 'bg-amber-50 text-amber-700 border border-amber-200' :
                        proc.status === 'RUNNING' ? 'bg-sky-50 text-sky-700 border border-sky-200' :
                        'bg-slate-100 text-slate-700 border border-slate-200'
                      }`}>
                        {proc.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs text-slate-600">
                      {proc.current_step || 'human_approval_node'}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      {proc.initiator || 'agent-supervisor'}
                    </td>
                    <td className="py-3.5 px-4 text-slate-400 text-xs">
                      {proc.created_at ? new Date(proc.created_at).toLocaleString() : 'Just now'}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Link
                        href={`/processes/${proc.id}`}
                        className="inline-flex items-center gap-1 px-3 py-1 bg-sky-50 hover:bg-sky-100 text-sky-700 border border-sky-200 rounded text-xs font-semibold transition-colors"
                      >
                        Open Graph <ArrowRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
