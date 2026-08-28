import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Bell, ShieldCheck, CheckCircle2, AlertTriangle } from 'lucide-react';

export default function Navbar({ title }) {
  const { user } = useAuth();
  const sub = user?.subscription;

  return (
    <header className="h-16 bg-slate-900/50 border-b border-slate-800 px-8 flex items-center justify-between backdrop-blur-md sticky top-0 z-20">
      <div>
        <h2 className="text-base font-bold text-white tracking-wide">{title}</h2>
      </div>

      <div className="flex items-center gap-4">
        {/* Subscription status indicator */}
        {user?.role !== 'admin' && sub && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="font-medium text-slate-300">الباقة: <strong className="text-white">{sub.plan_name}</strong></span>
            <span className="text-slate-500">•</span>
            <span className="text-emerald-400 font-semibold">{sub.days_remaining} يوم متبقي</span>
          </div>
        )}

        {user?.role === 'admin' && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-400 text-xs font-semibold">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>وضع مدير المنصة (الأدمن)</span>
          </div>
        )}

        <div className="h-4 w-px bg-slate-800"></div>

        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span>المحرك:</span>
          <span className="inline-flex items-center text-emerald-400 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 ml-1.5"></span> نشط ومراقب 24/7
          </span>
        </div>
      </div>
    </header>
  );
}
