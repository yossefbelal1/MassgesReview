import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { CreditCard, Check, ShieldCheck, Zap, Sparkles, Tag, Flame, Crown } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const DEFAULT_PLANS = [
  {
    id: 'starter',
    slug: 'starter',
    name: 'الباقة الأساسية (Starter)',
    price_monthly: 20.0,
    original_price: null,
    discount_badge: null,
    tag: 'باقة البداية الفردية',
    max_channels: 1,
    max_automations: 5,
    features: [
      'ربط قناة تيليجرام واحدة (1)',
      'حتى 5 أهداف وكلمات مفتاحية',
      'فواصل زمنية عشوائية ذكية',
      'نشر تفاعل موثوق 24/7',
      'تشغيل سحابي آمن وسريع'
    ]
  },
  {
    id: 'pro',
    slug: 'pro',
    name: 'الباقة الاحترافية (Pro)',
    price_monthly: 40.0,
    original_price: 60.0,
    discount_badge: 'وفر 33% (خصم $20 شهرياً)',
    tag: 'الأكثر طلباً وشعبية 🔥',
    popular: true,
    max_channels: 3,
    max_automations: 15,
    features: [
      'ربط 3 قنوات تيليجرام كاملة',
      'حتى 15 هدف وكلمة مفتاحية',
      'فواصل زمنية عشوائية ذكية',
      'أولوية النشر الفوري 24/7',
      'توفير $20 شهرياً ($13.3 للقناة)'
    ]
  },
  {
    id: 'vip',
    slug: 'vip',
    name: 'باقة النخبة (VIP)',
    price_monthly: 100.0,
    original_price: 200.0,
    discount_badge: 'وفر 50% نصف السعر (خصم $100 شهرياً)',
    tag: 'أفضل قيمة لأصحاب القنوات 💎',
    vip: true,
    max_channels: 10,
    max_automations: 50,
    features: [
      'ربط 10 قنوات تيليجرام كاملة',
      'حتى 50 هدف وكلمة مفتاحية',
      'فواصل زمنية عشوائية ذكية',
      'أعلى أولوية معالجة 24/7',
      'دعم فني VIP مخصص وسريع',
      'توفير $100 شهرياً ($10 فقط للقناة)'
    ]
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
        // Merge API data with rich marketing attributes (original price, badges)
        const enriched = res.data.map(p => {
          const fallback = DEFAULT_PLANS.find(df => df.slug === p.slug) || {};
          return {
            ...fallback,
            ...p,
            features: p.features && p.features.length > 0 ? p.features : fallback.features
          };
        });
        const sorted = [...enriched].sort((a, b) => a.price_monthly - b.price_monthly);
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
        <p className="text-xs text-slate-400 mt-1">تفاصيل الخطة المفعلة، عدد القنوات المسموحة، وباقات الاشتراك مع الخصومات الحصرية.</p>
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
              <span className="text-xs text-slate-400 block mb-1">حالة المحرك:</span>
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
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-base font-bold text-white">باقات الاشتراك المتاحة</h2>
          <span className="text-xs text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-3 py-1 rounded-full font-semibold">
            ✨ خصومات تصل إلى 50% على الباقات المتعددة
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans.map((p) => {
            const isCurrent = sub?.plan_name ? sub.plan_name.toLowerCase().includes(p.slug || '') || p.name.includes(sub.plan_name) : false;
            return (
              <div
                key={p.id || p.slug}
                className={`bg-slate-900 border rounded-2xl p-6 flex flex-col justify-between transition-all relative ${
                  isCurrent
                    ? 'border-emerald-500 shadow-xl shadow-emerald-950/50 ring-2 ring-emerald-500'
                    : p.popular
                    ? 'border-emerald-500/50 shadow-lg shadow-emerald-950/20 hover:border-emerald-400'
                    : p.vip
                    ? 'border-amber-500/50 shadow-lg shadow-amber-950/20 hover:border-amber-400'
                    : 'border-slate-800 hover:border-slate-700'
                }`}
              >
                {/* Top Badge */}
                {isCurrent ? (
                  <div className="absolute -top-3 right-6 bg-emerald-500 text-slate-950 text-[10px] font-extrabold px-3 py-0.5 rounded-full uppercase tracking-wider shadow">
                    باقتك المفعلة حالياً
                  </div>
                ) : p.popular ? (
                  <div className="absolute -top-3 right-6 bg-gradient-to-r from-emerald-500 to-teal-500 text-slate-950 text-[10px] font-extrabold px-3 py-0.5 rounded-full uppercase tracking-wider shadow flex items-center gap-1">
                    <Flame className="w-3 h-3" /> الأكثر طلباً
                  </div>
                ) : p.vip ? (
                  <div className="absolute -top-3 right-6 bg-gradient-to-r from-amber-500 to-orange-500 text-slate-950 text-[10px] font-extrabold px-3 py-0.5 rounded-full uppercase tracking-wider shadow flex items-center gap-1">
                    <Crown className="w-3 h-3" /> أعلى توفير 50%
                  </div>
                ) : null}

                <div>
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <h3 className="text-base font-bold text-white">{p.name}</h3>
                  </div>

                  {p.tag && (
                    <span className="text-[11px] text-slate-400 font-medium block mb-2">{p.tag}</span>
                  )}

                  {/* Pricing Box with Strikethrough & Discount */}
                  <div className="my-4 p-3.5 rounded-xl bg-slate-950/80 border border-slate-800/80">
                    <div className="flex items-baseline gap-2">
                      <span className="text-3xl font-extrabold text-white">${p.price_monthly || p.price || 0}</span>
                      <span className="text-xs text-slate-400">/ شهرياً</span>
                      
                      {p.original_price && (
                        <span className="text-sm text-slate-500 line-through font-semibold mr-auto">
                          ${p.original_price}
                        </span>
                      )}
                    </div>

                    {p.discount_badge && (
                      <div className="mt-2 inline-flex items-center gap-1 text-[11px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-md">
                        <Tag className="w-3 h-3" />
                        <span>{p.discount_badge}</span>
                      </div>
                    )}
                  </div>

                  {/* Channel Count Highlight Box */}
                  <div className="mb-4 p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/60 flex items-center justify-between text-xs">
                    <span className="text-slate-300 font-medium">عدد القنوات المسموح بها:</span>
                    <span className="font-bold text-emerald-400 px-2 py-0.5 rounded bg-emerald-950 border border-emerald-800/80">
                      {p.max_channels} {p.max_channels === 1 ? 'قناة واحدة' : 'قنوات'}
                    </span>
                  </div>

                  <ul className="space-y-2.5 text-xs text-slate-300 mb-6">
                    {p.features?.map((feat, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <Check className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                        <span>{feat}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <button
                  disabled={isCurrent}
                  onClick={() => window.open(`https://t.me/tamerads1?text=${encodeURIComponent(`مرحباً، أود ترقية اشتراكي إلى ${p.name} ($${p.price_monthly}/شهرياً) لربط ${p.max_channels} قنوات في منصة ReviewFlow`)}`, '_blank')}
                  className={`w-full py-2.5 rounded-xl text-xs font-semibold transition-all ${
                    isCurrent
                      ? 'bg-slate-800 text-slate-400 border border-slate-700 cursor-default'
                      : p.vip
                      ? 'bg-amber-600 hover:bg-amber-500 text-white shadow-lg shadow-amber-950 cursor-pointer'
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
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 text-center text-xs text-slate-400 mt-8">
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
