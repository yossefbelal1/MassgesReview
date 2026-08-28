import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { CreditCard, Check, ShieldCheck, Zap, Sparkles } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const DEFAULT_PLANS = [
  {
    id: 'starter',
    name: 'الباقة الأساسية (Starter)',
    price_monthly: 20.0,
    max_channels: 1,
    max_automations: 5,
    features: ['1 قناة تيليجرام واحدة', 'حتى 5 أهداف وكلمات مفتاحية', 'فواصل زمنية عشوائية ذكية', 'تشغيل سحابي 24/7']
  },
  {
    id: 'pro',
    name: 'الباقة الاحترافية (Pro)',
    price_monthly: 30.0,
    max_channels: 3,
    max_automations: 15,
    features: ['3 قنوات تيليجرام', 'حتى 15 هدف وكلمة مفتاحية', 'فواصل زمنية عشوائية ذكية', 'أولوية النشر الفوري 24/7']
  },
  {
    id: 'vip',
    name: 'باقة النخبة (VIP)',
    price_monthly: 80.0,
    max_channels: 10,
    max_automations: 50,
    features: ['10 قنوات تيليجرام', 'حتى 50 هدف وكلمة مفتاحية', 'فواصل زمنية عشوائية ذكية', 'دعم فني VIP مخصص 24/7']
  }
];

export default function SubscriptionPage() {
  const { user } = useAuth();
  const [plans, setPlans] = useState(DEFAULT_PLANS);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/admin/plans');
      if (res.data && res.data.length > 0) {
        const sorted = [...res.data].sort((a, b) => a.price_monthly - b.price_monthly);
        setPlans(sorted);
      }
    } catch (err) {
      console.error('Error fetching plans, using defaults:', err);
    } finally {
      setLoading(false);
    }
  };

  const sub = user?.subscription;

  return (
    <div className="space-y-8 max-w-5xl mx-auto" dir="rtl">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-white tracking-tight">باقتي والاشتراك</h1>
        <p className="text-xs text-slate-400 mt-1">تفاصيل الخطة المفعلة، عدد القنوات المسموحة، وتاريخ تجديد الاشتراك.</p>
      </div>

      {/* Current Active Plan Status Card */}
      {sub && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 relative overflow-hidden shadow-xl">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">الخطة الحالية النشطة</span>
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-white">{sub.plan_name || 'الباقة الاحترافية (Pro)'}</h2>
                <span className="px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
                  {sub.status === 'active' ? 'اشتراك نشط' : sub.status === 'trial' ? 'فترة تجريبية' : sub.status || 'نشط'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-2">
                تاريخ الانتهاء والتجديد: <strong className="text-slate-200">{sub.expires_at ? new Date(sub.expires_at).toLocaleDateString('ar-EG') : 'تجديد شهري'}</strong> ({sub.days_remaining || 30} يوم متبقي)
              </p>
            </div>

            <div className="text-left">
              <span className="text-xs text-slate-400 block mb-1">حالة الخدمة:</span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-950 border border-slate-800 text-emerald-400 text-xs">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>المحرك يعمل بنجاح 24/7</span>
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Plans Grid */}
      <div>
        <h2 className="text-base font-bold text-white mb-4">باقات الاشتراك المتاحة</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans.map((p) => {
            const isCurrent = sub?.plan_name ? sub.plan_name.toLowerCase().includes(p.slug || '') || p.name.includes(sub.plan_name) : false;
            return (
              <div
                key={p.id}
                className={`bg-slate-900 border rounded-2xl p-6 flex flex-col justify-between transition-all relative ${
                  isCurrent
                    ? 'border-emerald-500 shadow-lg shadow-emerald-950/50 ring-1 ring-emerald-500'
                    : 'border-slate-800 hover:border-slate-700'
                }`}
              >
                {isCurrent && (
                  <div className="absolute -top-3 right-6 bg-emerald-500 text-slate-950 text-[10px] font-extrabold px-3 py-0.5 rounded-full uppercase tracking-wider shadow">
                    باقتك الحالية
                  </div>
                )}

                <div>
                  <h3 className="text-base font-bold text-white mb-1">{p.name}</h3>
                  <div className="flex items-baseline gap-1 my-3">
                    <span className="text-3xl font-extrabold text-white">${p.price_monthly || p.price || 0}</span>
                    <span className="text-xs text-slate-400">/ شهرياً</span>
                  </div>

                  <ul className="space-y-2.5 text-xs text-slate-300 mb-6">
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      <span>حتى <strong>{p.max_channels}</strong> {p.max_channels === 1 ? 'قناة تيليجرام واحدة' : 'قنوات تيليجرام'}</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      <span>حتى <strong>{p.max_automations}</strong> أهداف وكلمات مفتاحية</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      <span>نشر تفاعل وآراء متداولين حقيقيين وموثوقين</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      <span>فواصل زمنية عشوائية ذكية تحاكي التفاعل البشري</span>
                    </li>
                  </ul>
                </div>

                <button
                  disabled={isCurrent}
                  onClick={() => window.open(`https://t.me/tamerads1?text=${encodeURIComponent(`مرحباً، أود ترقية اشتراكي إلى ${p.name} في منصة ReviewFlow`)}`, '_blank')}
                  className={`w-full py-2.5 rounded-xl text-xs font-semibold transition-all ${
                    isCurrent
                      ? 'bg-slate-800 text-slate-400 border border-slate-700 cursor-default'
                      : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-950 cursor-pointer'
                  }`}
                >
                  {isCurrent ? 'الخطة المفعلة حالياً' : `ترقية إلى ${p.name} (تواصل عبر تيليجرام)`}
                </button>
              </div>
            );
          })}
        </div>

        {/* Support & Direct Activation Notice */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 text-center text-xs text-slate-400">
          <p className="text-slate-300 font-semibold mb-1">💳 لتفعيل الاشتراكات وطرق الدفع المتاحة (USDT / التحويل البنكي):</p>
          <p>
            تواصل مباشرة مع إدارة المنصة عبر تيليجرام:{' '}
            <a
              href="https://t.me/tamerads1"
              target="_blank"
              rel="noopener noreferrer"
              className="text-emerald-400 font-bold hover:underline inline-flex items-center gap-1"
            >
              @tamerads1
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
