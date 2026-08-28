import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { Workflow, Plus, Play, Pause, Trash2, ArrowRight, Clock, Layers, Sparkles, CheckCircle2, Edit3, X } from 'lucide-react';

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
  const [editInitialDelaySeconds, setEditInitialDelaySeconds] = useState(5);
  const [editDelaySeconds, setEditDelaySeconds] = useState(4);
  const [savingEdit, setSavingEdit] = useState(false);

  useEffect(() => {
    fetchAutomations();
  }, []);

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
    setEditInitialDelaySeconds(auto.initial_delay_seconds || 5);
    setEditDelaySeconds(auto.delay_seconds || 4);
    setEditModalOpen(true);
  };

  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!editingAuto || !editTriggerValue.trim()) return;

    try {
      setSavingEdit(true);
      await apiClient.put(`/automations/${editingAuto.id}`, {
        name: editName.trim() || editingAuto.name,
        trigger_value: editTriggerValue.trim(),
        trigger_type: editTriggerType,
        reviews_count: parseInt(editReviewsCount) || 2,
        initial_delay_seconds: parseFloat(editInitialDelaySeconds) || 5.0,
        delay_seconds: parseFloat(editDelaySeconds) || 4.0
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
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">الكلمات المفتاحية وإعدادات الأهداف</h1>
          <p className="text-xs text-slate-400 mt-1">تحديد كلمات ضرب الهدف (مثل: TP1, TP2)، عدد التقييمات، والفواصل الزمنية العشوائية الذكية.</p>
        </div>
        <button
          onClick={() => onNavigate('create_automation')}
          className="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-950 transition-all flex items-center justify-center gap-2"
        >
          <Plus className="w-4 h-4" />
          <span>إضافة هدف / كلمة جديدة</span>
        </button>
      </div>

      {/* List */}
      {loading ? (
        <div className="p-12 text-center text-slate-400">جاري تحميل الأهداف...</div>
      ) : automations.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center">
          <Workflow className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-bold text-white mb-1">لا توجد أهداف مفعلة حالياً</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto mb-6">
            حدد الكلمة التي تريد مراقبتها في قناتك (مثال: عندما تكتب "TP1" ➔ إرسال 2 ريفيو بفارق 4 ثوانٍ تلقائياً).
          </p>
          <button
            onClick={() => onNavigate('create_automation')}
            className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-all inline-flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            <span>إنشاء أول هدف</span>
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {automations.map((auto) => (
            <div 
              key={auto.id}
              className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-6 transition-all shadow-md"
            >
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-base font-bold text-white">{auto.name}</h3>
                    <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
                      auto.is_active 
                        ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400' 
                        : 'bg-slate-800 border border-slate-700 text-slate-400'
                    }`}>
                      {auto.is_active ? 'مفعل وشغال' : 'متوقف مؤقتاً'}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">القناة: {auto.channel?.title || 'القناة المرتبطة'}</span>
                  </div>

                  {/* Trigger & Config Badges */}
                  <div className="flex flex-wrap items-center gap-2.5 text-xs text-slate-300">
                    <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800">
                      <span className="text-slate-400 text-[11px]">الكلمة المراقبة:</span>
                      <span className="font-mono font-bold text-emerald-400">"{auto.trigger_value}"</span>
                    </div>

                    <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800">
                      <span className="text-slate-400 text-[11px]">عدد الرسائل:</span>
                      <span className="font-bold text-white font-mono">{auto.reviews_count || 2} رسائل</span>
                    </div>

                    <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800">
                      <span className="text-slate-400 text-[11px]">تأخير البدء:</span>
                      <span className="font-bold text-sky-400 font-mono">~{auto.initial_delay_seconds || 5} ثوانٍ</span>
                    </div>

                    <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800">
                      <span className="text-slate-400 text-[11px]">الفواصل بين الرسائل:</span>
                      <span className="font-bold text-amber-400 font-mono">~{auto.delay_seconds || 4} ثوانٍ</span>
                      <span className="text-[10px] text-slate-400">(+ تنويع بشري)</span>
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 self-end lg:self-center">
                  <button
                    onClick={() => openEditModal(auto)}
                    className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors flex items-center gap-1.5"
                    title="تعديل الكلمة والعدد والفواصل"
                  >
                    <Edit3 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>تعديل الإعدادات</span>
                  </button>

                  <button
                    onClick={() => handleRunNow(auto.id)}
                    disabled={actionLoading === auto.id}
                    className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-emerald-400 text-xs font-semibold transition-colors flex items-center gap-1.5"
                    title="اختبار الإرسال الآن فوراً"
                  >
                    <Play className="w-3.5 h-3.5" />
                    <span>تجربة الآن</span>
                  </button>

                  <button
                    onClick={() => handleToggle(auto.id)}
                    className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors flex items-center gap-1.5"
                  >
                    {auto.is_active ? <Pause className="w-3.5 h-3.5 text-amber-400" /> : <Play className="w-3.5 h-3.5 text-emerald-400" />}
                    <span>{auto.is_active ? 'إيقاف مؤقت' : 'تفعيل'}</span>
                  </button>

                  <button
                    onClick={() => handleDelete(auto.id)}
                    className="p-2 rounded-xl text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                    title="حذف الهدف"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Sequence Info */}
              <div className="mt-4 pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>توليد آراء المتداولين: نشط وتلقائي (أعضاء موثوقين ومتنوعين)</span>
                </span>
                <span>إجمالي مرات التنفيذ: <strong className="text-white font-mono">{auto.total_executions || 0}</strong></span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit Trigger Modal */}
      {editModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-150">
            <div className="p-6 border-b border-slate-800 flex items-center justify-between">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Edit3 className="w-4 h-4 text-emerald-400" />
                <span>تعديل إعدادات الهدف والكلمة المفتاحية</span>
              </h3>
              <button onClick={() => setEditModalOpen(false)} className="text-slate-400 hover:text-slate-200">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveEdit} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">اسم الهدف / التسمية</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-sm outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  الكلمة المفتاحية المراقبة (مثال: TP1 أو الهدف الأول أو GOLD TP)
                </label>
                <input
                  type="text"
                  value={editTriggerValue}
                  onChange={(e) => setEditTriggerValue(e.target.value)}
                  placeholder="مثال: TP1 أو 🎯 الهدف الأول"
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-emerald-400 font-mono text-sm outline-none"
                  required
                />
                <p className="text-[11px] text-slate-400 mt-1">بمجرد نشر هذه الكلمة في قناتك، سيبدأ البوت بنشر التقييمات تلقائياً.</p>
              </div>

              {/* Reviews Count & Delay Configuration */}
              <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-white mb-1.5">
                      عدد الرسائل
                    </label>
                    <select
                      value={editReviewsCount}
                      onChange={(e) => setEditReviewsCount(e.target.value)}
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
                      تأخير البدء
                    </label>
                    <div className="flex items-center gap-1.5">
                      <input
                        type="number"
                        min="0"
                        max="300"
                        value={editInitialDelaySeconds}
                        onChange={(e) => setEditInitialDelaySeconds(e.target.value)}
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
                        value={editDelaySeconds}
                        onChange={(e) => setEditDelaySeconds(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 focus:border-emerald-500 text-amber-400 font-bold text-xs outline-none font-mono"
                        required
                      />
                      <span className="text-xs text-slate-400 font-medium">ثوانٍ</span>
                    </div>
                  </div>
                </div>

                <div className="pt-1 text-[11px] text-slate-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                  <span><strong>تأخير البدء:</strong> الوقت الذي ينتظره البوت بعد رصد الكلمة قبل إرسال أول ريفيو، ثم يرسل باقي الريفيوهات بالفواصل المحددة.</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">طريقة المطابقة</label>
                <select
                  value={editTriggerType}
                  onChange={(e) => setEditTriggerType(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-xs outline-none"
                >
                  <option value="contains">تحتوي الكلمة في أي مكان بالرسالة (الأفضل والموصى به)</option>
                  <option value="exact">مطابقة تامة للنص بالكامل فقط</option>
                  <option value="prefix">تبدأ الرسالة بالكلمة</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setEditModalOpen(false)}
                  className="px-4 py-2.5 rounded-xl bg-slate-800 text-slate-300 text-xs font-semibold"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={savingEdit}
                  className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-950 flex items-center gap-1.5"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>{savingEdit ? 'جاري الحفظ...' : 'حفظ التعديل الآن'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

