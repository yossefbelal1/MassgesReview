import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { History, CheckCircle2, AlertCircle, Clock, Search, Filter } from 'lucide-react';

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

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">سجل النشر والعمليات المباشرة</h1>
          <p className="text-xs text-slate-400 mt-1">سجل تدقيق حي لجميع الريفيوهات المنشورة، الفواصل الزمنية، وحالة الإرسال في تيليجرام.</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-900 border border-slate-800 p-4 rounded-2xl">
        <div className="flex items-center gap-2">
          {[
            { id: 'ALL', label: 'الكل' },
            { id: 'SUCCESS', label: 'ناجح' },
            { id: 'FLOOD_WAIT', label: 'انتظار تيليجرام' },
            { id: 'FAILED', label: 'فشل' }
          ].map((st) => (
            <button
              key={st.id}
              onClick={() => setStatusFilter(st.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-colors ${
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
            className="w-full pr-9 pl-4 py-1.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-xs outline-none"
          />
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="p-12 text-center text-slate-400">جاري تحميل السجلات...</div>
      ) : filteredHistory.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center">
          <History className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-bold text-white mb-1">لا يوجد سجل نشر حتى الآن</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            عند رصد أي كلمة هدف ونشر الريفيوهات في قناتك، سيتم تسجيل كل عملية ورقم الرسالة في تيليجرام هنا فورياً.
          </p>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-lg">
          <div className="overflow-x-auto">
            <table className="w-full text-right border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/40 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  <th className="py-3.5 px-6">الوقت والتاريخ</th>
                  <th className="py-3.5 px-6">الهدف / الأتمتة</th>
                  <th className="py-3.5 px-6">الرسالة / العضو</th>
                  <th className="py-3.5 px-6">الخطوة</th>
                  <th className="py-3.5 px-6">رقم رسالة تيليجرام</th>
                  <th className="py-3.5 px-6">الحالة</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-xs text-slate-300 font-sans">
                {filteredHistory.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-4 px-6 text-slate-400 font-mono text-[11px]">
                      {new Date(item.published_at).toLocaleString('ar-EG')}
                    </td>
                    <td className="py-4 px-6 font-semibold text-white">
                      {item.automation_name || 'هدف مخصص'}
                    </td>
                    <td className="py-4 px-6 text-emerald-400 font-medium">
                      {item.message_title}
                    </td>
                    <td className="py-4 px-6 font-mono text-slate-400">
                      الخطوة #{item.step_number}
                    </td>
                    <td className="py-4 px-6 font-mono text-slate-300">
                      {item.telegram_message_id ? `#${item.telegram_message_id}` : '-'}
                    </td>
                    <td className="py-4 px-6">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold ${
                        item.status === 'SUCCESS'
                          ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                          : item.status === 'FLOOD_WAIT'
                          ? 'bg-amber-500/10 border border-amber-500/20 text-amber-400'
                          : 'bg-rose-500/10 border border-rose-500/20 text-rose-400'
                      }`}>
                        {item.status === 'SUCCESS' && <CheckCircle2 className="w-3 h-3" />}
                        {item.status === 'SUCCESS' ? 'تم النشر بنجاح' : item.status === 'FLOOD_WAIT' ? 'انتظار الفاصل' : 'فشل'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
