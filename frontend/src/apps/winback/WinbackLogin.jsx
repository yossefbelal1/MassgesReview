import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { 
  UserCheck, Lock, Mail, ArrowRight, AlertCircle, Eye, EyeOff, 
  Sparkles, RefreshCw, Bot, ShieldCheck, CheckCircle2 
} from 'lucide-react';

export default function WinbackLogin({ onSwitchToRegister }) {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      setError('');
      await login(email, password);
      // Ensure we navigate cleanly to the winback dashboard
      const isSubdomain = window.location.hostname.startsWith('winback') || window.location.hostname.startsWith('retention');
      if (!isSubdomain && !window.location.pathname.startsWith('/winback') && !window.location.pathname.startsWith('/retention')) {
        window.history.pushState({}, '', '/winback');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'البريد الإلكتروني أو كلمة المرور غير صحيحة');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen min-h-[100dvh] bg-slate-950 flex flex-col justify-center items-center p-3.5 sm:p-6 relative overflow-hidden select-none" dir="rtl">
      {/* Dynamic Background Glows */}
      <div className="absolute -top-32 -right-32 w-96 h-96 bg-emerald-500/15 rounded-full blur-3xl pointer-events-none animate-pulse"></div>
      <div className="absolute -bottom-32 -left-32 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl pointer-events-none"></div>

      <div className="w-full max-w-md bg-slate-900/90 backdrop-blur-xl border border-slate-800 rounded-3xl p-5 sm:p-8 shadow-2xl relative z-10">
        
        {/* Dedicated Standalone Brand Header */}
        <div className="text-center mb-6 sm:mb-8">
          <div className="relative inline-block mb-3 sm:mb-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-emerald-600 via-emerald-500 to-teal-400 flex items-center justify-center mx-auto shadow-xl shadow-emerald-950/60 ring-4 ring-emerald-500/20">
              <UserCheck className="w-7 h-7 text-white" />
            </div>
            <span className="absolute -bottom-1 -left-1 flex h-4 w-4">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-4 w-4 bg-emerald-500 border-2 border-slate-900"></span>
            </span>
          </div>

          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-bold mb-2">
            <Sparkles className="w-3 h-3" />
            <span>نظام استعادة الأعضاء المستقل | TeleWinBack AI</span>
          </div>

          <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight">
            بوابة دخول استعادة الأعضاء
          </h1>
          <p className="text-[11px] sm:text-xs text-slate-400 mt-1 max-w-xs mx-auto leading-relaxed">
            المنظومة الذكية لرصد مغادرة أعضاء قنوات التيليجرام واستعادتهم آلياً وفهم الأسباب 24/7
          </p>
        </div>

        {/* Feature Highlights Pills */}
        <div className="grid grid-cols-3 gap-2 mb-6">
          <div className="p-2 rounded-xl bg-slate-950/70 border border-slate-800/80 text-center">
            <RefreshCw className="w-4 h-4 text-emerald-400 mx-auto mb-1" />
            <span className="text-[10px] font-bold text-slate-300 block">رصد فوري</span>
            <span className="text-[8px] text-slate-500">نفس الثانية</span>
          </div>
          <div className="p-2 rounded-xl bg-slate-950/70 border border-slate-800/80 text-center">
            <Bot className="w-4 h-4 text-teal-400 mx-auto mb-1" />
            <span className="text-[10px] font-bold text-slate-300 block">يوزربوت آلي</span>
            <span className="text-[8px] text-slate-500">تواصل مباشر</span>
          </div>
          <div className="p-2 rounded-xl bg-slate-950/70 border border-slate-800/80 text-center">
            <ShieldCheck className="w-4 h-4 text-emerald-400 mx-auto mb-1" />
            <span className="text-[10px] font-bold text-slate-300 block">تحليل الأسباب</span>
            <span className="text-[8px] text-slate-500">ودليل الأعضاء</span>
          </div>
        </div>

        {error && (
          <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-500/30 text-xs text-rose-400 flex items-center gap-2 mb-4 animate-shake">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">البريد الإلكتروني</label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-500 absolute right-3.5 top-3.5" />
              <input
                type="email"
                placeholder="admin@channel.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pr-10 pl-4 py-3 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-sm outline-none transition-colors"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">كلمة المرور</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-500 absolute right-3.5 top-3.5" />
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pr-10 pl-10 py-3 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-sm outline-none transition-colors"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute left-3.5 top-3.5 text-slate-500 hover:text-slate-300"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 active:scale-98 text-white text-xs sm:text-sm font-bold shadow-lg shadow-emerald-950/80 transition-all flex items-center justify-center gap-2 mt-2"
          >
            <span>{loading ? 'جاري التحقق والدخول...' : 'دخول منصة استعادة الأعضاء'}</span>
            <ArrowRight className="w-4 h-4 rotate-180" />
          </button>
        </form>

        <div className="mt-6 pt-5 border-t border-slate-800/80 flex flex-col items-center justify-center gap-2.5 text-xs">
          {onSwitchToRegister && (
            <button
              type="button"
              onClick={onSwitchToRegister}
              className="text-emerald-400 hover:text-emerald-300 font-bold transition-colors"
            >
              ليس لديك حساب؟ إنشاء حساب جديد في WinBack
            </button>
          )}

          <a
            href="/"
            className="text-[11px] text-slate-500 hover:text-slate-400 flex items-center gap-1 transition-colors"
          >
            <span>العودة لمنصة ريفيو فلو (إشارات وتقييمات)</span>
          </a>
        </div>
      </div>
    </div>
  );
}
