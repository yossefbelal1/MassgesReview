import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import WinbackLogin from './WinbackLogin';
import WinbackRegister from './WinbackRegister';
import WinbackLayout from './WinbackLayout';
import RetentionDashboard from '../../pages/customer/RetentionDashboard';
import { UserCheck } from 'lucide-react';

export default function WinbackApp() {
  const { user, loading } = useAuth();
  
  // Determine initial auth mode from URL (/winback/register or /register)
  const [authMode, setAuthMode] = useState(() => {
    const path = window.location.pathname.toLowerCase();
    return path.includes('register') ? 'register' : 'login';
  });

  const [activeTab, setActiveTab] = useState('cases');

  // Sync tab with URL hash or param if present
  useEffect(() => {
    const hash = window.location.hash.replace('#', '');
    if (['cases', 'analytics', 'members', 'settings', 'userbots'].includes(hash)) {
      setActiveTab(hash);
    }
  }, []);

  const handleSelectTab = (tab) => {
    setActiveTab(tab);
    window.location.hash = tab;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-400 gap-3" dir="rtl">
        <div className="relative">
          <div className="w-12 h-12 rounded-2xl bg-emerald-600/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
            <UserCheck className="w-6 h-6 animate-pulse" />
          </div>
          <div className="absolute inset-0 rounded-2xl border-2 border-emerald-500 border-t-transparent animate-spin"></div>
        </div>
        <span className="text-sm font-bold text-white tracking-wide">جاري تشغيل منصة استعادة ومتابعة الأعضاء...</span>
        <span className="text-xs text-slate-500 font-mono">TeleWinBack AI Engine</span>
      </div>
    );
  }

  if (!user) {
    if (authMode === 'register') {
      return <WinbackRegister onSwitchToLogin={() => setAuthMode('login')} />;
    }
    return <WinbackLogin onSwitchToRegister={() => setAuthMode('register')} />;
  }

  return (
    <WinbackLayout activeTab={activeTab} onSelectTab={handleSelectTab}>
      <RetentionDashboard 
        externalTab={activeTab} 
        onTabChange={handleSelectTab} 
      />
    </WinbackLayout>
  );
}
