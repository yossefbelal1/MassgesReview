import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { History, CheckCircle2, AlertCircle, Clock, Search, Filter, ExternalLink, Radio, MessageSquare } from 'lucide-react';

export default function PublishingHistory() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchHistory();
  }, [statusFilter]);

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const url = statusFilter === 'ALL' ? '/history/' : `/history/?status=${statusFilter}`;
      const res = await apiClient.get(url);
      setHistory(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filteredHistory = history.filter(h => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      (h.automation_name && h.automation_name.toLowerCase().includes(term)) ||
      (h.message_title && h.message_title.toLowerCase().includes(term)) ||
      (h.error_details && h.error_details.toLowerCase().includes(term))
    );
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'SUCCESS':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] sm:text-xs font-bold bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>ناجح ومسلم</span>
          </span>
        );
      case 'FLOOD_WAIT':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] sm:text-xs font-bold bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <Clock className="w-3.5 h-3.5" />
            <span>انتظار تيليجرام</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] sm:text-xs font-bold bg-rose-500/10 border border-rose-500/20 text-rose-400">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>فشل الإرسال</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <h1 className="text-lg sm:text-xl font-bold text-white tracking-tight">سجل النشر والعمليات المباشرة</h1>
          <p className="text-[11px] sm:text-xs text-slate-400 mt-0.5">سجل تدقيق حي لجميع الرسائل المنشورة وأرقامها في تيليجرام.</p>
        </div>
      </div>

      {/* Filters & Search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-900 border border-slate-800 p-3 sm:p-4 rounded-2xl">
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
          {[
            { id: 'ALL', label: 'الكل' },
            { id: 'SUCCESS', label: 'ناجح' },
            { id: 'FLOOD_WAIT', label: 'انتظار' },
            { id: 'FAILED', label: 'فشل' }
          ].map((st) => (
            <button
              key={st.id}
              onClick={() => setStatusFilter(st.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap transition-colors ${
                statusFilter === st.id
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              {st.label}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="w-4 h-4 text-slate-500 absolute right-3 top-2.5" />
          <input
            type="text"
            placeholder="بحث في السجلات..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pr-9 pl-4 py-2 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-xs outline-none"
          />
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="p-12 text-center text-slate-400">جاري تحميل السجلات...</div>
      ) : filteredHistory.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 sm:p-12 text-center">
          <History className="w-10 sm:w-12 h-10 sm:h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-sm sm:text-base font-bold text-white mb-1">لا يوجد سجل نشر حتى الآن</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            عند رصد أي كلمة هدف ونشر الريفيوهات في قناتك، سيتم تسجيل كل عملية ورقم الرسالة في تيليجرام هنا فورياً.
          </p>
        </div>
      ) : (
        <>
          {/* Mobile Card Timeline View (< md) */}
          <div className="md:hidden space-y-3">
            {filteredHistory.map((h) => (
              <div 
                key={h.id}
                className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3 shadow-md"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-bold">
                    الخطوة {h.step_number}
                  </span>
                  {getStatusBadge(h.status)}
                </div>

                <div className="space-y-1">
                  <h4 className="text-xs font-bold text-white leading-snug">{h.message_title || 'تقييم من عضو'}</h4>
                  <div className="flex items-center gap-2 text-[11px] text-slate-400">
                    <span className="text-emerald-400 font-medium">{h.automation_name || 'أتمتة الهدف'}</span>
                  </div>
                </div>

                <div className="pt-2.5 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
                  <span className="text-slate-400 font-mono">
                    {new Date(h.published_at).toLocaleString('ar-EG', { dateStyle: 'short', timeStyle: 'short' })}
                  </span>

                  {h.telegram_message_id && (
                    <span className="text-emerald-400 font-mono font-bold bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                      ID: #{h.telegram_message_id}
                    </span>
                  )}
                </div>

                {h.error_details && (
                  <p className="text-[10px] text-rose-400 bg-rose-500/10 p-2 rounded-lg break-words">
                    {h.error_details}
                  </p>
                )}
              </div>
            ))}
          </div>

          {/* Desktop Tabular View (>= md) */}
          <div className="hidden md:block bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-lg">
            <div className="overflow-x-auto">
              <table className="w-full text-right border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-950/60 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                    <th className="py-3.5 px-6">الوقت والتاريخ</th>
                    <th className="py-3.5 px-6">الهدف / الأتمتة</th>
                    <th className="py-3.5 px-6">الرسالة المنشورة</th>
                    <th className="py-3.5 px-6 text-center">الخطوة</th>
                    <th className="py-3.5 px-6 text-center">حالة النشر</th>
                    <th className="py-3.5 px-6">معرف الرسالة</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-xs">
                  {filteredHistory.map((h) => (
                    <tr key={h.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-4 px-6 text-slate-300 font-mono">
                        {new Date(h.published_at).toLocaleString('ar-EG')}
                      </td>
                      <td className="py-4 px-6 font-semibold text-white">
                        {h.automation_name || 'أتمتة افتراضية'}
                      </td>
                      <td className="py-4 px-6 text-slate-300">
                        {h.message_title || 'تقييم من بنك الرسائل'}
                      </td>
                      <td className="py-4 px-6 text-center">
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[11px]">
                          {h.step_number}
                        </span>
                      </td>
                      <td className="py-4 px-6 text-center">
                        {getStatusBadge(h.status)}
                      </td>
                      <td className="py-4 px-6 font-mono text-slate-400">
                        {h.telegram_message_id ? (
                          <span className="text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                            #{h.telegram_message_id}
                          </span>
                        ) : (
                          <span className="text-slate-600">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
