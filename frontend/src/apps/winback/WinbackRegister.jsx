import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { 
  UserCheck, Lock, Mail, User, Building2, ArrowRight, AlertCircle, 
  Sparkles, CheckCircle2 
} from 'lucide-react';

export default function WinbackRegister({ onSwitchToLogin }) {
  const { register } = useAuth();
  const [fullName, setFullName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      setError('');
      await register(fullName, email, password, companyName);
      const isSubdomain = window.location.hostname.startsWith('winback') || window.location.hostname.startsWith('retention');
      if (!isSubdomain && !window.location.pathname.startsWith('/winback') && !window.location.pathname.startsWith('/retention')) {
        window.history.pushState({}, '', '/winback');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'تعذر إنشاء الحساب، يرجى مراجعة البيانات');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen min-h-[100dvh] bg-slate-950 flex flex-col justify-center items-center p-3.5 sm:p-6 relative overflow-hidden select-none" dir="rtl">
      {/* Glows */}
      <div className="absolute -top-32 -right-32 w-96 h-96 bg-emerald-500/15 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute -bottom-32 -left-32 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl pointer-events-none"></div>

      <div className="w-full max-w-md bg-slate-900/90 backdrop-blur-xl border border-slate-800 rounded-3xl p-5 sm:p-8 shadow-2xl relative z-10">
        
        {/* Brand */}
        <div className="text-center mb-6 sm:mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center mx-auto mb-3 sm:mb-4 shadow-xl shadow-emerald-950/60 ring-4 ring-emerald-500/20">
            <UserCheck className="w-7 h-7 text-white" />
          </div>

          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-bold mb-2">
            <Sparkles className="w-3 h-3" />
            <span>حساب جديد | TeleWinBack AI</span>
          </div>

          <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight">
            إنشاء حساب في منصة استعادة الأعضاء
          </h1>
          <p className="text-[11px] sm:text-xs text-slate-400 mt-1 max-w-xs mx-auto">
            انضم الآن وابدأ بحماية أعضاء قنواتك واستردادهم تلقائياً
          </p>
        </div>

        {error && (
          <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-500/30 text-xs text-rose-400 flex items-center gap-2 mb-4">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3.5">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">الاسم بالكامل</label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-500 absolute right-3.5 top-3.5" />
              <input
                type="text"
                placeholder="أحمد محمد"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full pr-10 pl-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-sm outline-none transition-colors"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">اسم القناة أو المشروع</label>
            <div className="relative">
              <Building2 className="w-4 h-4 text-slate-500 absolute right-3.5 top-3.5" />
              <input
                type="text"
                placeholder="قناة التوصيات الذهبية"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                className="w-full pr-10 pl-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-sm outline-none transition-colors"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">البريد الإلكتروني</label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-500 absolute right-3.5 top-3.5" />
              <input
                type="email"
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pr-10 pl-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-sm outline-none transition-colors"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">كلمة المرور</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-500 absolute right-3.5 top-3.5" />
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pr-10 pl-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-sm outline-none transition-colors"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 active:scale-98 text-white text-xs sm:text-sm font-bold shadow-lg shadow-emerald-950/80 transition-all flex items-center justify-center gap-2 mt-3"
          >
            <span>{loading ? 'جاري إنشاء الحساب...' : 'إنشاء الحساب وبدء الاستخدام'}</span>
            <ArrowRight className="w-4 h-4 rotate-180" />
          </button>
        </form>

        <div className="mt-5 pt-4 border-t border-slate-800/80 flex items-center justify-center text-xs">
          <button
            type="button"
            onClick={onSwitchToLogin}
            className="text-emerald-400 hover:text-emerald-300 font-bold"
          >
            لديك حساب بالفعل؟ تسجيل الدخول
          </button>
        </div>
      </div>
    </div>
  );
}
