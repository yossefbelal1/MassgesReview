import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { 
  Radio, 
  Workflow, 
  Layers, 
  Send, 
  Clock, 
  CheckCircle2, 
  AlertCircle, 
  ArrowUpRight, 
  Calendar,
  Sparkles
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
      <div className="flex items-center justify-center h-64 text-slate-400 gap-3">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500"></div>
        <span>جاري تحميل بيانات لوحة التحكم...</span>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Top Welcome Banner */}
      <div className="bg-gradient-to-l from-emerald-950/40 via-slate-900 to-slate-900 border border-emerald-500/20 rounded-2xl p-6 relative overflow-hidden shadow-xl">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold mb-3">
              <Sparkles className="w-3.5 h-3.5" />
              <span>منصة أتمتة ونشر تقييمات قنوات التداول والفوركس 24/7</span>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">مركز التحكم والإدارة الآلية</h1>
            <p className="text-slate-400 text-sm mt-1 max-w-xl">
              انشر صفقاتك في قناتك بشكل طبيعي — يقوم النظام فوراً برصد ضرب الأهداف (مثل TP1 / TP2) وإعادة توجيه تقييمات حقيقية من أعضاء موثوقين بفواصل زمنية بشرية ذكية.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => onNavigate('automations')}
              className="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold shadow-lg shadow-emerald-950 transition-all flex items-center gap-2"
            >
              <Workflow className="w-4 h-4" />
              <span>الكلمات المفتاحية (الأهداف)</span>
            </button>
            <button
              onClick={() => onNavigate('channels')}
              className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-sm font-medium transition-colors flex items-center gap-2"
            >
              <Radio className="w-4 h-4" />
              <span>ربط قناة جديدة</span>
            </button>
          </div>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-semibold uppercase tracking-wider">القنوات المرتبطة</span>
            <Radio className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white">{channels.length}</div>
          <p className="text-xs text-slate-400 mt-1">قناة متصلة وجاهزة لاستقبال الريفيوهات</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-semibold uppercase tracking-wider">الأهداف المفعلة (Triggers)</span>
            <Workflow className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold text-white">{automations.filter(a => a.is_active).length}</div>
          <p className="text-xs text-slate-400 mt-1">تراقب إشارات وكلمات الصفقات في القناة</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-semibold uppercase tracking-wider">التقييمات المنشورة اليوم</span>
            <Send className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-emerald-400">{publishedToday}</span>
            {failedToday > 0 && <span className="text-xs text-rose-400">({failedToday} خطأ)</span>}
          </div>
          <p className="text-xs text-slate-400 mt-1">عملية تحويل آلي تمت بنجاح اليوم</p>
        </div>
      </div>

      {/* Grid: Upcoming Jobs & Quick Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Upcoming Scheduled Jobs */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <Clock className="w-5 h-5 text-emerald-400" />
              <h3 className="text-base font-bold text-white">المهام الجاري والمجدول تنفيذها</h3>
            </div>
            <button
              onClick={() => onNavigate('history')}
              className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
            >
              <span>عرض سجل النشر الكامل</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {upcomingJobs.length === 0 ? (
            <div className="p-8 text-center border border-dashed border-slate-800 rounded-xl">
              <CheckCircle2 className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <p className="text-sm text-slate-400 font-medium">جميع طوابير الإرسال مكتملة وهادئة</p>
              <p className="text-xs text-slate-400 mt-1">عند نشر كلمة هدف في قناتك، ستظهر المهام والفواصل الزمنية هنا تلقائياً.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {upcomingJobs.map((job) => (
                <div 
                  key={job.id}
                  className="flex items-center justify-between p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 hover:border-slate-700 transition-colors"
                >
                  <div className="flex items-center gap-3.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-white">الكلمة المرصودة: "{job.trigger_text || 'هدف'}"</span>
                        <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">الخطوة {job.current_step}/{job.total_steps}</span>
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5">وقت التنفيذ: {new Date(job.execute_at).toLocaleTimeString('ar-EG')}</p>
                    </div>
                  </div>
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                    {job.status === 'PENDING' ? 'قيد الانتظار' : job.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right 1 Col: Channels Status & Quick Links */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between">
          <div>
            <h3 className="text-base font-bold text-white mb-4 flex items-center gap-2">
              <Radio className="w-4 h-4 text-emerald-400" />
              <span>حالة القنوات المفعلة</span>
            </h3>
            
            {channels.length === 0 ? (
              <div className="text-center py-6">
                <p className="text-xs text-slate-400 mb-4">لم تقم بربط أي قناة تيليجرام حتى الآن.</p>
                <button
                  onClick={() => onNavigate('channels')}
                  className="w-full py-2 px-3 rounded-lg bg-emerald-600/20 border border-emerald-500/30 text-emerald-400 text-xs font-semibold hover:bg-emerald-600/30 transition-colors"
                >
                  + ربط أول قناة الآن
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {channels.slice(0, 4).map((ch) => (
                  <div key={ch.id} className="p-3 rounded-xl bg-slate-950/40 border border-slate-800/80 flex items-center justify-between">
                    <div className="overflow-hidden pl-2">
                      <p className="text-xs font-semibold text-white truncate">{ch.title}</p>
                      <p className="text-[11px] text-slate-400 truncate font-mono">{ch.username ? `@${ch.username}` : ch.telegram_chat_id}</p>
                    </div>
                    <span className="flex items-center text-[11px] text-emerald-400 font-medium whitespace-nowrap">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 ml-1.5"></span> مفعلة
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="mt-6 pt-5 border-t border-slate-800">
            <button
              onClick={() => onNavigate('automations')}
              className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors flex items-center justify-center gap-2"
            >
              <span>إدارة الأهداف والكلمات ({automations.length})</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
