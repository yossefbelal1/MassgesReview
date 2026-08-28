import React from 'react';
import { 
  LayoutDashboard, 
  Radio, 
  Layers, 
  Workflow, 
  History, 
  CreditCard, 
  Users, 
  Activity, 
  Sliders, 
  LogOut,
  Zap
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Sidebar({ currentTab, setCurrentTab }) {
  const { user, logout } = useAuth();
  const isAdmin = user?.role === 'admin';

  const customerNav = [
    { id: 'dashboard', name: 'الرئيسية (الإحصائيات)', icon: LayoutDashboard },
    { id: 'channels', name: 'قنواتي (ربط وتفعيل)', icon: Radio },
    { id: 'automations', name: 'الكلمات المفتاحية (الأهداف)', icon: Workflow },
    { id: 'history', name: 'سجل النشر المباشر', icon: History },
    { id: 'subscription', name: 'باقتي والاشتراك', icon: CreditCard },
  ];

  const adminNav = [
    { id: 'admin_dashboard', name: 'لوحة تحكم الأدمن', icon: LayoutDashboard },
    { id: 'admin_customers', name: 'قائمة العملاء والمشتركين', icon: Users },
    { id: 'admin_plans', name: 'الباقات والحدود', icon: Sliders },
    { id: 'admin_health', name: 'حالة السيرفر والعمال', icon: Activity },
  ];

  const navItems = isAdmin ? adminNav : customerNav;

  return (
    <aside className="w-64 bg-slate-900 border-l border-slate-800 flex flex-col h-screen select-none">
      {/* Brand Header */}
      <div className="p-6 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-600 to-green-400 flex items-center justify-center shadow-lg shadow-emerald-950">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-1.5">
              ريفيو فلو <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">SaaS</span>
            </h1>
            <p className="text-[11px] text-slate-400">أتمتة قنوات التداول والفوركس</p>
          </div>
        </div>
      </div>

      {/* Nav List */}
      <div className="flex-1 py-6 px-4 space-y-1.5 overflow-y-auto">
        <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          {isAdmin ? 'إدارة المنصة الشاملة' : 'لوحة تحكم العميل'}
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setCurrentTab(item.id)}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl font-medium text-sm transition-all duration-150 ${
                isActive
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-sm font-semibold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'text-emerald-400' : 'text-slate-400'}`} />
              <span>{item.name}</span>
            </button>
          );
        })}
      </div>

      {/* User Footer */}
      <div className="p-4 border-t border-slate-800 bg-slate-900/50">
        <div className="flex items-center justify-between mb-3 px-2">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-bold text-slate-300">
              {user?.full_name?.charAt(0) || 'ع'}
            </div>
            <div className="overflow-hidden">
              <p className="text-xs font-semibold text-white truncate">{user?.full_name || 'العميل'}</p>
              <p className="text-[11px] text-slate-400 truncate">{user?.tenant_name || user?.email}</p>
            </div>
          </div>
        </div>
        <button
          onClick={logout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-rose-400 hover:bg-rose-500/10 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span>تسجيل الخروج</span>
        </button>
      </div>
    </aside>
  );
}
