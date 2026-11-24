'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api-client';
import { DocumentMetadata, SearchResult } from '@/types/api';
import { Search, FileText, Layers, RefreshCw, Sparkles } from 'lucide-react';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const docs = await api.listDocuments();
      setDocuments(docs || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    try {
      const results = await api.searchDocuments(query.trim(), 5);
      setSearchResults(results || []);
    } catch (err: any) {
      alert(`Search failed: ${err?.message || 'Error occurred'}`);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Enterprise Knowledge & Documents</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Hybrid retrieval (BM25 keyword + semantic vector embeddings) for agentic research.
        </p>
      </div>

      {/* Search Input Bar */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="relative flex-1">
          <Search className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search enterprise policies, vendor invoices, SLAs, or technical documentation..."
            className="w-full pl-11 pr-4 py-2.5 rounded-lg border border-slate-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent shadow-sm"
          />
        </div>
        <button
          type="submit"
          disabled={searching}
          className="flex items-center gap-2 px-5 py-2.5 bg-sky-600 hover:bg-sky-500 text-white text-sm font-semibold rounded-lg shadow-sm transition-colors disabled:opacity-50"
        >
          <Sparkles className="w-4 h-4" />
          <span>{searching ? 'Retrieving...' : 'Hybrid Search'}</span>
        </button>
      </form>

      {/* Search Results Display */}
      {searchResults.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider">
            Search Matches ({searchResults.length})
          </h3>
          <div className="space-y-3">
            {searchResults.map((res, idx) => (
              <div key={idx} className="bg-white p-4 rounded-xl border border-sky-100 shadow-sm space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-200">
                    Source: {res.source}
                  </span>
                  <span className="text-slate-400 font-mono">Score: {res.score.toFixed(3)}</span>
                </div>
                <p className="text-sm text-slate-800 leading-relaxed">{res.content}</p>
                {res.locator && (
                  <p className="text-[11px] text-slate-400 font-mono">Locator: {res.locator}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Document Library Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="font-bold text-slate-900 text-sm">Indexed Corpora</h3>
          <button
            onClick={() => fetchDocs()}
            className="text-xs font-medium text-slate-500 hover:text-slate-800 flex items-center gap-1"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>
        <div className="divide-y divide-slate-100">
          {documents.length === 0 ? (
            <p className="p-6 text-sm text-slate-400 text-center">No documents in vector corpus.</p>
          ) : (
            documents.map((doc) => (
              <div key={doc.id} className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-800">{doc.filename}</p>
                    <p className="text-xs text-slate-400">ID: {doc.id}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-xs text-slate-500">
                  <span className="flex items-center gap-1 font-medium bg-slate-100 px-2.5 py-1 rounded">
                    <Layers className="w-3.5 h-3.5 text-slate-400" />
                    {doc.chunks_count || 1} chunks
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
