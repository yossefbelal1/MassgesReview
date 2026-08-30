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
  ArrowUpRight,
  Shield,
  ChevronLeft
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
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-400 gap-3">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500"></div>
        <span className="text-xs sm:text-sm font-medium">جاري تحميل إحصائيات الإدارة...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6 max-w-6xl mx-auto" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-lg sm:text-xl font-bold text-white tracking-tight">لوحة تحكم مدير المنصة (الأدمن)</h1>
          <p className="text-[11px] sm:text-xs text-slate-400 mt-0.5">مراقبة المشتركين، أداء السيرفر، وطوابير النشر اللحظية.</p>
        </div>
        <button
          onClick={() => onNavigate('admin_customers')}
          className="px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 active:scale-95 text-white text-xs font-bold shadow-lg shadow-purple-950 transition-all flex items-center justify-center gap-1.5 self-stretch sm:self-auto"
        >
          <Users className="w-4 h-4" />
          <span>إدارة المشتركين</span>
        </button>
      </div>

      {/* Main SaaS KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider">إجمالي المشتركين</span>
            <Users className="w-3.5 sm:w-4 h-3.5 sm:h-4 text-purple-400" />
          </div>
          <div className="text-xl sm:text-3xl font-extrabold text-white">{stats.total_customers}</div>
          <div className="flex items-center gap-1 text-[10px] sm:text-[11px] text-slate-400 mt-2 flex-wrap">
            <span className="text-emerald-400 font-bold">{stats.active_subscriptions} نشط</span>
            <span>•</span>
            <span className="text-amber-400">{stats.expiring_soon} ينتهي قريباً</span>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider">القنوات المتصلة</span>
            <Radio className="w-3.5 sm:w-4 h-3.5 sm:h-4 text-emerald-400" />
          </div>
          <div className="text-xl sm:text-3xl font-extrabold text-white">{stats.connected_channels}</div>
          <p className="text-[10px] sm:text-[11px] text-slate-400 mt-2">عبر كافة حسابات العملاء</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider">الأهداف النشطة</span>
            <Workflow className="w-3.5 sm:w-4 h-3.5 sm:h-4 text-blue-400" />
          </div>
          <div className="text-xl sm:text-3xl font-extrabold text-white">{stats.active_automations}</div>
          <p className="text-[10px] sm:text-[11px] text-slate-400 mt-2">قواعد مراقبة فعالة</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider">نشر اليوم</span>
            <Send className="w-3.5 sm:w-4 h-3.5 sm:h-4 text-emerald-400" />
          </div>
          <div className="text-xl sm:text-3xl font-extrabold text-white">{stats.jobs_today}</div>
          <div className="flex items-center gap-1 text-[10px] sm:text-[11px] text-slate-400 mt-2 flex-wrap">
            <span className="text-emerald-400 font-bold">{stats.successful_jobs_today} ناجح</span>
            {stats.failed_jobs_today > 0 && <span className="text-rose-400">({stats.failed_jobs_today} خطأ)</span>}
          </div>
        </div>
      </div>

      {/* Worker Health & System Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-400" />
            <h3 className="text-xs sm:text-base font-bold text-white">حالة المحرك والسيرفر والعمال</h3>
          </div>
          <span className="text-[10px] sm:text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-bold">
            جاهزية 100%
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Server className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <div>
                <span className="text-[10px] text-slate-400 block">عامل الرصد (Listener)</span>
                <strong className="text-white text-xs">ReviewFlow Worker</strong>
              </div>
            </div>
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Database className="w-4 h-4 text-blue-400 flex-shrink-0" />
              <div>
                <span className="text-[10px] text-slate-400 block">قاعدة البيانات (PostgreSQL)</span>
                <strong className="text-white text-xs">reviewflow_production</strong>
              </div>
            </div>
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Activity className="w-4 h-4 text-amber-400 flex-shrink-0" />
              <div>
                <span className="text-[10px] text-slate-400 block">طابور المهام (Redis Queue)</span>
                <strong className="text-white text-xs">Redis Cluster</strong>
              </div>
            </div>
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
          </div>
        </div>
      </div>
    </div>
  );
}
