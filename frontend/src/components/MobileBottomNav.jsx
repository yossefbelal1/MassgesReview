import React from 'react';
import { 
  LayoutDashboard, 
  Radio, 
  Workflow, 
  History, 
  CreditCard, 
  Users, 
  Activity, 
  Sliders,
  ShieldCheck,
  UserCheck
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function MobileBottomNav({ currentTab, setCurrentTab, adminViewMode, onOpenDrawer }) {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const customerItems = [
    { id: 'dashboard', name: 'الرئيسية', icon: LayoutDashboard },
    { id: 'channels', name: 'قنواتي', icon: Radio },
    { id: 'automations', name: 'الأتمتة', icon: Workflow },
    { id: 'history', name: 'السجل', icon: History },
    { id: 'subscription', name: 'باقتي', icon: CreditCard },
  ];

  const adminItems = [
    { id: 'admin_dashboard', name: 'الأدمن', icon: LayoutDashboard },
    { id: 'admin_customers', name: 'العملاء', icon: Users },
    { id: 'admin_plans', name: 'الباقات', icon: Sliders },
    { id: 'admin_health', name: 'السيرفر', icon: Activity },
    { id: 'dashboard', name: 'القنوات', icon: UserCheck },
  ];

  const items = (isAdmin && adminViewMode === 'admin') ? adminItems : customerItems;

  return (
    <nav 
      className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-slate-900/95 backdrop-blur-xl border-t border-slate-800/90 px-2 py-1.5 pb-safe shadow-2xl select-none"
      dir="rtl"
      aria-label="التنقل الرئيسي للهاتف"
    >
      <div className="flex items-center justify-around max-w-md mx-auto">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id || (item.id === 'automations' && currentTab === 'create_automation');
          
          return (
            <button
              key={item.id}
              onClick={() => setCurrentTab(item.id)}
              className={`flex flex-col items-center justify-center py-1 px-2 rounded-xl transition-all duration-150 flex-1 min-h-[48px] relative ${
                isActive
                  ? 'text-emerald-400 font-bold'
                  : 'text-slate-400 hover:text-slate-200 active:scale-95'
              }`}
            >
              {isActive && (
                <span className="absolute -top-1.5 w-6 h-1 bg-emerald-400 rounded-full shadow-[0_0_8px_rgba(52,211,153,0.6)]"></span>
              )}
              <div className={`p-1 rounded-lg transition-colors ${isActive ? 'bg-emerald-500/10' : ''}`}>
                <Icon className={`w-5 h-5 ${isActive ? 'text-emerald-400' : 'text-slate-400'}`} />
              </div>
              <span className={`text-[10px] tracking-tight mt-0.5 ${isActive ? 'text-emerald-300 font-extrabold' : 'text-slate-400'}`}>
                {item.name}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
