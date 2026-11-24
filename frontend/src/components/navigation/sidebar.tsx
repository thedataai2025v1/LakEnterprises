'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/context/auth-context';
import { 
  LayoutDashboard, 
  Workflow, 
  CheckSquare, 
  Files, 
  ShieldCheck, 
  LogOut, 
  LogIn,
  UserCheck 
} from 'lucide-react';

interface SidebarProps {
  className?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ className = '' }) => {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const navigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Processes', href: '/processes', icon: Workflow },
    { name: 'Approvals', href: '/approvals', icon: CheckSquare },
    { name: 'Knowledge & Docs', href: '/documents', icon: Files },
  ];

  return (
    <aside className={`w-64 bg-slate-900 text-slate-200 flex flex-col min-h-screen border-r border-slate-800 ${className}`}>
      {/* Brand header */}
      <div className="h-16 flex items-center px-6 gap-3 border-b border-slate-800 bg-slate-950">
        <div className="w-8 h-8 rounded-lg bg-sky-500 flex items-center justify-center font-bold text-white shadow-md">
          L
        </div>
        <div>
          <span className="font-bold text-base tracking-wide text-white">LakEnterprises</span>
          <span className="block text-xs text-sky-400 font-mono">Console UI Shell</span>
        </div>
      </div>

      {/* Navigation links */}
      <nav className="flex-1 px-4 py-6 space-y-1.5">
        {navigation.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* User profile & RBAC status */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/60">
        {user ? (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-sky-400 font-semibold text-sm">
                {user.username.charAt(0).toUpperCase()}
              </div>
              <div className="overflow-hidden">
                <p className="text-sm font-medium text-white truncate">{user.username}</p>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider bg-sky-950 text-sky-300 border border-sky-800">
                  {user.role}
                </span>
              </div>
            </div>
            <button
              onClick={() => logout()}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-md transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Sign Out
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-white bg-sky-600 hover:bg-sky-500 rounded-md shadow transition-colors"
          >
            <LogIn className="w-4 h-4" />
            Sign In / Demo
          </Link>
        )}
      </div>
    </aside>
  );
};
