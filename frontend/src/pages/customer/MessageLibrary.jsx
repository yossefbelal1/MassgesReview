import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { Layers, Sparkles, CheckCircle2, ShieldCheck, MessageSquare, Quote } from 'lucide-react';

export default function MessageLibrary() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('ALL');

  useEffect(() => {
    fetchMessages();
  }, [categoryFilter]);

  const fetchMessages = async () => {
    try {
      setLoading(true);
      const url = categoryFilter === 'ALL' ? '/messages/' : `/messages/?category=${categoryFilter}`;
      const res = await apiClient.get(url);
      setMessages(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const categories = [
    { id: 'ALL', label: 'الكل' },
    { id: 'Results', label: 'نتائج وأرباح' },
    { id: 'Social Proof', label: 'تفاعل حقيقي' },
    { id: 'Reviews', label: 'تقييمات' },
    { id: 'VIP Feedback', label: 'آراء الـ VIP' }
  ];

  return (
    <div className="space-y-4 sm:space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-lg sm:text-xl font-bold text-white tracking-tight">بنك التقييمات الحقيقية المركزي</h1>
          <p className="text-[11px] sm:text-xs text-slate-400 mt-0.5">
            نماذج تقييمات حقيقية موثقة من أعضاء حقيقيين يتم تدويرها وتحويلها تلقائياً.
          </p>
        </div>
        <div className="px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold flex items-center gap-1.5 self-start sm:self-auto">
          <ShieldCheck className="w-4 h-4 flex-shrink-0" />
          <span>البنك المركزي نشط 24/7</span>
        </div>
      </div>

      {/* Info Banner */}
      <div className="bg-emerald-950/20 border border-emerald-500/20 rounded-2xl p-3.5 sm:p-4 flex items-center gap-3 text-xs text-slate-300">
        <Sparkles className="w-5 h-5 text-emerald-400 flex-shrink-0" />
        <p className="leading-relaxed text-[11px] sm:text-xs">
          <strong className="text-white">نظام التدوير الآمن:</strong> جميع الرسائل يتم تحويلها كـ Forward طبيعي مع أسماء وصور بروفايل الأعضاء الحقيقيين لإعطاء أقصى مصداقية لقناتك.
        </p>
      </div>

      {/* Category Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
        {categories.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setCategoryFilter(cat.id)}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap transition-all ${
              categoryFilter === cat.id
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="p-12 text-center text-slate-400">جاري تحميل الرسائل...</div>
      ) : messages.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 sm:p-12 text-center">
          <Layers className="w-10 sm:w-12 h-10 sm:h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-sm sm:text-base font-bold text-white mb-1">بنك التقييمات جاهز</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            يقوم البوت باختيار الرسائل وتدويرها تلقائياً عند تحقيق أهداف الصفقات.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5 sm:gap-5">
          {messages.map((m) => (
            <div key={m.id} className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-4 sm:p-5 transition-all shadow-md flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between gap-2 mb-3">
                  <span className="text-[10px] sm:text-[11px] font-bold px-2.5 py-0.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                    {m.category || 'تقييم'}
                  </span>
                  <span className="text-[10px] text-emerald-400 font-bold px-2 py-0.5 rounded-full bg-emerald-950/60 border border-emerald-500/30 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3 flex-shrink-0" />
                    <span>موثق</span>
                  </span>
                </div>

                <h3 className="text-xs sm:text-sm font-bold text-white mb-2 line-clamp-1">{m.title}</h3>

                <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 mb-3 relative">
                  <Quote className="w-3.5 h-3.5 text-slate-600 absolute left-2 top-2" />
                  <p className="text-xs text-slate-300 line-clamp-3 leading-relaxed">
                    {m.text_preview || 'رسالة تقييم أرباح وتحويل من عضو حقيقي في القناة.'}
                  </p>
                </div>
              </div>

              <div className="pt-2.5 border-t border-slate-800 flex items-center justify-between text-[10px] sm:text-[11px] text-slate-400 font-mono">
                <span>المعرف: #{m.source_message_id}</span>
                <span className="text-emerald-400 font-bold">جاهز للإرسال</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
