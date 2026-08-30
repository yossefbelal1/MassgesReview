import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { Sliders, Plus, Check, ShieldCheck } from 'lucide-react';

export default function PlansManager() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/admin/plans');
      setPlans(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6 max-w-5xl mx-auto" dir="rtl">
      <div>
        <h1 className="text-lg sm:text-xl font-bold text-white tracking-tight">إدارة الباقات وحدود الموارد</h1>
        <p className="text-[11px] sm:text-xs text-slate-400 mt-0.5">التحكم في أسعار الباقات وحدود القنوات والأتمتات لكل مشترك.</p>
      </div>

      {loading ? (
        <div className="p-12 text-center text-slate-400">جاري تحميل الباقات...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6">
          {plans.map((p) => (
            <div key={p.id} className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-6 flex flex-col justify-between shadow-lg">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-base font-bold text-white">{p.name}</h3>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-950 text-slate-400">{p.slug}</span>
                </div>

                <div className="text-2xl sm:text-3xl font-extrabold text-white mb-4">
                  ${p.price_monthly} <span className="text-xs text-slate-400 font-normal">/ شهرياً</span>
                </div>

                <ul className="space-y-2 text-xs text-slate-300">
                  <li className="flex items-center justify-between py-1.5 border-b border-slate-800/60">
                    <span className="text-slate-400">الحد الأقصى للقنوات</span>
                    <strong className="text-emerald-400 font-bold">{p.max_channels} قنوات</strong>
                  </li>
                  <li className="flex items-center justify-between py-1.5 border-b border-slate-800/60">
                    <span className="text-slate-400">الحد الأقصى للأتمتات</span>
                    <strong className="text-white font-bold">{p.max_automations} أهداف</strong>
                  </li>
                  <li className="flex items-center justify-between py-1.5 border-b border-slate-800/60">
                    <span className="text-slate-400">بنك الرسائل</span>
                    <strong className="text-white font-bold">{p.max_messages} رسالة</strong>
                  </li>
                  <li className="flex items-center justify-between py-1.5">
                    <span className="text-slate-400">النشر اليومي</span>
                    <strong className="text-emerald-400 font-bold">{p.max_daily_executions} تنفيذ / يوم</strong>
                  </li>
                </ul>
              </div>

              <div className="pt-3.5 mt-5 border-t border-slate-800 text-xs text-emerald-400 font-bold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>الباقة فعالة وجاهزة للاشتراك</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
