import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { 
  Users, 
  Radio, 
  Workflow, 
  CreditCard, 
  Activity, 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  Server, 
  Database, 
  Send, 
  ArrowUpRight 
} from 'lucide-react';

export default function AdminDashboard({ onNavigate }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/admin/stats');
      setStats(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !stats) {
    return <div className="p-12 text-center text-slate-400">Loading admin statistics...</div>;
  }

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">ReviewFlow SaaS Operations</h1>
          <p className="text-xs text-slate-400 mt-1">Real-time multi-tenant monitoring, subscriptions health, and worker queue status.</p>
        </div>
        <button
          onClick={() => onNavigate('admin_customers')}
          className="px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-lg shadow-purple-950 transition-all flex items-center space-x-2"
        >
          <Users className="w-4 h-4" />
          <span>Manage Customers</span>
        </button>
      </div>

      {/* Main SaaS KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Total Customers</span>
            <Users className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-3xl font-extrabold text-white">{stats.total_customers}</div>
          <div className="flex items-center space-x-2 text-[11px] text-slate-400 mt-2">
            <span className="text-emerald-400 font-semibold">{stats.active_subscriptions} Active</span>
            <span>•</span>
            <span className="text-amber-400">{stats.expiring_soon} Expiring</span>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Connected Channels</span>
            <Radio className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-extrabold text-white">{stats.connected_channels}</div>
          <p className="text-[11px] text-slate-400 mt-2">Across all customer tenants</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Active Automations</span>
            <Workflow className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-3xl font-extrabold text-white">{stats.active_automations}</div>
          <p className="text-[11px] text-slate-400 mt-2">Live trigger rules active</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Jobs Executed Today</span>
            <Send className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-extrabold text-white">{stats.jobs_today}</div>
          <div className="flex items-center space-x-2 text-[11px] text-slate-400 mt-2">
            <span className="text-emerald-400 font-semibold">{stats.successful_jobs_today} Success</span>
            {stats.failed_jobs_today > 0 && <span className="text-rose-400">({stats.failed_jobs_today} Failed)</span>}
          </div>
        </div>
      </div>

      {/* System Health Card (Matching exact user spec) */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-md">
        <h2 className="text-base font-bold text-white mb-5 flex items-center space-x-2">
          <Activity className="w-5 h-5 text-emerald-400" />
          <span>SaaS System & Services Health</span>
        </h2>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Server className="w-5 h-5 text-slate-400" />
              <div>
                <span className="text-xs font-semibold text-white block">Worker Engine</span>
                <span className="text-[11px] text-slate-400">Delayed Queue</span>
              </div>
            </div>
            <span className="w-3 h-3 rounded-full bg-emerald-400 animate-pulse shadow-sm shadow-emerald-400"></span>
          </div>

          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Database className="w-5 h-5 text-slate-400" />
              <div>
                <span className="text-xs font-semibold text-white block">Database</span>
                <span className="text-[11px] text-slate-400">PostgreSQL / Storage</span>
              </div>
            </div>
            <span className="w-3 h-3 rounded-full bg-emerald-400 animate-pulse shadow-sm shadow-emerald-400"></span>
          </div>

          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Activity className="w-5 h-5 text-slate-400" />
              <div>
                <span className="text-xs font-semibold text-white block">Redis / State</span>
                <span className="text-[11px] text-slate-400">Idempotency Lock</span>
              </div>
            </div>
            <span className="w-3 h-3 rounded-full bg-emerald-400 animate-pulse shadow-sm shadow-emerald-400"></span>
          </div>

          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Radio className="w-5 h-5 text-slate-400" />
              <div>
                <span className="text-xs font-semibold text-white block">Telegram MTProto</span>
                <span className="text-[11px] text-slate-400">Central Userbot</span>
              </div>
            </div>
            <span className="w-3 h-3 rounded-full bg-emerald-400 animate-pulse shadow-sm shadow-emerald-400"></span>
          </div>
        </div>
      </div>
    </div>
  );
}
