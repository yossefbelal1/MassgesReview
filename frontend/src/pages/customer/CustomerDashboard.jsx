import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { 
  Radio, 
  Workflow, 
  Send, 
  Clock, 
  CheckCircle2, 
  ArrowUpRight, 
  Sparkles,
  ChevronLeft,
  Activity,
  Plus
} from 'lucide-react';

export default function CustomerDashboard({ onNavigate }) {
  const [channels, setChannels] = useState([]);
  const [automations, setAutomations] = useState([]);
  const [upcomingJobs, setUpcomingJobs] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [chRes, autoRes, jobsRes, histRes] = await Promise.all([
        apiClient.get('/channels/'),
        apiClient.get('/automations/'),
        apiClient.get('/jobs/upcoming'),
        apiClient.get('/history/'),
      ]);
      setChannels(chRes.data);
      setAutomations(autoRes.data);
      setUpcomingJobs(jobsRes.data);
      setHistory(histRes.data);
    } catch (err) {
      console.error('Error fetching dashboard', err);
    } finally {
      setLoading(false);
    }
  };

  const publishedToday = history.filter(h => {
    const pubDate = new Date(h.published_at);
    const today = new Date();
    return pubDate.toDateString() === today.toDateString() && h.status === 'SUCCESS';
  }).length;

  const failedToday = history.filter(h => {
    const pubDate = new Date(h.published_at);
    const today = new Date();
    return pubDate.toDateString() === today.toDateString() && h.status !== 'SUCCESS';
  }).length;

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-400 gap-3">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500"></div>
        <span className="text-xs sm:text-sm font-medium">جاري تحميل بيانات لوحة التحكم...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6" dir="rtl">
      {/* Top Welcome Banner */}
      <div className="bg-gradient-to-l from-emerald-950/40 via-slate-900 to-slate-900 border border-emerald-500/20 rounded-2xl p-4 sm:p-6 relative overflow-hidden shadow-xl">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] sm:text-xs font-semibold mb-2 sm:mb-3">
              <Sparkles className="w-3.5 h-3.5 flex-shrink-0" />
              <span>أتمتة ونشر تقييمات قنوات التداول 24/7</span>
            </div>
            <h1 className="text-lg sm:text-2xl font-bold text-white tracking-tight">مركز التحكم الآلي</h1>
            <p className="text-slate-400 text-xs sm:text-sm mt-1 max-w-xl leading-relaxed">
              انشر صفقاتك في قناتك بشكل طبيعي — يقوم النظام تلقائياً برصد ضرب الأهداف وتحويل تقييمات موثوقة بفواصل زمنية ذكية.
            </p>
          </div>

          <div className="grid grid-cols-2 sm:flex sm:items-center gap-2.5 pt-2 sm:pt-0 border-t sm:border-0 border-slate-800">
            <button
              onClick={() => onNavigate('create_automation')}
              className="px-3.5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white text-xs font-bold shadow-lg shadow-emerald-950 transition-all flex items-center justify-center gap-1.5"
            >
              <Plus className="w-4 h-4 flex-shrink-0" />
              <span>هدف جديد</span>
            </button>
            <button
              onClick={() => onNavigate('channels')}
              className="px-3.5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 active:scale-95 border border-slate-700 text-slate-200 text-xs font-semibold transition-colors flex items-center justify-center gap-1.5"
            >
              <Radio className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <span>قنواتي</span>
            </button>
          </div>
        </div>
      </div>

      {/* Metric Cards - 2 cols on mobile, 3 cols on desktop */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 sm:gap-5">
        <div 
          onClick={() => onNavigate('channels')} 
          className="bg-slate-900 border border-slate-800 rounded-2xl p-3.5 sm:p-5 hover:border-slate-700 active:scale-98 transition-all cursor-pointer"
        >
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider">القنوات</span>
            <Radio className="w-3.5 sm:w-4 h-3.5 sm:h-4 text-emerald-400" />
          </div>
          <div className="text-xl sm:text-3xl font-extrabold text-white">{channels.length}</div>
          <p className="text-[10px] sm:text-xs text-slate-400 mt-1 truncate">قنوات مربوطة ونشطة</p>
        </div>

        <div 
          onClick={() => onNavigate('automations')} 
          className="bg-slate-900 border border-slate-800 rounded-2xl p-3.5 sm:p-5 hover:border-slate-700 active:scale-98 transition-all cursor-pointer"
        >
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider">الأهداف</span>
            <Workflow className="w-3.5 sm:w-4 h-3.5 sm:h-4 text-blue-400" />
          </div>
          <div className="text-xl sm:text-3xl font-extrabold text-white">{automations.filter(a => a.is_active).length}</div>
          <p className="text-[10px] sm:text-xs text-slate-400 mt-1 truncate">أتمتات مراقبة فعالة</p>
        </div>

        <div 
          onClick={() => onNavigate('history')} 
          className="col-span-2 sm:col-span-1 bg-slate-900 border border-slate-800 rounded-2xl p-3.5 sm:p-5 hover:border-slate-700 active:scale-98 transition-all cursor-pointer"
        >
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider">نشر اليوم</span>
            <Send className="w-3.5 sm:w-4 h-3.5 sm:h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-xl sm:text-3xl font-extrabold text-emerald-400">{publishedToday}</span>
            {failedToday > 0 && <span className="text-xs text-rose-400 font-bold">({failedToday} خطأ)</span>}
          </div>
          <p className="text-[10px] sm:text-xs text-slate-400 mt-1 truncate">تقييمات منشورة اليوم</p>
        </div>
      </div>

      {/* Grid: Upcoming Jobs & Quick Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        {/* Left 2 Cols: Upcoming Scheduled Jobs */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-400" />
              <h3 className="text-xs sm:text-base font-bold text-white">المهام الجاري والمجدول تنفيذها</h3>
            </div>
            <button
              onClick={() => onNavigate('history')}
              className="text-[11px] sm:text-xs font-semibold text-emerald-400 hover:text-emerald-300 flex items-center gap-0.5"
            >
              <span>السجل الكامل</span>
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
          </div>

          {upcomingJobs.length === 0 ? (
            <div className="py-8 px-4 text-center border border-dashed border-slate-800 rounded-xl">
              <CheckCircle2 className="w-7 h-7 sm:w-8 sm:h-8 text-emerald-500/50 mx-auto mb-2" />
              <p className="text-xs sm:text-sm text-slate-300 font-medium">طابور المهام هادئ والريفيوهات جاهزة</p>
              <p className="text-[10px] sm:text-xs text-slate-400 mt-1">عند نشر كلمة هدف في قناتك، ستظهر المهام والفواصل الزمنية هنا تلقائياً.</p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {upcomingJobs.map((job) => (
                <div 
                  key={job.id}
                  className="flex items-center justify-between p-3 sm:p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 hover:border-slate-700 transition-colors"
                >
                  <div className="flex items-center gap-3 overflow-hidden">
                    <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse flex-shrink-0"></div>
                    <div className="overflow-hidden">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs sm:text-sm font-bold text-white truncate">"{job.trigger_text || 'هدف'}"</span>
                        <span className="text-[10px] sm:text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">الخطوة {job.current_step}/{job.total_steps}</span>
                      </div>
                      <p className="text-[10px] sm:text-xs text-slate-400 mt-0.5">وقت التنفيذ: {new Date(job.execute_at).toLocaleTimeString('ar-EG')}</p>
                    </div>
                  </div>
                  <span className="text-[10px] sm:text-xs font-bold px-2 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex-shrink-0">
                    {job.status === 'PENDING' ? 'قيد الانتظار' : job.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right 1 Col: Channels Status & Quick Links */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs sm:text-base font-bold text-white flex items-center gap-2">
                <Radio className="w-4 h-4 text-emerald-400" />
                <span>حالة القنوات المفعلة</span>
              </h3>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-semibold">
                {channels.length} قنوات
              </span>
            </div>
            
            {channels.length === 0 ? (
              <div className="text-center py-6 px-2">
                <p className="text-xs text-slate-400 mb-4">لم تقم بربط أي قناة تيليجرام حتى الآن.</p>
                <button
                  onClick={() => onNavigate('channels')}
                  className="w-full py-2.5 px-3 rounded-xl bg-emerald-600/20 border border-emerald-500/30 text-emerald-400 text-xs font-bold hover:bg-emerald-600/30 transition-colors flex items-center justify-center gap-1.5"
                >
                  <Plus className="w-4 h-4" />
                  <span>ربط أول قناة الآن</span>
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {channels.slice(0, 4).map((ch) => (
                  <div key={ch.id} className="p-2.5 sm:p-3 rounded-xl bg-slate-950/40 border border-slate-800/80 flex items-center justify-between">
                    <div className="overflow-hidden pl-2">
                      <p className="text-xs font-bold text-white truncate">{ch.title}</p>
                      <p className="text-[10px] text-slate-400 truncate font-mono">{ch.username ? `@${ch.username}` : ch.telegram_chat_id}</p>
                    </div>
                    <span className="flex items-center text-[10px] sm:text-[11px] text-emerald-400 font-semibold whitespace-nowrap flex-shrink-0">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 ml-1.5"></span> مفعلة
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="mt-4 pt-4 border-t border-slate-800">
            <button
              onClick={() => onNavigate('automations')}
              className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold transition-colors flex items-center justify-center gap-1.5"
            >
              <span>إدارة الأهداف والكلمات ({automations.length})</span>
              <ChevronLeft className="w-3.5 h-3.5 text-emerald-400" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
