import React from 'react';
import { useAuth } from '../context/AuthContext';
import { ShieldCheck, Menu, Zap, Sparkles } from 'lucide-react';

export default function Navbar({ title, onOpenDrawer }) {
  const { user } = useAuth();
  const sub = user?.subscription;

  return (
    <header className="h-14 sm:h-16 bg-slate-900/80 border-b border-slate-800 px-4 sm:px-8 flex items-center justify-between backdrop-blur-md sticky top-0 z-30 select-none pt-safe" dir="rtl">
      {/* Title & Mobile Brand */}
      <div className="flex items-center gap-3 overflow-hidden">
        <button
          onClick={onOpenDrawer}
          className="md:hidden p-2 -mr-1 rounded-xl text-slate-300 hover:text-white hover:bg-slate-800 transition-colors flex items-center justify-center"
          aria-label="فتح القائمة الجانبية"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2 overflow-hidden">
          <div className="md:hidden w-7 h-7 rounded-lg bg-gradient-to-tr from-emerald-600 to-green-400 flex items-center justify-center flex-shrink-0 shadow-sm">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <h2 className="text-xs sm:text-base font-bold text-white tracking-tight truncate">{title}</h2>
        </div>
      </div>

      {/* Badges / Actions */}
      <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
        {/* Subscription status indicator on desktop */}
        {user?.role !== 'admin' && sub && (
          <div className="flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full bg-slate-800/90 border border-slate-700 text-[11px] sm:text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse flex-shrink-0"></span>
            <span className="font-medium text-slate-300 hidden sm:inline">الباقة: <strong className="text-white">{sub.plan_name}</strong></span>
            <span className="font-medium text-white sm:hidden">{sub.plan_name}</span>
            <span className="text-slate-500 hidden sm:inline">•</span>
            <span className="text-emerald-400 font-semibold">{sub.days_remaining} يوم</span>
          </div>
        )}

        {user?.role === 'admin' && (
          <div className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-400 text-[10px] sm:text-xs font-semibold">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">مدير المنصة (الأدمن)</span>
            <span className="sm:hidden">أدمن</span>
          </div>
        )}

        <div className="h-4 w-px bg-slate-800 hidden sm:block"></div>

        <div className="hidden lg:flex items-center gap-2 text-xs text-slate-400">
          <span>المحرك:</span>
          <span className="inline-flex items-center text-emerald-400 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 ml-1.5"></span> مراقب 24/7
          </span>
        </div>
      </div>
    </header>
  );
}
