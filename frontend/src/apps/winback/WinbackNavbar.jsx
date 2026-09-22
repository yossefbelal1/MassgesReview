import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { 
  UserCheck, LogOut, Menu, RefreshCw, Sparkles, Shield, User, ExternalLink
} from 'lucide-react';

export default function WinbackNavbar({ onOpenDrawer, onRefresh, refreshing }) {
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
  };

  return (
    <header className="h-16 bg-slate-900/80 backdrop-blur-md border-b border-slate-800/80 px-4 sm:px-6 flex items-center justify-between z-20 shrink-0 select-none" dir="rtl">
      {/* Right side: Mobile Menu + Platform Title */}
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenDrawer}
          className="md:hidden p-2 rounded-xl bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 transition-colors"
          title="القائمة"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center shadow-md shadow-emerald-950/50">
            <UserCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm sm:text-base font-black text-white tracking-tight">
                منصة استعادة ومتابعة الأعضاء
              </h1>
              <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold">
                <Sparkles className="w-2.5 h-2.5" />
                TeleWinBack AI
              </span>
            </div>
            <p className="text-[10px] text-slate-400 hidden sm:block">
              رصد مغادرة الأعضاء، تواصل فوري عبر اليوزربوت، وتحليلات أسباب الخروج
            </p>
          </div>
        </div>
      </div>

      {/* Left side: Live engine indicator + User + Logout */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Engine status indicator */}
        <div className="hidden lg:flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-[11px] font-bold text-slate-300">الرصد الآلي: 24/7 نشط</span>
        </div>

        {/* User Info */}
        <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
          <div className="w-7 h-7 rounded-lg bg-emerald-600/30 text-emerald-400 font-bold flex items-center justify-center text-xs">
            {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'U'}
          </div>
          <div className="hidden sm:block text-right">
            <span className="text-xs font-bold text-white block leading-none">{user?.full_name || 'المدير'}</span>
            <span className="text-[9px] text-slate-400 block mt-0.5">{user?.company_name || user?.email}</span>
          </div>
        </div>

        {/* Standalone Logout Button */}
        <button
          onClick={handleLogout}
          className="p-2 sm:px-3 sm:py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 transition-all text-xs font-bold flex items-center gap-1.5"
          title="تسجيل الخروج"
        >
          <LogOut className="w-4 h-4" />
          <span className="hidden sm:inline">تسجيل الخروج</span>
        </button>
      </div>
    </header>
  );
}
