import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { Workflow, Plus, ArrowRight, Clock, Sparkles, CheckCircle2 } from 'lucide-react';

export default function CreateAutomation({ onNavigate }) {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Form Fields
  const [name, setName] = useState('');
  const [channelId, setChannelId] = useState('');
  const [triggerValue, setTriggerValue] = useState('');
  const [triggerType, setTriggerType] = useState('contains');
  const [reviewsCount, setReviewsCount] = useState(2);
  const [initialDelaySeconds, setInitialDelaySeconds] = useState(5);
  const [delaySeconds, setDelaySeconds] = useState(4);

  useEffect(() => {
    fetchChannels();
  }, []);

  const fetchChannels = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/channels/');
      setChannels(res.data);
      if (res.data.length > 0) {
        setChannelId(res.data[0].id);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !channelId || !triggerValue.trim()) {
      alert('يرجى ملء جميع الحقول المطلوبة');
      return;
    }

    try {
      setSubmitting(true);
      await apiClient.post('/automations/', {
        name: name.trim(),
        channel_id: channelId,
        trigger_type: triggerType,
        trigger_value: triggerValue.trim(),
        reviews_count: parseInt(reviewsCount) || 2,
        initial_delay_seconds: parseFloat(initialDelaySeconds) || 5.0,
        delay_seconds: parseFloat(delaySeconds) || 4.0,
        steps: []
      });
      onNavigate('automations');
    } catch (err) {
      alert(err.response?.data?.detail || 'فشل إنشاء الهدف');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="p-12 text-center text-slate-400">جاري التحميل...</div>;
  }

  if (channels.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center max-w-lg mx-auto" dir="rtl">
        <h3 className="text-base font-bold text-white mb-2">يرجى ربط قناة تيليجرام أولاً</h3>
        <p className="text-xs text-slate-400 mb-6">تحتاج إلى ربط قناة واحدة على الأقل قبل إنشاء كلمة مراقبة أو هدف جديد.</p>
        <button
          onClick={() => onNavigate('channels')}
          className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold"
        >
          الانتقال لصفحة قنواتي
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl mx-auto pb-12" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">إضافة هدف / كلمة مفتاحية جديدة</h1>
          <p className="text-xs text-slate-400 mt-1">حدد الكلمة التي ترغب بمراقبتها وعدد التقييمات وتأخير بدء الإرسال والفواصل.</p>
        </div>
        <button
          onClick={() => onNavigate('automations')}
          className="text-xs font-semibold text-slate-400 hover:text-white transition-colors"
        >
          رجوع للقائمة
        </button>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-6 shadow-xl">
        {/* Basic Info */}
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              اسم الهدف / الاستراتيجية <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              placeholder="مثال: 🎯 الهدف الأول TP1 أو صفقة الذهب"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-sm outline-none transition-colors"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              القناة المستهدفة <span className="text-rose-400">*</span>
            </label>
            <select
              value={channelId}
              onChange={(e) => setChannelId(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-xs outline-none"
            >
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  {ch.title} ({ch.username ? `@${ch.username}` : ch.telegram_chat_id})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              الكلمة المفتاحية المراقبة في قناتك <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              placeholder="مثال: TP1 أو الهدف الأول أو 🎯 ضرب الهدف"
              value={triggerValue}
              onChange={(e) => setTriggerValue(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-emerald-400 font-mono text-sm outline-none transition-colors"
              required
            />
            <p className="text-[11px] text-slate-400 mt-1">بمجرد أن تنشر رسالة في قناتك تحتوي على هذه الكلمة، سيتم إرسال التقييمات فوراً.</p>
          </div>

          {/* Configuration Box */}
          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-4">
            <h4 className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" />
              <span>إعدادات التفاعل والتوقيتات الذكية</span>
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-white mb-1.5">
                  عدد الريفيوهات
                </label>
                <select
                  value={reviewsCount}
                  onChange={(e) => setReviewsCount(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 focus:border-emerald-500 text-emerald-400 font-bold text-xs outline-none"
                >
                  <option value="1">1 رسالة واحدة</option>
                  <option value="2">2 رسائل (الموصى به)</option>
                  <option value="3">3 رسائل</option>
                  <option value="4">4 رسائل</option>
                  <option value="5">5 رسائل</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-white mb-1.5">
                  تأخير بدء الإرسال
                </label>
                <div className="flex items-center gap-1.5">
                  <input
                    type="number"
                    min="0"
                    max="300"
                    value={initialDelaySeconds}
                    onChange={(e) => setInitialDelaySeconds(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 focus:border-emerald-500 text-sky-400 font-bold text-xs outline-none font-mono"
                    required
                  />
                  <span className="text-xs text-slate-400 font-medium">ثوانٍ</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-white mb-1.5">
                  الفواصل بين الرسائل
                </label>
                <div className="flex items-center gap-1.5">
                  <input
                    type="number"
                    min="1"
                    max="60"
                    value={delaySeconds}
                    onChange={(e) => setDelaySeconds(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 focus:border-emerald-500 text-amber-400 font-bold text-xs outline-none font-mono"
                    required
                  />
                  <span className="text-xs text-slate-400 font-medium">ثوانٍ</span>
                </div>
              </div>
            </div>

            <p className="text-[11px] text-slate-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              <span><strong>تأخير البدء:</strong> الوقت الذي ينتظره البوت بعد نشر الإشارة قبل إرسال أول ريفيو ليبدو التفاعل بشرياً وطبيعياً 100%.</span>
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">طريقة المطابقة</label>
            <select
              value={triggerType}
              onChange={(e) => setTriggerType(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-xs outline-none"
            >
              <option value="contains">تحتوي الكلمة في أي جزء من الرسالة (الموصى به)</option>
              <option value="exact">مطابقة تامة للنص بالكامل فقط</option>
              <option value="prefix">تبدأ الرسالة بالكلمة</option>
            </select>
          </div>
        </div>

        {/* Submit */}
        <div className="pt-4 border-t border-slate-800 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={() => onNavigate('automations')}
            className="px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors"
          >
            إلغاء
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold shadow-lg shadow-emerald-950 transition-all flex items-center gap-2"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>{submitting ? 'جاري الإنشاء والتفعيل...' : 'حفظ وتفعيل الهدف فوراً'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
