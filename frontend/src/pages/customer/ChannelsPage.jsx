import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { 
  Radio, Plus, Trash2, CheckCircle2, AlertTriangle, ShieldCheck, 
  RefreshCw, X, ArrowLeft, ArrowRight, UserCheck, Link, Sparkles, Copy 
} from 'lucide-react';

import { useAuth } from '../../context/AuthContext';

export default function ChannelsPage() {
  const { user } = useAuth();
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  // Wizard States
  const [currentStep, setCurrentStep] = useState(1); // 1: Link & Join, 2: Make Admin, 3: Success
  const [channelInput, setChannelInput] = useState('');
  const [joinedChannelData, setJoinedChannelData] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchChannels();
  }, []);

  const fetchChannels = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/channels/');
      setChannels(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const openWizard = () => {
    setCurrentStep(1);
    setChannelInput('');
    setJoinedChannelData(null);
    setErrorMsg('');
    setModalOpen(true);
  };

  const closeWizard = () => {
    setModalOpen(false);
    fetchChannels();
  };

  // Step 1: Submit Link & Auto-Join Channel
  const handleStep1Join = async (e) => {
    e.preventDefault();
    if (!channelInput.trim()) return;

    try {
      setProcessing(true);
      setErrorMsg('');
      const res = await apiClient.post('/channels/join', {
        telegram_chat_id: channelInput.trim(),
        title: 'قيد الانضمام'
      });
      setJoinedChannelData(res.data);
      setCurrentStep(2);
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'تعذر الانضمام إلى القناة. تأكد من صحة الرابط أو أن رابط الدعوة صالح.');
    } finally {
      setProcessing(false);
    }
  };

  // Step 2: Verify Promotion to Admin
  const handleStep2VerifyAdmin = async () => {
    if (!channelInput.trim()) return;

    try {
      setProcessing(true);
      setErrorMsg('');
      const res = await apiClient.post('/channels/verify', {
        telegram_chat_id: channelInput.trim(),
        title: joinedChannelData?.title || 'قناتي'
      });
      setJoinedChannelData(res.data);
      setCurrentStep(3);
      fetchChannels();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'لم يتم العثور على صلاحيات المشرف بعد. تأكد من ترقية @AutoMassge1 لمشرف داخل القناة.');
    } finally {
      setProcessing(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('هل أنت متأكد من رغبتك في إلغاء ربط هذه القناة؟ ستتوقف أتمتة الرسائل الخاصة بها.')) return;
    try {
      await apiClient.delete(`/channels/${id}`);
      fetchChannels();
    } catch (err) {
      alert(err.response?.data?.detail || 'فشل حذف القناة');
    }
  };

  const copyUsername = () => {
    navigator.clipboard.writeText('@AutoMassge1');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const maxChannels = user?.subscription?.max_channels || 3;
  const isLimitReached = channels.length >= maxChannels;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">قنواتي (ربط وتفعيل)</h1>
          <p className="text-xs text-slate-400 mt-1">اربط قناتك بسهولة من خلال معالج الانضمام الذكي والترقية التلقائية.</p>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs flex items-center gap-2">
            <span className="text-slate-400">القنوات المربوطة:</span>
            <strong className={`font-bold ${isLimitReached ? 'text-amber-400' : 'text-emerald-400'}`}>
              {channels.length} / {maxChannels}
            </strong>
          </div>

          <button
            onClick={openWizard}
            disabled={isLimitReached}
            className={`px-4 py-2.5 rounded-xl text-xs font-semibold shadow-lg transition-all flex items-center justify-center gap-2 ${
              isLimitReached
                ? 'bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-950 cursor-pointer'
            }`}
          >
            <Plus className="w-4 h-4" />
            <span>{isLimitReached ? 'وصلت للحد الأقصى' : 'ربط قناة جديدة'}</span>
          </button>
        </div>
      </div>

      {/* Limit Alert Banner if reached */}
      {isLimitReached && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 text-amber-300">
            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
            <span>لقد استهلكت كامل عدد القنوات المسموح بها في باقتك الحالية (<strong>{maxChannels}</strong> قنوات). لربط قنوات إضافية يرجى الترقية للباقة الأعلى.</span>
          </div>
          <a
            href="/subscription"
            className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs whitespace-nowrap"
          >
            ترقية الباقة الآن
          </a>
        </div>
      )}

      {/* Status Banner */}
      <div className="bg-emerald-950/20 border border-emerald-500/20 rounded-2xl p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 flex-shrink-0">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-white">نظام التفاعل الآلي الذكي مفعل</h4>
            <p className="text-[11px] text-slate-400">ينضم البوت لقناتك تلقائياً وبمجرد ترقيته لمشرف يبدأ فوراً برصد الأهداف ونشر تقييمات الأعضاء الحقيقيين.</p>
          </div>
        </div>
        <span className="text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-full whitespace-nowrap hidden md:inline-block">
          معالج ربط سريع
        </span>
      </div>

      {/* Channel Cards */}
      {loading ? (
        <div className="p-12 text-center text-slate-400">جاري تحميل القنوات...</div>
      ) : channels.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center">
          <Radio className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-bold text-white mb-1">لا توجد قنوات مربوطة حالياً</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto mb-6">
            اربط قناة تيليجرام الخاصة بك لتبدأ المنصة برصد صفقاتك وتحويل الريفيوهات الحقيقية تلقائياً.
          </p>
          <button
            onClick={openWizard}
            className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-all inline-flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            <span>ربط أول قناة الآن</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {channels.map((ch) => (
            <div key={ch.id} className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-6 transition-all shadow-md flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold">
                      {ch.title.charAt(0)}
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white">{ch.title}</h3>
                      <p className="text-xs text-slate-400 font-mono">{ch.username ? `@${ch.username}` : ch.telegram_chat_id}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(ch.id)}
                    className="text-slate-500 hover:text-rose-400 transition-colors p-1.5 rounded-lg hover:bg-rose-500/10"
                    title="إلغاء ربط القناة"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-2.5 my-4">
                  <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80">
                    <span className="text-[10px] uppercase text-slate-400 font-semibold block">البوت الأساسي (@AutoMassge1)</span>
                    <span className="text-xs font-medium text-emerald-400 flex items-center mt-0.5 gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> مشرف نشط
                    </span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80">
                    <span className="text-[10px] uppercase text-slate-400 font-semibold block">التعافي الذاتي (Failover)</span>
                    <span className="text-xs font-medium text-emerald-400 flex items-center mt-0.5 gap-1">
                      <ShieldCheck className="w-3.5 h-3.5" /> مفعّل 24/7
                    </span>
                  </div>
                </div>

                {/* Failover & Health Warning Banner if Admin Required */}
                {ch.last_health_warning && (
                  <div className={`p-3 rounded-xl mb-3 text-xs flex items-start justify-between gap-2 border ${
                    ch.health_status === 'ADMIN_RIGHTS_REQUIRED'
                      ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                      : ch.health_status === 'FAILOVER_ACTIVE'
                      ? 'bg-sky-500/10 border-sky-500/30 text-sky-300'
                      : 'bg-slate-950 border-slate-800 text-slate-300'
                  }`}>
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-semibold">{ch.last_health_warning}</p>
                        <p className="text-[10px] text-slate-400 mt-0.5">أضف الحساب (+447727190089 - Dala) كمشرف لتأمين النشر التلقائي عند الطوارئ.</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="pt-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                <span>تاريخ الربط: {new Date(ch.verified_at).toLocaleDateString('ar-EG')}</span>
                <span className="inline-flex items-center text-emerald-400 font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 ml-1.5 animate-pulse"></span>
                  {ch.health_status === 'FAILOVER_ACTIVE' ? 'يعمل عبر الحساب الاحتياطي' : 'متصلة ومحمية 24/7'}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 3-STEP ONBOARDING PROGRESS WIZARD MODAL */}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-xl overflow-hidden shadow-2xl">
            
            {/* Modal Header & Stepper */}
            <div className="p-6 border-b border-slate-800/80 bg-slate-950/50">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold text-xs">
                    {currentStep}/3
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">معالج ربط القناة الذكي</h3>
                    <p className="text-[11px] text-slate-400">اتبع الخطوات البسيطة لربط أي قناة عامة أو خاصة</p>
                  </div>
                </div>
                <button 
                  onClick={closeWizard}
                  className="text-slate-500 hover:text-slate-300 p-1 rounded-lg hover:bg-slate-800"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Progress Stepper Bar */}
              <div className="grid grid-cols-3 gap-2">
                <div className={`h-1.5 rounded-full transition-all duration-300 ${currentStep >= 1 ? 'bg-emerald-500 shadow-sm shadow-emerald-500/50' : 'bg-slate-800'}`} />
                <div className={`h-1.5 rounded-full transition-all duration-300 ${currentStep >= 2 ? 'bg-emerald-500 shadow-sm shadow-emerald-500/50' : 'bg-slate-800'}`} />
                <div className={`h-1.5 rounded-full transition-all duration-300 ${currentStep >= 3 ? 'bg-emerald-500 shadow-sm shadow-emerald-500/50' : 'bg-slate-800'}`} />
              </div>

              <div className="flex justify-between text-[11px] font-semibold text-slate-400 mt-2">
                <span className={currentStep === 1 ? 'text-emerald-400' : ''}>1. رابط القناة</span>
                <span className={currentStep === 2 ? 'text-emerald-400' : ''}>2. ترقية المشرف</span>
                <span className={currentStep === 3 ? 'text-emerald-400' : ''}>3. الجاهزية والربط</span>
              </div>
            </div>

            {/* Error Message Display */}
            {errorMsg && (
              <div className="m-6 mb-0 p-3.5 rounded-2xl bg-rose-950/40 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2.5 animate-in slide-in-from-top-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0 text-rose-400" />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* STEP 1: Enter Link & Bot Auto-Join */}
            {currentStep === 1 && (
              <form onSubmit={handleStep1Join} className="p-6 space-y-5">
                <div className="space-y-2">
                  <label className="block text-xs font-bold text-slate-200">
                    ضع رابط قناتك في تيليجرام (عامة أو خاصة):
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      placeholder="https://t.me/arabictchannel أو https://t.me/+AbCdEf..."
                      value={channelInput}
                      onChange={(e) => setChannelInput(e.target.value)}
                      className="w-full pl-4 pr-10 py-3 rounded-2xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-sm font-mono outline-none transition-all shadow-inner"
                      required
                    />
                    <Link className="w-4 h-4 text-slate-500 absolute right-3.5 top-3.5" />
                  </div>
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    💡 <strong>كيف تعمل:</strong> سيقوم البوت بالانضمام فوراً لقناتك كعضو عادي عبر الرابط، ليتسنى لك ترقيته لمشرف بكل سهولة حتى في القنوات الكبرى.
                  </p>
                </div>

                {/* Identity Card */}
                <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center font-bold text-emerald-400 text-xs">
                      🤖
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-white">Auto massge</h4>
                      <p className="text-[11px] font-mono text-emerald-400">@AutoMassge1</p>
                    </div>
                  </div>
                  <span className="text-[10px] bg-slate-800 text-slate-300 px-2.5 py-1 rounded-lg">
                    حساب النشر المعتمد
                  </span>
                </div>

                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={closeWizard}
                    className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors"
                  >
                    إلغاء
                  </button>
                  <button
                    type="submit"
                    disabled={processing}
                    className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold shadow-lg shadow-emerald-950 transition-all flex items-center gap-2"
                  >
                    {processing ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>جاري انضمام البوت للقناة...</span>
                      </>
                    ) : (
                      <>
                        <span>انضمام البوت ومتابعة</span>
                        <ArrowLeft className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}

            {/* STEP 2: Make Bot Admin in Channel */}
            {currentStep === 2 && (
              <div className="p-6 space-y-5">
                {/* Joined Channel Badge */}
                <div className="p-4 rounded-2xl bg-emerald-950/30 border border-emerald-500/30 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold">
                      ✓
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-xs font-bold text-white">{joinedChannelData?.title || 'القناة'}</h4>
                        <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-md font-bold">
                          انضم البوت بنجاح
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                        {joinedChannelData?.username ? `@${joinedChannelData.username}` : joinedChannelData?.chat_id}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Clear Instruction Steps */}
                <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-900 pb-2.5">
                    <span className="text-xs font-bold text-slate-200">الخطوة التالية (ترقية البوت لأدمن):</span>
                    <button
                      type="button"
                      onClick={copyUsername}
                      className="px-2.5 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-[11px] font-mono font-bold flex items-center gap-1.5 transition-colors border border-emerald-500/20"
                    >
                      {copied ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copied ? 'تم النسخ!' : '@AutoMassge1'}</span>
                    </button>
                  </div>

                  <ol className="list-decimal list-inside space-y-2 text-xs text-slate-300 leading-relaxed">
                    <li>افتح تطبيق تيليجرام وادخل على قناتك: <strong className="text-white">{joinedChannelData?.title}</strong>.</li>
                    <li>اضغط على <strong>إدارة القناة (Manage Channel) ➔ المشرفون (Administrators)</strong>.</li>
                    <li>اضغط <strong>إضافة مشرف (Add Administrator)</strong> واختر الحساب <strong className="text-emerald-400 font-mono">@AutoMassge1</strong> (الموجود في أعضاء القناة الآن).</li>
                    <li>فعّل له صلاحية <strong>نشر الرسائل (Post Messages)</strong> فقط ثم احفظ.</li>
                  </ol>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <button
                    type="button"
                    onClick={() => setCurrentStep(1)}
                    className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                  >
                    <ArrowRight className="w-4 h-4" />
                    <span>رجوع</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleStep2VerifyAdmin}
                    disabled={processing}
                    className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold shadow-lg shadow-emerald-950 transition-all flex items-center gap-2"
                  >
                    {processing ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>جاري التحقق من الترقية...</span>
                      </>
                    ) : (
                      <>
                        <ShieldCheck className="w-4 h-4" />
                        <span>تمت الترقية، تحقق وتفعيل القناة 🚀</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* STEP 3: Complete Success Screen */}
            {currentStep === 3 && (
              <div className="p-8 text-center space-y-5">
                <div className="w-16 h-16 rounded-3xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mx-auto shadow-xl shadow-emerald-950/40">
                  <Sparkles className="w-8 h-8 animate-bounce" />
                </div>

                <div>
                  <h3 className="text-lg font-bold text-white">🎉 تم ربط وتفعيل القناة بنجاح!</h3>
                  <p className="text-xs text-slate-300 mt-1.5 max-w-sm mx-auto leading-relaxed">
                    أصبحت قناتك <strong className="text-emerald-400">"{joinedChannelData?.title}"</strong> متصلة بالنظام بالكامل وجاهزة لرصد الصفقات ونشر التقييمات تلقائياً.
                  </p>
                </div>

                <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 text-xs text-slate-400 text-right space-y-1.5">
                  <div className="flex justify-between">
                    <span>اسم القناة:</span>
                    <span className="font-bold text-white">{joinedChannelData?.title}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>معرف القناة:</span>
                    <span className="font-mono text-emerald-400">{joinedChannelData?.telegram_chat_id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>حالة المراقبة:</span>
                    <span className="text-emerald-400 font-bold flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> نشطة 24/7
                    </span>
                  </div>
                </div>

                <div className="pt-2">
                  <button
                    type="button"
                    onClick={closeWizard}
                    className="w-full py-3 rounded-2xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-xl shadow-emerald-950 transition-all"
                  >
                    تم، التوجه للوحة التحكم والكلمات المفتاحية 🚀
                  </button>
                </div>
              </div>
            )}

          </div>
        </div>
      )}
    </div>
  );
}
