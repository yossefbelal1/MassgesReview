import React, { useState } from 'react';
import { useAuth, AuthProvider } from './context/AuthContext';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';
import MobileBottomNav from './components/MobileBottomNav';
import MobileDrawer from './components/MobileDrawer';
import Login from './pages/Login';
import Register from './pages/Register';

// Customer Pages
import CustomerDashboard from './pages/customer/CustomerDashboard';
import ChannelsPage from './pages/customer/ChannelsPage';
import MessageLibrary from './pages/customer/MessageLibrary';
import AutomationsPage from './pages/customer/AutomationsPage';
import CreateAutomation from './pages/customer/CreateAutomation';
import PublishingHistory from './pages/customer/PublishingHistory';
import SubscriptionPage from './pages/customer/SubscriptionPage';

// Admin Pages
import AdminDashboard from './pages/admin/AdminDashboard';
import CustomerList from './pages/admin/CustomerList';
import PlansManager from './pages/admin/PlansManager';

function MainApp() {
  const { user, loading } = useAuth();
  const [authMode, setAuthMode] = useState('login'); // 'login' or 'register'
  const [currentTab, setCurrentTab] = useState('dashboard');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [adminViewMode, setAdminViewMode] = useState(() => {
    return user?.role === 'admin' ? 'admin' : 'customer';
  });

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-400 gap-3">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-emerald-500"></div>
        <span className="text-sm font-medium">جاري تشغيل منصة ريفيو فلو...</span>
      </div>
    );
  }

  if (!user) {
    if (authMode === 'register') {
      return <Register onSwitchToLogin={() => setAuthMode('login')} />;
    }
    return <Login onSwitchToRegister={() => setAuthMode('register')} />;
  }

  const effectiveTab = currentTab;

  const getPageTitle = () => {
    switch (effectiveTab) {
      case 'dashboard': return 'الرئيسية والإحصائيات';
      case 'channels': return 'قنوات تيليجرام';
      case 'automations': return 'الكلمات المفتاحية والأهداف';
      case 'create_automation': return 'إنشاء هدف / كلمة مفتاحية';
      case 'history': return 'سجل النشر المباشر';
      case 'subscription': return 'الاشتراك والباقات';
      case 'admin_dashboard': return 'لوحة تحكم الأدمن';
      case 'admin_customers': return 'قائمة المشتركين والعملاء';
      case 'admin_plans': return 'إدارة الباقات والحدود';
      case 'admin_health': return 'صحة السيرفر والعمال';
      default: return 'ريفيو فلو SaaS';
    }
  };

  const renderContent = () => {
    switch (effectiveTab) {
      // Customer Routes
      case 'dashboard':
        return <CustomerDashboard onNavigate={setCurrentTab} />;
      case 'channels':
        return <ChannelsPage />;
      case 'automations':
        return <AutomationsPage onNavigate={setCurrentTab} />;
      case 'create_automation':
        return <CreateAutomation onNavigate={setCurrentTab} />;
      case 'history':
        return <PublishingHistory />;
      case 'subscription':
        return <SubscriptionPage />;

      // Admin Routes
      case 'admin_dashboard':
        return <AdminDashboard onNavigate={setCurrentTab} />;
      case 'admin_customers':
        return <CustomerList />;
      case 'admin_plans':
        return <PlansManager />;
      case 'admin_health':
        return <AdminDashboard onNavigate={setCurrentTab} />;

      default:
        return <CustomerDashboard onNavigate={setCurrentTab} />;
    }
  };

  return (
    <div className="flex h-screen h-[100dvh] bg-slate-950 text-slate-100 overflow-hidden" dir="rtl">
      {/* Desktop Sidebar */}
      <Sidebar 
        currentTab={effectiveTab} 
        setCurrentTab={setCurrentTab} 
        adminViewMode={adminViewMode}
        setAdminViewMode={setAdminViewMode}
      />

      {/* Main Content Viewport */}
      <div className="flex-1 flex flex-col h-full overflow-hidden min-w-0">
        {/* Top Navbar */}
        <Navbar 
          title={getPageTitle()} 
          onOpenDrawer={() => setDrawerOpen(true)} 
        />

        {/* Scrollable Page Content */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-3.5 sm:p-6 md:p-8 pb-24 md:pb-8 bg-slate-950/70">
          <div className="max-w-7xl mx-auto w-full">
            {renderContent()}
          </div>
        </main>

        {/* Mobile Bottom Navigation Bar */}
        <MobileBottomNav 
          currentTab={effectiveTab} 
          setCurrentTab={setCurrentTab} 
          adminViewMode={adminViewMode}
          onOpenDrawer={() => setDrawerOpen(true)}
        />

        {/* Mobile Slide Drawer Menu */}
        <MobileDrawer 
          isOpen={drawerOpen} 
          onClose={() => setDrawerOpen(false)} 
          currentTab={effectiveTab} 
          setCurrentTab={setCurrentTab}
          adminViewMode={adminViewMode}
          setAdminViewMode={setAdminViewMode}
        />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}
