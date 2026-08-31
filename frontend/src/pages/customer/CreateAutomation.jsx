import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { Workflow, Plus, ArrowRight, Clock, Sparkles, CheckCircle2, CheckSquare, Square, Radio } from 'lucide-react';

export default function CreateAutomation({ onNavigate }) {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Form Fields
  const [name, setName] = useState('');
  const [selectedChannelIds, setSelectedChannelIds] = useState([]);
  const [triggerValue, setTriggerValue] = useState('');
  const [triggerType, setTriggerType] = useState('contains');
  const [reviewsCount, setReviewsCount] = useState(2);
  const [initialDelayValue, setInitialDelayValue] = useState(5);
  const [initialDelayUnit, setInitialDelayUnit] = useState('seconds'); // 'seconds' | 'minutes'
  const [delayValue, setDelayValue] = useState(4);
  const [delayUnit, setDelayUnit] = useState('seconds'); // 'seconds' | 'minutes'

  useEffect(() => {
    fetchChannels();
  }, []);

  const fetchChannels = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/channels/');
      setChannels(res.data);
      if (res.data.length > 0) {
        setSelectedChannelIds(res.data.map(c => c.id));
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const toggleChannel = (id) => {
    if (selectedChannelIds.includes(id)) {
      setSelectedChannelIds(selectedChannelIds.filter(cid => cid !== id));
    } else {
      setSelectedChannelIds([...selectedChannelIds, id]);
    }
  };

  const selectAllChannels = () => {
    if (selectedChannelIds.length === channels.length) {
      setSelectedChannelIds([]);
    } else {
      setSelectedChannelIds(channels.map(c => c.id));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || selectedChannelIds.length === 0 || !triggerValue.trim()) {
      alert('يرجى ملء جميع الحقول وتحديد قناة واحدة على الأقل');
      return;
    }

    const calculatedInitialDelay = initialDelayUnit === 'minutes' 
      ? (parseFloat(initialDelayValue) || 1) * 60 
      : (parseFloat(initialDelayValue) || 5.0);

    const calculatedDelay = delayUnit === 'minutes' 
      ? (parseFloat(delayValue) || 1) * 60 
      : (parseFloat(delayValue) || 4.0);

    try {
      setSubmitting(true);
      await apiClient.post('/automations/', {
        name: name.trim(),
        channel_ids: selectedChannelIds,
        trigger_type: triggerType,
        trigger_value: triggerValue.trim(),
        reviews_count: parseInt(reviewsCount) || 2,
        initial_delay_seconds: calculatedInitialDelay,
        delay_seconds: calculatedDelay,
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
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-400 gap-3">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500"></div>
        <span className="text-xs sm:text-sm font-medium">جاري التحميل...</span>
      </div>
    );
  }

  if (channels.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-12 text-center max-w-lg mx-auto" dir="rtl">
        <h3 className="text-base font-bold text-white mb-2">يرجى ربط قناة تيليجرام أولاً</h3>
        <p className="text-xs text-slate-400 mb-6 leading-relaxed">تحتاج إلى ربط قناة واحدة على الأقل قبل إنشاء كلمة مراقبة أو هدف جديد.</p>
        <button
          onClick={() => onNavigate('channels')}
          className="w-full sm:w-auto px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:scale-98 text-white text-xs font-bold transition-all min-h-[44px]"
        >
          الانتقال لصفحة قنواتي
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6 max-w-2xl mx-auto" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div>
          <h1 className="text-lg sm:text-xl font-bold text-white tracking-tight">إضافة هدف / كلمة مفتاحية جديدة</h1>
          <p className="text-[11px] sm:text-xs text-slate-400 mt-0.5">حدد الكلمة المراقبة وخصص القنوات المستهدفة.</p>
        </div>
        <button
          onClick={() => onNavigate('automations')}
          className="text-xs font-bold text-slate-400 hover:text-white transition-colors px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 flex-shrink-0 min-h-[40px] flex items-center"
        >
          رجوع للقائمة
        </button>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-8 space-y-4 sm:space-y-6 shadow-xl">
        {/* Basic Info */}
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              اسم الهدف / الاستراتيجية <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              placeholder="مثال: 🎯 الهدف الأول TP1 أو صفقة الذهب أو شاركونا"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-sm outline-none transition-colors min-h-[44px]"
              required
            />
          </div>

          {/* MULTI-CHANNEL SELECTOR */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-xs font-semibold text-slate-300">
                القنوات المستهدفة <span className="text-rose-400">*</span>
              </label>
              <button
                type="button"
                onClick={selectAllChannels}
                className="text-xs text-emerald-400 hover:text-emerald-300 font-bold transition-colors py-1 px-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20"
              >
                {selectedChannelIds.length === channels.length ? 'إلغاء تحديد الكل' : `تحديد جميع القنوات (${channels.length})`}
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-h-56 overflow-y-auto p-1">
              {channels.map((ch) => {
                const isSelected = selectedChannelIds.includes(ch.id);
                return (
                  <div
                    key={ch.id}
                    onClick={() => toggleChannel(ch.id)}
                    className={`p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between min-h-[48px] active:scale-[0.98] ${
                      isSelected
                        ? 'bg-emerald-950/40 border-emerald-500/50 text-white shadow-sm'
                        : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 overflow-hidden">
                      <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 ${isSelected ? 'text-emerald-400' : 'text-slate-600'}`}>
                        {isSelected ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
                      </div>
                      <div className="overflow-hidden">
                        <h4 className="text-xs font-bold truncate">{ch.title}</h4>
                        <p className="text-[10px] text-slate-400 font-mono truncate">{ch.username ? `@${ch.username}` : ch.telegram_chat_id}</p>
                      </div>
                    </div>
                    {isSelected && (
                      <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded font-semibold whitespace-nowrap mr-2">
                        محددة
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="text-[11px] text-slate-400 mt-1.5">
              تم تحديد <strong className="text-emerald-400">{selectedChannelIds.length}</strong> من إجمالي <strong>{channels.length}</strong> قنوات.
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              الكلمة المفتاحية المراقبة في قناتك <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              placeholder="مثال: TP1 أو أرباحكم أو شاركونا أو الهدف الأول"
              value={triggerValue}
              onChange={(e) => setTriggerValue(e.target.value)}
              className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-emerald-400 font-mono text-sm outline-none transition-colors min-h-[44px]"
              required
            />
            <p className="text-[11px] text-slate-400 mt-1.5 leading-relaxed">
              💡 <strong>مطابقة ذكية:</strong> يتعرف النظام تلقائياً على الهمزات والتاء المربوطة والأشكال المختلفة (أرباحكم / ارباحكم / رايكم / رأيكم) وجميع الكلمات الإنجليزية والعربية دون حساسية للحروف.
            </p>
          </div>

          {/* Configuration Box */}
          <div className="p-3.5 sm:p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3.5">
            <h4 className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 flex-shrink-0" />
              <span>إعدادات التفاعل والتوقيتات الذكية</span>
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-semibold text-white mb-1.5">
                  عدد الريفيوهات
                </label>
                <select
                  value={reviewsCount}
                  onChange={(e) => setReviewsCount(e.target.value)}
                  className="w-full px-3 py-3 rounded-xl bg-slate-900 border border-slate-700 focus:border-emerald-500 text-emerald-400 font-bold text-xs outline-none min-h-[44px]"
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
                    inputMode="numeric"
                    min="1"
                    max={initialDelayUnit === 'minutes' ? 60 : 3600}
                    value={initialDelayValue}
                    onChange={(e) => setInitialDelayValue(e.target.value)}
                    className="w-full px-3 py-3 rounded-xl bg-slate-900 border border-slate-700 focus:border-emerald-500 text-white text-xs font-mono outline-none min-h-[44px]"
                  />
                  <select
                    value={initialDelayUnit}
                    onChange={(e) => setInitialDelayUnit(e.target.value)}
                    className="px-3 py-3 rounded-xl bg-slate-900 border border-slate-700 focus:border-emerald-500 text-slate-200 text-xs font-bold outline-none min-h-[44px] cursor-pointer"
                  >
                    <option value="seconds">ثواني</option>
                    <option value="minutes">دقائق</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-white mb-1.5">
                  الفارق بين الرسائل
                </label>
                <div className="flex items-center gap-1.5">
                  <input
                    type="number"
                    inputMode="numeric"
                    min="1"
                    max={delayUnit === 'minutes' ? 60 : 600}
                    value={delayValue}
                    onChange={(e) => setDelayValue(e.target.value)}
                    className="w-full px-3 py-3 rounded-xl bg-slate-900 border border-slate-700 focus:border-emerald-500 text-white text-xs font-mono outline-none min-h-[44px]"
                  />
                  <select
                    value={delayUnit}
                    onChange={(e) => setDelayUnit(e.target.value)}
                    className="px-3 py-3 rounded-xl bg-slate-900 border border-slate-700 focus:border-emerald-500 text-slate-200 text-xs font-bold outline-none min-h-[44px] cursor-pointer"
                  >
                    <option value="seconds">ثواني</option>
                    <option value="minutes">دقائق</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2.5 pt-4 border-t border-slate-800">
          <button
            type="button"
            onClick={() => onNavigate('automations')}
            className="w-full sm:w-auto px-5 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors min-h-[44px]"
          >
            إلغاء
          </button>
          <button
            type="submit"
            disabled={submitting || selectedChannelIds.length === 0}
            className="w-full sm:w-auto px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:scale-98 disabled:opacity-50 text-white text-xs font-bold shadow-lg shadow-emerald-950 transition-all flex items-center justify-center gap-2 min-h-[44px]"
          >
            <Plus className="w-4 h-4 flex-shrink-0" />
            <span>{submitting ? 'جاري الإنشاء والربط...' : `حفظ الأتمتة (${selectedChannelIds.length} قنوات) 🚀`}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
