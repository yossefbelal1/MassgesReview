import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { 
  Radio, Plus, Trash2, CheckCircle2, AlertTriangle, ShieldCheck, 
  RefreshCw, X, ArrowLeft, ArrowRight, UserCheck, Link, Sparkles, Copy,
  Check, ExternalLink, Activity
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function ChannelsPage() {
  const { user, refreshProfile } = useAuth();
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
    if (refreshProfile) {
      refreshProfile();
    }
  }, []);

  useEffect(() => {
    if (modalOpen) {
      document.body.classList.add('modal-open');
    } else {
      document.body.classList.remove('modal-open');
    }
    return () => {
      document.body.classList.remove('modal-open');
    };
  }, [modalOpen]);

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
    if (refreshProfile) {
      refreshProfile();
    }
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
      alert('فشل إلغاء ربط القناة');
    }
  };

  const copyBackupBot = () => {
    navigator.clipboard.writeText('+447727190089');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const sub = user?.subscription;
  const maxChannels = sub?.max_channels || 1;
  const isLimitReached = channels.length >= maxChannels;

  return (
    <div className="space-y-4 sm:space-y-6" dir="rtl">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4">
        <div>
          <h1 className="text-lg sm:text-xl font-bold text-white tracking-tight">إدارة قنوات تيليجرام</h1>
          <p className="text-[11px] sm:text-xs text-slate-400 mt-0.5">اربط قنواتك بسهولة من خلال معالج الانضمام والترقية التلقائي.</p>
        </div>

        <div className="flex items-center justify-between sm:justify-end gap-2.5">
          <div className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs flex items-center gap-1.5 flex-shrink-0">
            <span className="text-slate-400">القنوات:</span>
            <strong className={`font-bold ${isLimitReached ? 'text-amber-400' : 'text-emerald-400'}`}>
              {channels.length} / {maxChannels}
            </strong>
          </div>

          <button
            onClick={openWizard}
            disabled={isLimitReached}
            className={`px-4 py-2.5 rounded-xl text-xs font-bold shadow-lg transition-all flex items-center justify-center gap-1.5 ${
              isLimitReached
                ? 'bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed'
                : 'bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white shadow-emerald-950 cursor-pointer'
            }`}
          >
            <Plus className="w-4 h-4 flex-shrink-0" />
            <span>{isLimitReached ? 'الحد الأقصى' : 'ربط قناة جديدة'}</span>
          </button>
        </div>
      </div>

      {/* Limit Alert Banner if reached */}
      {isLimitReached && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-3.5 sm:p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 text-amber-300">
            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
            <span>استهلكت الحد الأقصى للقنوات في باقتك (<strong>{maxChannels}</strong> قنوات). لربط قنوات إضافية يرجى ترقية باقتك.</span>
          </div>
          <button
            onClick={() => window.location.href = '/subscription'}
            className="w-full sm:w-auto px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs text-center"
          >
            ترقية الباقة الآن
          </button>
        </div>
      )}

      {/* Failover / Self-Healing Info Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-lg">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3.5 border-b border-slate-800/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 flex-shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-xs sm:text-sm font-bold text-white flex items-center gap-2">
                <span>نظام الحماية الذكي والتسليم المزدوج (Dual-Bot Failover)</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                  نشط 24/7
                </span>
              </h4>
              <p className="text-[11px] text-slate-400 mt-0.5">
                حساب أساسي (@AutoMassge1) + حساب احتياطي للطوارئ (Dala) لضمان عدم توقف النشر لحظة واحدة.
              </p>
            </div>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1 text-xs">
          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2 overflow-hidden">
              <span className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0"></span>
              <div className="truncate">
                <span className="text-slate-400 text-[10px] block">الحساب الأساسي</span>
                <strong className="text-white text-xs font-mono">@AutoMassge1</strong>
              </div>
            </div>
            <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded font-bold">نشط</span>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2 overflow-hidden">
              <span className="w-2 h-2 rounded-full bg-blue-400 flex-shrink-0"></span>
              <div className="truncate">
                <span className="text-slate-400 text-[10px] block">حساب الطوارئ الاحتياطي</span>
                <strong className="text-white text-xs font-mono">Dala (+447727190089)</strong>
              </div>
            </div>
            <button
              onClick={copyBackupBot}
              className="text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-1 rounded-lg font-bold flex items-center gap-1 transition-colors flex-shrink-0"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              <span>{copied ? 'تم النسخ' : 'نسخ الرقم'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Channel Cards */}
      {loading ? (
        <div className="p-12 text-center text-slate-400">جاري تحميل القنوات...</div>
      ) : channels.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 sm:p-12 text-center">
          <Radio className="w-10 sm:w-12 h-10 sm:h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-sm sm:text-base font-bold text-white mb-1">لا توجد قنوات مربوطة حالياً</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto mb-6">
            اربط قناة تيليجرام الخاصة بك لتبدأ المنصة برصد صفقاتك وتحويل الريفيوهات الحقيقية تلقائياً.
          </p>
          <button
            onClick={openWizard}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all inline-flex items-center justify-center gap-2"
          >
            <Plus className="w-4 h-4" />
            <span>ربط أول قناة الآن</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5">
          {channels.map((ch) => (
            <div key={ch.id} className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-4 sm:p-6 transition-all shadow-md flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3 overflow-hidden">
                    <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold text-sm flex-shrink-0">
                      {ch.title ? ch.title.charAt(0) : 'ق'}
                    </div>
                    <div className="overflow-hidden">
                      <h3 className="text-sm font-bold text-white truncate">{ch.title}</h3>
                      <p className="text-xs text-slate-400 font-mono truncate">{ch.username ? `@${ch.username}` : ch.telegram_chat_id}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(ch.id)}
                    className="text-slate-500 hover:text-rose-400 transition-colors p-2 rounded-lg hover:bg-rose-500/10 flex-shrink-0"
                    title="إلغاء ربط القناة"
                    aria-label="إلغاء ربط القناة"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-2 my-3">
                  <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                    <span className="text-[10px] text-slate-400 block mb-0.5">صلاحيات الإدارة</span>
                    <span className="flex items-center gap-1.5 text-xs text-emerald-400 font-bold">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>مشرف مفعل</span>
                    </span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                    <span className="text-[10px] text-slate-400 block mb-0.5">حالة الأتمتة</span>
                    <span className="flex items-center gap-1.5 text-xs text-emerald-400 font-bold">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                      <span>مراقبة 24/7</span>
                    </span>
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-xs">
                <span className="text-[11px] text-slate-400">تاريخ الربط: {new Date(ch.created_at).toLocaleDateString('ar-EG')}</span>
                <span className="text-[11px] font-bold text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">
                  متصلة
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* CHANNEL WIZARD MODAL (Mobile-Friendly Full Dialog / Bottom Sheet) */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-950/80 backdrop-blur-sm" dir="rtl">
          <div className="bg-slate-900 border-t sm:border border-slate-800 rounded-t-3xl sm:rounded-2xl max-w-lg w-full p-5 sm:p-8 max-h-[92vh] overflow-y-auto shadow-2xl relative">
            <button
              onClick={closeWizard}
              className="absolute left-4 top-4 text-slate-400 hover:text-white p-2 rounded-xl bg-slate-800/50 hover:bg-slate-800 transition-colors"
              aria-label="إغلاق"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Wizard Step 1 */}
            {currentStep === 1 && (
              <form onSubmit={handleStep1Join} className="space-y-4">
                <div className="text-center pb-2">
                  <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto mb-3">
                    <Link className="w-6 h-6" />
                  </div>
                  <h3 className="text-base font-bold text-white">الخطوة 1: رابط القناة</h3>
                  <p className="text-xs text-slate-400 mt-1">أدخل رابط قناتك العامة أو رابط الدعوة الخاص بقناتك الخاصة.</p>
                </div>

                {errorMsg && (
                  <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>{errorMsg}</span>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    رابط القناة أو المعرف (Username)
                  </label>
                  <input
                    type="text"
                    placeholder="https://t.me/your_channel أو @channel_name"
                    value={channelInput}
                    onChange={(e) => setChannelInput(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-sm outline-none font-mono"
                    required
                  />
                </div>

                <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-400 space-y-1 leading-relaxed">
                  <p>💡 <strong>ملاحظة:</strong> إذا كانت القناة خاصة، تأكد من استخدام رابط دعوة صالح (Invite Link) لكي يتمكن البوت من الانضمام.</p>
                </div>

                <button
                  type="submit"
                  disabled={processing || !channelInput.trim()}
                  className="w-full py-3.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold shadow-lg shadow-emerald-950 transition-all flex items-center justify-center gap-2"
                >
                  <span>{processing ? 'جاري الانضمام إلى القناة...' : 'الانضمام للقناة والمتابعة'}</span>
                  <ArrowLeft className="w-4 h-4" />
                </button>
              </form>
            )}

            {/* Wizard Step 2 */}
            {currentStep === 2 && (
              <div className="space-y-4">
                <div className="text-center pb-2">
                  <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center mx-auto mb-3">
                    <UserCheck className="w-6 h-6" />
                  </div>
                  <h3 className="text-base font-bold text-white">الخطوة 2: ترقية البوت لمشرف (Admin)</h3>
                  <p className="text-xs text-slate-400 mt-1">انضم البوت بنجاح! الآن قم بترقيته لمشرف داخل قناتك لنشر الريفيوهات.</p>
                </div>

                {errorMsg && (
                  <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>{errorMsg}</span>
                  </div>
                )}

                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 text-xs">
                  <h4 className="font-bold text-white mb-2">تعليمات الترقية السريعة:</h4>
                  <ol className="list-decimal list-inside space-y-1.5 text-slate-300 leading-relaxed">
                    <li>افتح إعدادات قناتك في تيليجرام $\rightarrow$ المشرفون (Administrators).</li>
                    <li>ابحث عن حساب: <strong className="text-emerald-400 font-mono">@AutoMassge1</strong> وقم بإضافته مشرفاً.</li>
                    <li>امنحه صلاحية: <strong>نشر الرسائل (Post Messages)</strong>.</li>
                  </ol>
                </div>

                <div className="grid grid-cols-2 gap-2.5">
                  <button
                    type="button"
                    onClick={() => setCurrentStep(1)}
                    className="py-3 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
                  >
                    رجوع
                  </button>
                  <button
                    type="button"
                    onClick={handleStep2VerifyAdmin}
                    disabled={processing}
                    className="py-3 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold shadow-lg shadow-emerald-950 transition-all flex items-center justify-center gap-1.5"
                  >
                    <span>{processing ? 'جاري التحقق...' : 'تأكيد الترقية والتشغيل 🚀'}</span>
                  </button>
                </div>
              </div>
            )}

            {/* Wizard Step 3: Success */}
            {currentStep === 3 && (
              <div className="text-center space-y-4 py-2">
                <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">تم تفعيل القناة بنجاح 100%!</h3>
                  <p className="text-xs text-slate-400 mt-1">تم التحقق من صلاحيات المشرف، وتم توليد الكلمات المفتاحية الافتراضية لقناتك تلقائياً.</p>
                </div>

                <button
                  onClick={closeWizard}
                  className="w-full py-3.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-lg transition-all"
                >
                  الانتهاء والعودة للقنوات
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
