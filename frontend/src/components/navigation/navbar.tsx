'use client';

import React from 'react';
import { useAuth } from '@/context/auth-context';
import { Bell, Shield, Activity } from 'lucide-react';

interface NavbarProps {
  title?: string;
}

export const Navbar: React.FC<NavbarProps> = ({ title = 'Enterprise Console' }) => {
  const { user } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-bold text-slate-800 tracking-tight">{title}</h1>
      </div>

      <div className="flex items-center gap-4">
        {/* Environment Badge */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full text-xs font-semibold">
          <Activity className="w-3.5 h-3.5 animate-pulse text-emerald-500" />
          <span>API Connected (:8001)</span>
        </div>

        {/* RBAC Role Indicator */}
        {user && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 text-slate-700 rounded-md text-xs font-medium border border-slate-200">
            <Shield className="w-3.5 h-3.5 text-sky-600" />
            <span>Role: <strong className="capitalize">{user.role}</strong></span>
          </div>
        )}
      </div>
    </header>
  );
};
