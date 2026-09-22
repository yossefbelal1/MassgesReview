import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { 
  UserCheck, RefreshCw, BarChart3, Users, Settings, Bot, 
  LogOut, ExternalLink, Sparkles, ShieldCheck
} from 'lucide-react';

export default function WinbackSidebar({ activeTab, onSelectTab }) {
  const { user, logout } = useAuth();

  const navItems = [
    { 
      id: 'cases', 
      label: 'حالات الاسترداد الحية', 
      sublabel: 'المغادرين والإرسال الفوري',
      icon: RefreshCw,
      badge: 'مباشر ⚡'
    },
    { 
      id: 'analytics', 
      label: 'تحليلات أسباب المغادرة', 
      sublabel: 'إحصائيات ونسب الخروج',
      icon: BarChart3 
    },
    { 
      id: 'members', 
      label: 'دليل الأعضاء الشامل', 
      sublabel: 'سجل جمهور القنوات',
      icon: Users 
    },
    { 
      id: 'settings', 
      label: 'قواعد وقوالب الاسترداد', 
      sublabel: 'التوقيت والرسائل الآلية',
      icon: Settings 
    },
    { 
      id: 'userbots', 
      label: 'ربط القنوات واليوزربوت', 
      sublabel: 'حسابات الإرسال النشطة',
      icon: Bot 
    },
  ];

  return (
    <aside className="hidden md:flex flex-col w-64 lg:w-72 bg-slate-900 border-l border-slate-800/80 h-full shrink-0 select-none" dir="rtl">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-emerald-600 via-emerald-500 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-950/60 ring-2 ring-emerald-500/20">
            <UserCheck className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-base font-black text-white tracking-tight">TeleWinBack</span>
              <span className="px-1.5 py-0.2 rounded-md bg-emerald-500/10 text-emerald-400 text-[9px] font-extrabold border border-emerald-500/30">
                PRO
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-medium">استعادة ومتابعة الأعضاء 24/7</p>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-1.5">
        <span className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-2">
          لوحة تحكم الاسترداد
        </span>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center justify-between px-3.5 py-3 rounded-2xl text-right transition-all group ${
                isActive
                  ? 'bg-gradient-to-l from-emerald-600/90 to-emerald-700 text-white font-bold shadow-lg shadow-emerald-950/60 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className={`p-2 rounded-xl transition-colors ${
                  isActive ? 'bg-white/10 text-white' : 'bg-slate-950 text-slate-400 group-hover:text-emerald-400'
                }`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div className="truncate">
                  <div className="text-xs font-bold leading-tight truncate">{item.label}</div>
                  <div className={`text-[10px] truncate ${isActive ? 'text-emerald-100' : 'text-slate-400'}`}>
                    {item.sublabel}
                  </div>
                </div>
              </div>

              {item.badge && (
                <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold shrink-0 ${
                  isActive ? 'bg-white/20 text-white' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                }`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Footer / Account / Switch Link */}
      <div className="p-3.5 border-t border-slate-800/80 bg-slate-950/40 space-y-2">
        {/* Switch to ReviewFlow if accessible */}
        <a
          href="/"
          className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-slate-900/90 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors text-[11px]"
        >
          <span className="flex items-center gap-2">
            <ExternalLink className="w-3.5 h-3.5 text-slate-500" />
            <span>منصة ريفيو فلو (الإشارات)</span>
          </span>
          <span className="text-[9px] text-slate-400">الرئيسية ↗</span>
        </a>

        {/* User Card & Logout */}
        <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900 border border-slate-800/80">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-emerald-600/30 text-emerald-400 font-bold flex items-center justify-center text-xs shrink-0">
              {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'U'}
            </div>
            <div className="truncate">
              <span className="text-xs font-bold text-white block truncate leading-tight">{user?.full_name || 'المدير'}</span>
              <span className="text-[9px] text-slate-400 block truncate">{user?.company_name || 'Winback Client'}</span>
            </div>
          </div>

          <button
            onClick={logout}
            className="p-1.5 text-slate-500 hover:text-rose-400 transition-colors shrink-0"
            title="تسجيل الخروج"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
