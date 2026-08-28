import React, { useState } from 'react';
import { useAuth, AuthProvider } from './context/AuthContext';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';
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

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-400">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-emerald-500 mr-3"></div>
        <span>Starting ReviewFlow Engine...</span>
      </div>
    );
  }

  if (!user) {
    if (authMode === 'register') {
      return <Register onSwitchToLogin={() => setAuthMode('login')} />;
    }
    return <Login onSwitchToRegister={() => setAuthMode('register')} />;
  }

  // Adjust default tab for admin
  const effectiveTab = (user.role === 'admin' && currentTab === 'dashboard') 
    ? 'admin_dashboard' 
    : currentTab;

  const getPageTitle = () => {
    switch (effectiveTab) {
      case 'dashboard': return 'Dashboard Overview';
      case 'channels': return 'Telegram Channels';
      case 'automations': return 'Trade Signal Automations';
      case 'create_automation': return 'Build Sequence Automation';
      case 'history': return 'Publishing & Execution History';
      case 'subscription': return 'Subscription & Plan Management';
      case 'admin_dashboard': return 'Admin Operations Overview';
      case 'admin_customers': return 'Customer Tenants Management';
      case 'admin_plans': return 'SaaS Plan & Resource Limits';
      case 'admin_health': return 'SaaS System Health & Worker Queues';
      default: return 'ReviewFlow Platform';
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
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar currentTab={effectiveTab} setCurrentTab={setCurrentTab} />
      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        <Navbar title={getPageTitle()} />
        <main className="flex-1 overflow-y-auto p-8 bg-slate-950/70">
          {renderContent()}
        </main>
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
