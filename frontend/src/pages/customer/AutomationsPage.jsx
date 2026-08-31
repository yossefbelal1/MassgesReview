import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { 
  Workflow, Plus, Play, Pause, Trash2, Clock, Sparkles, 
  CheckCircle2, Edit3, X, Radio, ArrowUpRight, Zap, AlertCircle
} from 'lucide-react';

export const formatDelayArabic = (seconds) => {
  const s = parseFloat(seconds) || 0;
  if (s >= 60 && s % 60 === 0) {
    const mins = Math.floor(s / 60);
    return mins === 1 ? '1 دقيقة' : mins === 2 ? '2 دقيقة' : `${mins} دقيقة`;
  }
  return `${s} ث`;
};

export default function AutomationsPage({ onNavigate }) {
  const [automations, setAutomations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);

  // Edit Modal State
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingAuto, setEditingAuto] = useState(null);
  const [editName, setEditName] = useState('');
  const [editTriggerValue, setEditTriggerValue] = useState('');
  const [editTriggerType, setEditTriggerType] = useState('contains');
  const [editReviewsCount, setEditReviewsCount] = useState(2);
  const [editInitialDelayValue, setEditInitialDelayValue] = useState(5);
  const [editInitialDelayUnit, setEditInitialDelayUnit] = useState('seconds'); // 'seconds' | 'minutes'
  const [editDelayValue, setEditDelayValue] = useState(4);
  const [editDelayUnit, setEditDelayUnit] = useState('seconds'); // 'seconds' | 'minutes'
  const [savingEdit, setSavingEdit] = useState(false);

  useEffect(() => {
    fetchAutomations();
  }, []);

  useEffect(() => {
    if (editModalOpen) {
      document.body.classList.add('modal-open');
    } else {
      document.body.classList.remove('modal-open');
    }
    return () => {
      document.body.classList.remove('modal-open');
    };
  }, [editModalOpen]);

  const fetchAutomations = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/automations/');
      setAutomations(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (id) => {
    try {
      await apiClient.patch(`/automations/${id}/toggle`);
      fetchAutomations();
    } catch (err) {
      alert('فشل تغيير الحالة');
    }
  };

  const handleRunNow = async (id) => {
    try {
      setActionLoading(id);
      const res = await apiClient.post(`/automations/${id}/run-now`);
      alert(res.data.message || 'تم إرسال ونشر تسلسل التقييمات بنجاح!');
      fetchAutomations();
    } catch (err) {
      alert(err.response?.data?.detail || 'فشل تشغيل الأتمتة');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('هل أنت متأكد من رغبتك في حذف هذا الهدف؟')) return;
    try {
      await apiClient.delete(`/automations/${id}`);
      fetchAutomations();
    } catch (err) {
      alert('فشل حذف الهدف');
    }
  };

  const openEditModal = (auto) => {
    setEditingAuto(auto);
    setEditName(auto.name);
    setEditTriggerValue(auto.trigger_value);
    setEditTriggerType(auto.trigger_type || 'contains');
    setEditReviewsCount(auto.reviews_count || 2);
    
    const initSec = auto.initial_delay_seconds || 5;
    if (initSec >= 60 && initSec % 60 === 0) {
      setEditInitialDelayValue(initSec / 60);
      setEditInitialDelayUnit('minutes');
    } else {
      setEditInitialDelayValue(initSec);
      setEditInitialDelayUnit('seconds');
    }

    const delSec = auto.delay_seconds || 4;
    if (delSec >= 60 && delSec % 60 === 0) {
      setEditDelayValue(delSec / 60);
      setEditDelayUnit('minutes');
    } else {
      setEditDelayValue(delSec);
      setEditDelayUnit('seconds');
    }

    setEditModalOpen(true);
  };

  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!editingAuto || !editTriggerValue.trim()) return;

    const calculatedInitialDelay = editInitialDelayUnit === 'minutes' 
      ? (parseFloat(editInitialDelayValue) || 1) * 60 
      : (parseFloat(editInitialDelayValue) || 5.0);

    const calculatedDelay = editDelayUnit === 'minutes' 
      ? (parseFloat(editDelayValue) || 1) * 60 
      : (parseFloat(editDelayValue) || 4.0);

    try {
      setSavingEdit(true);
      await apiClient.put(`/automations/${editingAuto.id}`, {
        name: editName.trim() || editingAuto.name,
        trigger_value: editTriggerValue.trim(),
        trigger_type: editTriggerType,
        reviews_count: parseInt(editReviewsCount) || 2,
        initial_delay_seconds: calculatedInitialDelay,
        delay_seconds: calculatedDelay
      });
      setEditModalOpen(false);
      fetchAutomations();
    } catch (err) {
      alert(err.response?.data?.detail || 'فشل تحديث الهدف');
    } finally {
      setSavingEdit(false);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4">
        <div>
          <h1 className="text-lg sm:text-xl font-bold text-white tracking-tight">الكلمات المفتاحية والأهداف (Automations)</h1>
          <p className="text-[11px] sm:text-xs text-slate-400 mt-0.5">راقب إشارات القناة مثل TP1 / TP2 / أرباحكم ونفذ النشر التلقائي.</p>
        </div>

        <button
          onClick={() => onNavigate('create_automation')}
          className="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white text-xs font-bold shadow-lg shadow-emerald-950 transition-all flex items-center justify-center gap-2 self-stretch sm:self-auto"
        >
          <Plus className="w-4 h-4 flex-shrink-0" />
          <span>إضافة هدف جديد</span>
        </button>
      </div>

      {/* Automations List */}
      {loading ? (
        <div className="p-12 text-center text-slate-400">جاري تحميل الأتمتات...</div>
      ) : automations.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 sm:p-12 text-center">
          <Workflow className="w-10 sm:w-12 h-10 sm:h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-sm sm:text-base font-bold text-white mb-1">لا توجد كلمات مفتاحية مراقبة حالياً</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto mb-6">
            أنشئ أول هدف لمراقبة الكلمات المنشورة في قناتك وإرسال ريفيوهات تلقائياً.
          </p>
          <button
            onClick={() => onNavigate('create_automation')}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all inline-flex items-center justify-center gap-2"
          >
            <Plus className="w-4 h-4" />
            <span>إنشاء أول أتمتة الآن</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {automations.map((auto) => (
            <div
              key={auto.id}
              className={`bg-slate-900 border rounded-2xl p-4 sm:p-5 transition-all shadow-md flex flex-col justify-between ${
                auto.is_active ? 'border-slate-800 hover:border-slate-700' : 'border-slate-800/40 opacity-75'
              }`}
            >
              <div>
                {/* Top Row: Title & Active Toggle */}
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="overflow-hidden">
                    <h3 className="text-sm font-bold text-white truncate">{auto.name}</h3>
                    <div className="flex items-center gap-1.5 mt-1">
                      <Radio className="w-3 h-3 text-emerald-400 flex-shrink-0" />
                      <span className="text-[11px] text-slate-400 truncate">
                        {auto.channel?.title || 'قناة غير محددة'}
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={() => handleToggle(auto.id)}
                    className={`px-2.5 py-1 rounded-full text-[10px] font-bold border transition-colors flex items-center gap-1 flex-shrink-0 ${
                      auto.is_active
                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                        : 'bg-slate-800 border-slate-700 text-slate-400'
                    }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${auto.is_active ? 'bg-emerald-400' : 'bg-slate-500'}`} />
                    <span>{auto.is_active ? 'نشط' : 'معطل'}</span>
                  </button>
                </div>

                {/* Trigger Keyword Badge */}
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2 overflow-hidden">
                    <span className="text-xs text-slate-400 flex-shrink-0">يراقب:</span>
                    <span className="px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono font-bold text-xs truncate">
                      {auto.trigger_value}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-500 uppercase font-semibold">
                    {auto.trigger_type === 'contains' ? 'تتضمن' : auto.trigger_type}
                  </span>
                </div>

                {/* Timing Config Summary */}
                <div className="grid grid-cols-3 gap-2 text-center text-xs mb-3">
                  <div className="p-2 rounded-lg bg-slate-950/40 border border-slate-800/60">
                    <span className="text-[10px] text-slate-400 block">العدد</span>
                    <strong className="text-white text-xs">{auto.reviews_count || 2} رسائل</strong>
                  </div>
                  <div className="p-2 rounded-lg bg-slate-950/40 border border-slate-800/60">
                    <span className="text-[10px] text-slate-400 block">بدء الإرسال</span>
                    <strong className="text-white text-xs">{formatDelayArabic(auto.initial_delay_seconds || 5)}</strong>
                  </div>
                  <div className="p-2 rounded-lg bg-slate-950/40 border border-slate-800/60">
                    <span className="text-[10px] text-slate-400 block">الفواصل</span>
                    <strong className="text-white text-xs">{formatDelayArabic(auto.delay_seconds || 4)}</strong>
                  </div>
                </div>
              </div>

              {/* Action Buttons Row */}
              <div className="pt-3 border-t border-slate-800 flex items-center justify-between gap-2">
                <button
                  onClick={() => handleRunNow(auto.id)}
                  disabled={actionLoading === auto.id || !auto.is_active}
                  className="flex-1 py-2 px-3 rounded-xl bg-emerald-600/10 hover:bg-emerald-600/20 active:scale-95 border border-emerald-500/20 text-emerald-400 disabled:opacity-40 text-xs font-bold transition-all flex items-center justify-center gap-1.5"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>{actionLoading === auto.id ? 'جاري الإرسال...' : 'تجربة فورية 🚀'}</span>
                </button>

                <button
                  onClick={() => openEditModal(auto)}
                  className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
                  title="تعديل الأتمتة"
                  aria-label="تعديل"
                >
                  <Edit3 className="w-4 h-4" />
                </button>

                <button
                  onClick={() => handleDelete(auto.id)}
                  className="p-2 rounded-xl bg-slate-800 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 text-xs font-medium transition-colors"
                  title="حذف الأتمتة"
                  aria-label="حذف"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit Automation Modal */}
      {editModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4" dir="rtl">
          <div className="bg-slate-900 border-t sm:border border-slate-800 rounded-t-3xl sm:rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl p-4 sm:p-6 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Edit3 className="w-4 h-4 text-emerald-400" />
                <span>تعديل الهدف والكلمة المفتاحية</span>
              </h3>
              <button
                onClick={() => setEditModalOpen(false)}
                className="w-8 h-8 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveEdit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  اسم الهدف
                </label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-sm outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  الكلمة المفتاحية المراقبة
                </label>
                <input
                  type="text"
                  value={editTriggerValue}
                  onChange={(e) => setEditTriggerValue(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-emerald-400 font-mono text-sm outline-none"
                  required
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    عدد الرسائل
                  </label>
                  <select
                    value={editReviewsCount}
                    onChange={(e) => setEditReviewsCount(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs outline-none"
                  >
                    <option value="1">1 رسالة</option>
                    <option value="2">2 رسائل</option>
                    <option value="3">3 رسائل</option>
                    <option value="4">4 رسائل</option>
                    <option value="5">5 رسائل</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    بدء الإرسال
                  </label>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      inputMode="numeric"
                      min="1"
                      max={editInitialDelayUnit === 'minutes' ? 60 : 3600}
                      value={editInitialDelayValue}
                      onChange={(e) => setEditInitialDelayValue(e.target.value)}
                      className="w-full px-2.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs outline-none font-mono"
                    />
                    <select
                      value={editInitialDelayUnit}
                      onChange={(e) => setEditInitialDelayUnit(e.target.value)}
                      className="px-2 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-300 text-[11px] font-bold outline-none cursor-pointer"
                    >
                      <option value="seconds">ثواني</option>
                      <option value="minutes">دقائق</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    الفواصل
                  </label>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      inputMode="numeric"
                      min="1"
                      max={editDelayUnit === 'minutes' ? 60 : 600}
                      value={editDelayValue}
                      onChange={(e) => setEditDelayValue(e.target.value)}
                      className="w-full px-2.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs outline-none font-mono"
                    />
                    <select
                      value={editDelayUnit}
                      onChange={(e) => setEditDelayUnit(e.target.value)}
                      className="px-2 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-300 text-[11px] font-bold outline-none cursor-pointer"
                    >
                      <option value="seconds">ثواني</option>
                      <option value="minutes">دقائق</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setEditModalOpen(false)}
                  className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={savingEdit}
                  className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold shadow-lg transition-all"
                >
                  {savingEdit ? 'جاري الحفظ...' : 'حفظ التعديلات'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
