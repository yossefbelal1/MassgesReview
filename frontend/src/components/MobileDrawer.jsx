import React from 'react';
import { 
  X, 
  LogOut, 
  Shield, 
  UserCheck, 
  Zap, 
  CreditCard, 
  Radio, 
  Workflow, 
  History,
  LayoutDashboard,
  Users,
  Sliders,
  Activity,
  ExternalLink,
  ChevronLeft
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function MobileDrawer({ isOpen, onClose, currentTab, setCurrentTab, adminViewMode, setAdminViewMode }) {
  const { user, logout } = useAuth();
  const isAdmin = user?.role === 'admin';
  const sub = user?.subscription;

  if (!isOpen) return null;

  const handleSelectTab = (tabId) => {
    setCurrentTab(tabId);
    onClose();
  };

  const handleToggleAdminMode = (mode) => {
    setAdminViewMode(mode);
    if (mode === 'admin') {
      setCurrentTab('admin_dashboard');
    } else {
      setCurrentTab('dashboard');
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 md:hidden flex justify-end" dir="rtl">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm transition-opacity" 
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer Body */}
      <div className="relative w-4/5 max-w-xs bg-slate-900 border-r border-slate-800 h-full flex flex-col justify-between shadow-2xl z-10 pt-safe pb-safe">
        {/* Top Header */}
        <div>
          <div className="p-4 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-600 to-green-400 flex items-center justify-center shadow-md">
                <Zap className="w-4 h-4 text-white" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white">ريفيو فلو</h2>
                <span className="text-[10px] text-emerald-400 font-mono">ReviewFlow SaaS</span>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              aria-label="إغلاق القائمة"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* User Profile Card */}
          <div className="p-4 bg-slate-950/60 border-b border-slate-800/80">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-white text-sm flex-shrink-0">
                {user?.full_name?.charAt(0) || 'ع'}
              </div>
              <div className="overflow-hidden">
                <h3 className="text-xs font-bold text-white truncate">{user?.full_name || 'المستخدم'}</h3>
                <p className="text-[11px] text-slate-400 truncate">{user?.email}</p>
                {sub && user?.role !== 'admin' && (
                  <span className="inline-block mt-1 text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full font-semibold">
                    باقة {sub.plan_name} ({sub.days_remaining} يوم)
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Admin Mode Switcher (If Admin) */}
          {isAdmin && (
            <div className="p-3 m-3 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-2">وضع الحساب</span>
              <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-900 rounded-lg">
                <button
                  onClick={() => handleToggleAdminMode('admin')}
                  className={`py-1.5 px-2 rounded text-xs font-bold transition-all flex items-center justify-center gap-1 ${
                    adminViewMode === 'admin'
                      ? 'bg-emerald-600 text-white shadow'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <Shield className="w-3.5 h-3.5" />
                  <span>الأدمن</span>
                </button>
                <button
                  onClick={() => handleToggleAdminMode('customer')}
                  className={`py-1.5 px-2 rounded text-xs font-bold transition-all flex items-center justify-center gap-1 ${
                    adminViewMode === 'customer'
                      ? 'bg-emerald-600 text-white shadow'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <UserCheck className="w-3.5 h-3.5" />
                  <span>العميل</span>
                </button>
              </div>
            </div>
          )}

          {/* Quick Links */}
          <div className="p-3 space-y-1">
            <span className="px-3 text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              التنقل السريع
            </span>

            {(isAdmin && adminViewMode === 'admin' ? [
              { id: 'admin_dashboard', name: 'لوحة تحكم الأدمن', icon: LayoutDashboard },
              { id: 'admin_customers', name: 'المشتركون والعملاء', icon: Users },
              { id: 'admin_plans', name: 'الباقات والأسعار', icon: Sliders },
              { id: 'admin_health', name: 'صحة السيرفر والعمال', icon: Activity },
            ] : [
              { id: 'dashboard', name: 'الرئيسية والإحصائيات', icon: LayoutDashboard },
              { id: 'channels', name: 'قنواتي وتيليجرام', icon: Radio },
              { id: 'automations', name: 'الكلمات المفتاحية والأهداف', icon: Workflow },
              { id: 'history', name: 'سجل النشر والتدقيق', icon: History },
              { id: 'subscription', name: 'الاشتراك والباقة', icon: CreditCard },
            ]).map((link) => {
              const Icon = link.icon;
              const isActive = currentTab === link.id;
              return (
                <button
                  key={link.id}
                  onClick={() => handleSelectTab(link.id)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-medium transition-colors ${
                    isActive
                      ? 'bg-emerald-500/10 text-emerald-400 font-bold'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className="w-4 h-4" />
                    <span>{link.name}</span>
                  </div>
                  <ChevronLeft className="w-3.5 h-3.5 text-slate-600" />
                </button>
              );
            })}
          </div>
        </div>

        {/* Footer Logout */}
        <div className="p-4 border-t border-slate-800">
          <button
            onClick={() => {
              onClose();
              logout();
            }}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 text-xs font-bold transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span>تسجيل الخروج</span>
          </button>
        </div>
      </div>
    </div>
  );
}
