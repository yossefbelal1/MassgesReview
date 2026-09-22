import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { 
  UserCheck, RefreshCw, BarChart3, Users, Settings, Bot, 
  X, LogOut, ExternalLink, Sparkles
} from 'lucide-react';

export default function WinbackMobileNav({ isOpen, onClose, activeTab, onSelectTab }) {
  const { user, logout } = useAuth();

  const navItems = [
    { id: 'cases', label: 'حالات الاسترداد الحية', icon: RefreshCw },
    { id: 'analytics', label: 'تحليلات أسباب المغادرة', icon: BarChart3 },
    { id: 'members', label: 'دليل الأعضاء الشامل', icon: Users },
    { id: 'settings', label: 'إعدادات وقوالب الاسترداد', icon: Settings },
    { id: 'userbots', label: 'ربط القنوات واليوزربوت', icon: Bot },
  ];

  return (
    <>
      {/* Mobile Bottom Navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 h-16 bg-slate-900/95 backdrop-blur-xl border-t border-slate-800/80 px-2 flex items-center justify-around z-30 select-none" dir="rtl">
        {navItems.slice(0, 4).map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`flex flex-col items-center justify-center py-1 px-2 rounded-xl transition-all ${
                isActive ? 'text-emerald-400 font-bold' : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              <Icon className={`w-5 h-5 mb-0.5 ${isActive ? 'scale-110' : ''}`} />
              <span className="text-[10px] leading-tight truncate max-w-[65px]">{item.label.split(' ')[0]}</span>
            </button>
          );
        })}

        {/* 5th item: More / Drawer trigger */}
        <button
          onClick={() => onSelectTab('userbots')}
          className={`flex flex-col items-center justify-center py-1 px-2 rounded-xl transition-all ${
            activeTab === 'userbots' ? 'text-emerald-400 font-bold' : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          <Bot className="w-5 h-5 mb-0.5" />
          <span className="text-[10px] leading-tight">اليوزربوت</span>
        </button>
      </nav>

      {/* Slide-out Drawer */}
      {isOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex justify-end bg-black/70 backdrop-blur-sm animate-fade-in" dir="rtl">
          <div className="w-72 bg-slate-900 h-full p-5 flex flex-col justify-between border-r border-slate-800 shadow-2xl">
            <div>
              {/* Drawer Header */}
              <div className="flex items-center justify-between pb-4 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center text-white">
                    <UserCheck className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="text-sm font-bold text-white block">TeleWinBack</span>
                    <span className="text-[9px] text-emerald-400 block font-semibold">استعادة ومتابعة الأعضاء</span>
                  </div>
                </div>
                <button
                  onClick={onClose}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Drawer Links */}
              <div className="py-4 space-y-1">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = activeTab === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        onSelectTab(item.id);
                        onClose();
                      }}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-bold transition-colors ${
                        isActive ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      <span>{item.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Drawer Footer */}
            <div className="pt-4 border-t border-slate-800 space-y-2">
              <a
                href="/"
                className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-400 text-xs"
              >
                <span>منصة ريفيو فلو</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>

              <button
                onClick={logout}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/20 text-xs font-bold"
              >
                <LogOut className="w-4 h-4" />
                <span>تسجيل الخروج</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
