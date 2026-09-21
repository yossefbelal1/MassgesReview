import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { 
  UserCheck, Users, RefreshCw, MessageSquare, ShieldAlert, CheckCircle2, 
  Clock, Sparkles, Filter, Search, ArrowUpRight, Send, AlertCircle, 
  Settings, BarChart3, Bot, ChevronLeft, X, ExternalLink, Radio, MessageCircle
} from 'lucide-react';

export default function RetentionDashboard({ onNavigate }) {
  const [channels, setChannels] = useState([]);
  const [selectedChannelId, setSelectedChannelId] = useState('');
  const [activeTab, setActiveTab] = useState('cases'); // 'cases', 'analytics', 'members', 'settings', 'userbots'
  
  const [summary, setSummary] = useState(null);
  const [cases, setCases] = useState([]);
  const [members, setMembers] = useState([]);
  const [settings, setSettings] = useState(null);
  const [userbots, setUserbots] = useState([]);
  
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Chat Modal State
  const [selectedCase, setSelectedCase] = useState(null);
  const [caseMessages, setCaseMessages] = useState([]);
  const [modalLoading, setModalLoading] = useState(false);
  const [manualText, setManualText] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);

  // Settings Form State
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsForm, setSettingsForm] = useState({
    is_retention_enabled: true,
    is_welcome_enabled: false,
    initial_delay_value: 3,
    initial_delay_unit: 'minutes',
    welcome_message_template: '',
    recovery_first_message_template: '',
    invite_link: '',
    max_daily_contacts: 30
  });

  useEffect(() => {
    fetchChannels();
  }, []);

  useEffect(() => {
    fetchData();
  }, [selectedChannelId, activeTab]);

  const fetchChannels = async () => {
    try {
      const res = await apiClient.get('/channels/');
      setChannels(res.data);
      if (res.data.length > 0 && !selectedChannelId) {
        setSelectedChannelId(res.data[0].id);
      }
    } catch (err) {
      console.error('Error fetching channels:', err);
    }
  };

  const fetchData = async () => {
    try {
      setLoading(true);
      const chParam = selectedChannelId ? `?channel_id=${selectedChannelId}` : '';

      // 1. Summary KPIs
      const sumRes = await apiClient.get(`/retention/summary${chParam}`);
      setSummary(sumRes.data);

      // 2. Active Tab Data
      if (activeTab === 'cases') {
        const casesRes = await apiClient.get(`/retention/cases${chParam}${statusFilter ? `&status_filter=${statusFilter}` : ''}`);
        setCases(casesRes.data);
      } else if (activeTab === 'members') {
        const memRes = await apiClient.get(`/retention/members${chParam}`);
        setMembers(memRes.data);
      } else if (activeTab === 'settings' && selectedChannelId) {
        const setRes = await apiClient.get(`/retention/settings/${selectedChannelId}`);
        setSettings(setRes.data);
        const sSec = setRes.data.initial_delay_seconds || 180;
        const isMin = sSec >= 60 && sSec % 60 === 0;
        setSettingsForm({
          is_retention_enabled: setRes.data.is_retention_enabled,
          is_welcome_enabled: setRes.data.is_welcome_enabled,
          initial_delay_value: isMin ? sSec / 60 : sSec,
          initial_delay_unit: isMin ? 'minutes' : 'seconds',
          welcome_message_template: setRes.data.welcome_message_template || '',
          recovery_first_message_template: setRes.data.recovery_first_message_template || '',
          invite_link: setRes.data.invite_link || '',
          max_daily_contacts: setRes.data.max_daily_contacts || 30
        });
      } else if (activeTab === 'userbots') {
        const botRes = await apiClient.get('/retention/userbots');
        setUserbots(botRes.data);
      }
    } catch (err) {
      console.error('Error fetching retention data:', err);
    } finally {
      setLoading(false);
    }
  };

  const openCaseChat = async (c) => {
    setSelectedCase(c);
    setModalLoading(true);
    try {
      const res = await apiClient.get(`/retention/cases/${c.id}`);
      setCaseMessages(res.data.messages || []);
    } catch (err) {
      alert('فشل تحميل سجل المحادثة');
    } finally {
      setModalLoading(false);
    }
  };

  const handleSendManualMessage = async (e) => {
    e.preventDefault();
    if (!selectedCase || !manualText.trim()) return;

    try {
      setSendingMessage(true);
      const res = await apiClient.post(`/retention/cases/${selectedCase.id}/message`, {
        text: manualText.trim()
      });
      setCaseMessages(prev => [...prev, res.data]);
      setManualText('');
      setSelectedCase(prev => ({ ...prev, status: 'CONVERSATION_ACTIVE', contactable: true }));
      fetchAllData();
    } catch (err) {
      alert(err.response?.data?.detail || 'فشل إرسال الرسالة');
    } finally {
      setSendingMessage(false);
    }
  };

  const handleRetryCase = async (caseId) => {
    try {
      await apiClient.post(`/retention/cases/${caseId}/retry`);
      if (selectedCase && selectedCase.id === caseId) {
        setSelectedCase(prev => ({ ...prev, status: 'SCHEDULED', contactable: true }));
      }
      fetchAllData();
    } catch (err) {
      alert('حدث خطأ أثناء إعادة الجدولة: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleResetAllUncontactable = async () => {
    try {
      setLoading(true);
      const res = await apiClient.post('/retention/cases/reset-all');
      alert(res.data?.message || 'تمت إعادة جدولة الحالات بنجاح.');
      fetchAllData();
    } catch (err) {
      alert('حدث خطأ أثناء إعادة الجدولة: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    if (!selectedChannelId) return;

    const calculatedDelay = settingsForm.initial_delay_unit === 'minutes'
      ? (parseInt(settingsForm.initial_delay_value) || 1) * 60
      : (parseInt(settingsForm.initial_delay_value) || 30);

    try {
      setSavingSettings(true);
      await apiClient.put(`/retention/settings/${selectedChannelId}`, {
        is_retention_enabled: settingsForm.is_retention_enabled,
        is_welcome_enabled: settingsForm.is_welcome_enabled,
        initial_delay_seconds: calculatedDelay,
        welcome_message_template: settingsForm.welcome_message_template,
        recovery_first_message_template: settingsForm.recovery_first_message_template,
        invite_link: settingsForm.invite_link,
        max_daily_contacts: parseInt(settingsForm.max_daily_contacts) || 30
      });
      alert('تم حفظ إعدادات الاسترداد والترحيب بنجاح! 🚀');
    } catch (err) {
      alert(err.response?.data?.detail || 'فشل حفظ الإعدادات');
    } finally {
      setSavingSettings(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'RECOVERED':
        return <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">🟢 تم الاسترداد بنجاح</span>;
      case 'CONVERSATION_ACTIVE':
        return <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center gap-1">💬 قيد المحادثة</span>;
      case 'LINK_DELIVERED':
        return <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-teal-500/10 text-teal-400 border border-teal-500/20 flex items-center gap-1">🔗 تم إرسال الرابط</span>;
      case 'CONTACTED':
        return <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-1">📩 تم التواصل الأولي</span>;
      case 'SCHEDULED':
        return <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center gap-1">⏱️ مجدولة للتواصل</span>;
      case 'UNCONTACTABLE':
        return <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-slate-800 text-slate-400 border border-slate-700 flex items-center gap-1">🛡️ غير قابل للمراسلة</span>;
      case 'OPT_OUT':
        return <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20 flex items-center gap-1">⛔ رفض المتابعة</span>;
      default:
        return <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-slate-800 text-slate-400">{status}</span>;
    }
  };

  const getReasonLabel = (cat) => {
    switch (cat) {
      case 'MISTAKE_OR_LOST_LINK': return '❌ خرج بالخطأ / يبحث عن الرابط';
      case 'TOO_MANY_MESSAGES': return '🔕 كثرة الرسائل والإشعارات';
      case 'CONTENT_CRITIQUE': return '📉 ملاحظات على المحتوى والصفقات';
      case 'OPT_OUT': return '🚫 طلب إيقاف المراسلة';
      default: return '💬 رأي / استفسار آخر';
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6 max-w-7xl mx-auto" dir="rtl">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-lg sm:text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-emerald-400" />
            <span>نظام استعادة ومتابعة الأعضاء (Retention & Win-back)</span>
          </h1>
          <p className="text-[11px] sm:text-xs text-slate-400 mt-0.5">
            رصد مغادرة الأعضاء آلياً، والتواصل معهم ذكياً، وفهم الأسباب، وإعادتهم لقناتك تلقائياً.
          </p>
        </div>

        {/* Channel Selector */}
        {channels.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400 hidden sm:inline">القناة:</span>
            <select
              value={selectedChannelId}
              onChange={(e) => setSelectedChannelId(e.target.value)}
              className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-white text-xs font-semibold outline-none focus:border-emerald-500 min-h-[40px]"
            >
              <option value="">جميع القنوات</option>
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>{ch.title}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Executive KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {/* Win-back Rate */}
        <div className="col-span-2 sm:col-span-1 p-4 rounded-2xl bg-gradient-to-br from-emerald-950/60 to-slate-900 border border-emerald-500/30 shadow-lg">
          <span className="text-[11px] font-semibold text-emerald-400 block mb-1">معدل الاسترداد (Win-back)</span>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-white font-mono">{summary?.win_back_rate_percent || 0}%</span>
            <span className="text-[10px] text-emerald-400 font-bold">🎯 نسبة النجاح</span>
          </div>
          <span className="text-[10px] text-slate-400 mt-1 block">من إجمالي الأعضاء المغادرين</span>
        </div>

        {/* Total Left */}
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-400 block mb-1">إجمالي المغادرين</span>
          <span className="text-xl sm:text-2xl font-bold text-white font-mono">{summary?.total_left_detected || 0}</span>
          <span className="text-[10px] text-slate-500 block mt-1">عضو تم رصدهم</span>
        </div>

        {/* Contacted */}
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 shadow-sm">
          <span className="text-[11px] font-semibold text-blue-400 block mb-1">تم التواصل تلقائياً</span>
          <span className="text-xl sm:text-2xl font-bold text-white font-mono">{summary?.total_contacted || 0}</span>
          <span className="text-[10px] text-slate-500 block mt-1">محادثة أطلقها اليوزربوت</span>
        </div>

        {/* Rejoined */}
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 shadow-sm">
          <span className="text-[11px] font-semibold text-emerald-400 block mb-1">أعضاء عادوا للقناة</span>
          <span className="text-xl sm:text-2xl font-bold text-emerald-400 font-mono">{summary?.total_rejoined || 0}</span>
          <span className="text-[10px] text-slate-500 block mt-1">متوسط العودة: {summary?.average_rejoin_hours || 0} ساعة</span>
        </div>

        {/* Privacy Restricted */}
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-400 block mb-1">حماية الخصوصية</span>
          <span className="text-xl sm:text-2xl font-bold text-slate-300 font-mono">{summary?.uncontactable_count || 0}</span>
          <span className="text-[10px] text-slate-500 block mt-1">إعدادات خصوصية تيليجرام</span>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-1.5 p-1 bg-slate-900/80 rounded-2xl border border-slate-800 overflow-x-auto text-xs">
        <button
          onClick={() => setActiveTab('cases')}
          className={`px-4 py-2.5 rounded-xl font-bold whitespace-nowrap transition-all flex items-center gap-2 ${
            activeTab === 'cases' ? 'bg-emerald-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
          }`}
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>حالات الاسترداد الحية ({cases.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('analytics')}
          className={`px-4 py-2.5 rounded-xl font-bold whitespace-nowrap transition-all flex items-center gap-2 ${
            activeTab === 'analytics' ? 'bg-emerald-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
          }`}
        >
          <BarChart3 className="w-3.5 h-3.5" />
          <span>تحليلات أسباب المغادرة</span>
        </button>

        <button
          onClick={() => setActiveTab('members')}
          className={`px-4 py-2.5 rounded-xl font-bold whitespace-nowrap transition-all flex items-center gap-2 ${
            activeTab === 'members' ? 'bg-emerald-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          <span>دليل الأعضاء</span>
        </button>

        <button
          onClick={() => setActiveTab('settings')}
          className={`px-4 py-2.5 rounded-xl font-bold whitespace-nowrap transition-all flex items-center gap-2 ${
            activeTab === 'settings' ? 'bg-emerald-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
          }`}
        >
          <Settings className="w-3.5 h-3.5" />
          <span>إعدادات الاسترداد والترحيب</span>
        </button>

        <button
          onClick={() => setActiveTab('userbots')}
          className={`px-4 py-2.5 rounded-xl font-bold whitespace-nowrap transition-all flex items-center gap-2 ${
            activeTab === 'userbots' ? 'bg-emerald-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
          }`}
        >
          <Bot className="w-3.5 h-3.5" />
          <span>حالة اليوزربوت</span>
        </button>
      </div>

      {/* ── TAB 1: LIVE RECOVERY CASES ────────────────────────────────────── */}
      {activeTab === 'cases' && (
        <div className="space-y-3">
          {/* Filters Bar */}
          <div className="p-3 bg-slate-900 border border-slate-800 rounded-2xl flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute right-3 top-3 text-slate-500" />
              <input
                type="text"
                placeholder="البحث بالاسم، المعرف، أو اليوزر..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pr-9 pl-4 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white outline-none focus:border-emerald-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white outline-none"
              >
                <option value="">جميع الحالات</option>
                <option value="RECOVERED">تم الاسترداد 🟢</option>
                <option value="CONVERSATION_ACTIVE">قيد المحادثة 💬</option>
                <option value="LINK_DELIVERED">تم إرسال الرابط 🔗</option>
                <option value="CONTACTED">تم التواصل 📩</option>
                <option value="SCHEDULED">مجدولة للتواصل ⏱️</option>
                <option value="UNCONTACTABLE">غير قابل للتواصل 🛡️</option>
                <option value="OPT_OUT">رفض الاستمرار ⛔</option>
              </select>

              <button
                onClick={handleResetAllUncontactable}
                className="px-3 py-2 rounded-xl bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 text-xs font-bold transition-all flex items-center gap-1.5 whitespace-nowrap"
                title="إعادة محاولة المراسلة لجميع الحالات العالقة"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>إعادة مراسلة غير المتواصل معهم</span>
              </button>

              <button
                onClick={fetchData}
                className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                title="تحديث"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Cases Feed / Table */}
          {loading ? (
            <div className="p-12 text-center text-slate-400">جاري تحميل حالات الاسترداد...</div>
          ) : cases.length === 0 ? (
            <div className="p-12 text-center bg-slate-900 border border-slate-800 rounded-2xl text-slate-400">
              لا توجد حالات استرداد مسجلة حتى الآن. سيبدأ النظام تلقائياً برصد أي مغادرة فور حدوثها في قناتك!
            </div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-right text-xs">
                  <thead className="bg-slate-950/60 border-b border-slate-800 text-slate-400 font-semibold">
                    <tr>
                      <th className="p-3.5">العضو</th>
                      <th className="p-3.5">القناة</th>
                      <th className="p-3.5">الحالة</th>
                      <th className="p-3.5">السبب المرصود</th>
                      <th className="p-3.5">اليوزربوت</th>
                      <th className="p-3.5">تاريخ المغادرة</th>
                      <th className="p-3.5 text-center">المحادثة</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {cases
                      .filter(c => {
                        if (!searchQuery) return true;
                        const s = searchQuery.toLowerCase();
                        return (c.user_full_name && c.user_full_name.toLowerCase().includes(s)) ||
                               (c.user_username && c.user_username.toLowerCase().includes(s)) ||
                               c.telegram_user_id.includes(s);
                      })
                      .map((c) => (
                        <tr key={c.id} className="hover:bg-slate-800/30 transition-colors">
                          <td className="p-3.5 font-bold text-white">
                            <div className="flex items-center gap-2">
                              <div className="w-7 h-7 rounded-full bg-slate-800 flex items-center justify-center text-emerald-400 text-xs font-bold">
                                {(c.user_full_name || 'U')[0]}
                              </div>
                              <div>
                                <span>{c.user_full_name || `مستخدم ${c.telegram_user_id.slice(-4)}`}</span>
                                {c.user_username && (
                                  <span className="block text-[10px] text-slate-400 font-mono font-normal">@{c.user_username}</span>
                                )}
                              </div>
                            </div>
                          </td>
                          <td className="p-3.5 text-slate-300 font-medium">{c.channel_title}</td>
                          <td className="p-3.5">{getStatusBadge(c.status)}</td>
                          <td className="p-3.5">
                            {c.leave_reason_category ? (
                              <div>
                                <span className="font-semibold text-slate-200">{getReasonLabel(c.leave_reason_category)}</span>
                                {c.leave_reason_raw && (
                                  <span className="block text-[10px] text-slate-400 truncate max-w-xs italic">
                                    "{c.leave_reason_raw}"
                                  </span>
                                )}
                              </div>
                            ) : (
                              <span className="text-slate-500 italic">قيد التحليل...</span>
                            )}
                          </td>
                          <td className="p-3.5 font-mono text-[11px] text-emerald-400">
                            {c.assigned_userbot ? `@${c.assigned_userbot}` : 'تلقائي'}
                          </td>
                          <td className="p-3.5 text-slate-400 text-[11px]">
                            {new Date(c.created_at).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })}
                          </td>
                          <td className="p-3.5 text-center">
                            <div className="flex items-center justify-center gap-1.5">
                              <button
                                onClick={() => openCaseChat(c)}
                                className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-emerald-400 text-xs font-bold transition-all inline-flex items-center gap-1.5"
                              >
                                <MessageSquare className="w-3.5 h-3.5" />
                                <span>المحادثة</span>
                              </button>
                              {c.status === 'UNCONTACTABLE' && (
                                <button
                                  onClick={() => handleRetryCase(c.id)}
                                  className="px-2.5 py-1.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-bold border border-emerald-500/20 transition-all inline-flex items-center gap-1"
                                  title="إعادة الجدولة والمراسلة"
                                >
                                  <RefreshCw className="w-3 h-3" />
                                  <span>إعادة المحاولة</span>
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TAB 2: FEEDBACK & CHURN ANALYTICS ──────────────────────────────── */}
      {activeTab === 'analytics' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Churn Reasons Breakdown */}
            <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-sm space-y-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-emerald-400" />
                <span>أسباب المغادرة المسجلة ومعدل استرداد كل سبب</span>
              </h3>

              {summary?.reasons_breakdown?.length === 0 ? (
                <div className="p-8 text-center text-slate-500 text-xs italic">
                  لم يتم تسجيل إجابات من الأعضاء بعد. ستظهر الإحصائيات مع بدء تفاعل الأعضاء بالردود!
                </div>
              ) : (
                <div className="space-y-3">
                  {summary?.reasons_breakdown?.map((r, i) => (
                    <div key={i} className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-white">{getReasonLabel(r.category)}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-slate-400">{r.count} عضو</span>
                          <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-bold font-mono">
                            {r.rate}% استرداد
                          </span>
                        </div>
                      </div>
                      <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div 
                          className="bg-emerald-500 h-full rounded-full transition-all"
                          style={{ width: `${Math.min(100, r.rate)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Daily Trend (Last 7 Days) */}
            <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-sm space-y-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <RefreshCw className="w-4 h-4 text-blue-400" />
                <span>معدل المغادرة مقابل العودة اليومي (آخر 7 أيام)</span>
              </h3>

              <div className="space-y-2">
                {summary?.daily_trend?.map((d, idx) => (
                  <div key={idx} className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800/60 text-xs">
                    <span className="font-mono text-slate-400">{d.date}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-rose-400 font-bold">-{d.leaves} مغادر</span>
                      <span className="text-emerald-400 font-bold">+{d.rejoins} عاد</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 3: AUDIENCE DIRECTORY ─────────────────────────────────────── */}
      {activeTab === 'members' && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Users className="w-4 h-4 text-emerald-400" />
              <span>أعضاء القناة المسجلين ({members.length})</span>
            </h3>
          </div>

          {members.length === 0 ? (
            <div className="p-12 text-center text-slate-400 text-xs">لا يوجد أعضاء مسجلين بعد.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-right text-xs">
                <thead className="bg-slate-950/60 border-b border-slate-800 text-slate-400">
                  <tr>
                    <th className="p-3.5">العضو</th>
                    <th className="p-3.5">الحالة</th>
                    <th className="p-3.5">تاريخ الانضمام</th>
                    <th className="p-3.5">آخر مغادرة / عودة</th>
                    <th className="p-3.5">الاهتمامات</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {members.map((m) => (
                    <tr key={m.id} className="hover:bg-slate-800/30">
                      <td className="p-3.5 font-bold text-white">
                        <span>{m.first_name || 'مستخدم'} {m.last_name || ''}</span>
                        {m.username && <span className="block text-[10px] text-slate-400 font-mono">@{m.username}</span>}
                      </td>
                      <td className="p-3.5">{getStatusBadge(m.status)}</td>
                      <td className="p-3.5 text-slate-400 font-mono text-[11px]">
                        {new Date(m.first_joined_at).toLocaleDateString('ar-EG')}
                      </td>
                      <td className="p-3.5 text-slate-400 text-[11px]">
                        {m.last_rejoined_at ? `عاد في ${new Date(m.last_rejoined_at).toLocaleDateString('ar-EG')}` : m.last_left_at ? `غادر في ${new Date(m.last_left_at).toLocaleDateString('ar-EG')}` : 'نشط دائماً'}
                      </td>
                      <td className="p-3.5">
                        {m.interests?.length > 0 ? (
                          <div className="flex gap-1 flex-wrap">
                            {m.interests.map((it, idx) => (
                              <span key={idx} className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-semibold">
                                {it}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-slate-500 italic text-[11px]">عام</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── TAB 4: AUTOMATION & SETTINGS ──────────────────────────────────── */}
      {activeTab === 'settings' && (
        <form onSubmit={handleSaveSettings} className="space-y-4 max-w-3xl">
          <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-3">
              <Sparkles className="w-4 h-4 text-emerald-400" />
              <span>إعدادات التواصل والاسترداد الذكي</span>
            </h3>

            {/* Toggle Retention Enabled */}
            <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-950 border border-slate-800">
              <div>
                <strong className="text-xs text-white block">تفعيل استرداد المغادرين التلقائي</strong>
                <span className="text-[11px] text-slate-400">يبدأ اليوزربوت بالتواصل مع أي عضو يغادر القناة تلقائياً.</span>
              </div>
              <input
                type="checkbox"
                checked={settingsForm.is_retention_enabled}
                onChange={(e) => setSettingsForm({ ...settingsForm, is_retention_enabled: e.target.checked })}
                className="w-5 h-5 accent-emerald-500 rounded cursor-pointer"
              />
            </div>

            {/* Initial Delay */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                فترة الانتظار قبل بدء أول تواصل بعد المغادرة
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min="1"
                  max="120"
                  value={settingsForm.initial_delay_value}
                  onChange={(e) => setSettingsForm({ ...settingsForm, initial_delay_value: e.target.value })}
                  className="w-32 px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs font-mono outline-none focus:border-emerald-500"
                />
                <select
                  value={settingsForm.initial_delay_unit}
                  onChange={(e) => setSettingsForm({ ...settingsForm, initial_delay_unit: e.target.value })}
                  className="px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs font-bold outline-none cursor-pointer"
                >
                  <option value="minutes">دقائق (موصى به: 3 دقائق)</option>
                  <option value="seconds">ثواني</option>
                </select>
              </div>
              <p className="text-[10px] text-slate-400 mt-1">تمنح العضو فرصة للعودة بنفسه دون الشعور بالملاحقة الفورية.</p>
            </div>

            {/* Channel Rejoin Link */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                رابط القناة لإعادة الانضمام (Invite Link)
              </label>
              <input
                type="text"
                placeholder="مثال: https://t.me/+AbCdEfGhIjKlMn"
                value={settingsForm.invite_link}
                onChange={(e) => setSettingsForm({ ...settingsForm, invite_link: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs font-mono outline-none focus:border-emerald-500"
              />
              <p className="text-[10px] text-slate-400 mt-1">يتم إرساله آلياً للعضو إذا أفاد بمغادرته بالخطأ أو طلب الرابط.</p>
            </div>

            {/* Recovery Message Template */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                نص رسالة الاسترداد الأولى المخصصة (افتراضي مريح وودود)
              </label>
              <textarea
                rows={3}
                placeholder="مرحباً {name}، لاحظنا مغادرتك لقناة {channel} وحبينا نتطمن عليك..."
                value={settingsForm.recovery_first_message_template}
                onChange={(e) => setSettingsForm({ ...settingsForm, recovery_first_message_template: e.target.value })}
                className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs outline-none focus:border-emerald-500 leading-relaxed"
              />
            </div>

            {/* Welcome Flow Toggle */}
            <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-950 border border-slate-800">
              <div>
                <strong className="text-xs text-white block">تفعيل الترحيب بالأعضاء الجدد (Welcome Flow)</strong>
                <span className="text-[11px] text-slate-400">يرسل اليوزربوت رسالة ترحيبية وسؤال اهتمامات في الخاص عند انضمام عضو جديد.</span>
              </div>
              <input
                type="checkbox"
                checked={settingsForm.is_welcome_enabled}
                onChange={(e) => setSettingsForm({ ...settingsForm, is_welcome_enabled: e.target.checked })}
                className="w-5 h-5 accent-emerald-500 rounded cursor-pointer"
              />
            </div>

            {settingsForm.is_welcome_enabled && (
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  نص رسالة الترحيب
                </label>
                <textarea
                  rows={3}
                  placeholder="أهلاً بك يا {name} في {channel}! 🚀..."
                  value={settingsForm.welcome_message_template}
                  onChange={(e) => setSettingsForm({ ...settingsForm, welcome_message_template: e.target.value })}
                  className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs outline-none focus:border-emerald-500 leading-relaxed"
                />
              </div>
            )}

            {/* Max Daily Contacts Safety Limit */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                الحد الأقصى للمراسلات اليومية (Anti-Spam Safety Guard)
              </label>
              <input
                type="number"
                min="5"
                max="50"
                value={settingsForm.max_daily_contacts}
                onChange={(e) => setSettingsForm({ ...settingsForm, max_daily_contacts: e.target.value })}
                className="w-32 px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs font-mono outline-none"
              />
              <span className="text-[10px] text-slate-400 block mt-1">يحمي حساب اليوزربوت من قيود تيليجرام (موصى به: 25-35 يومياً).</span>
            </div>

            <div className="pt-3 border-t border-slate-800 flex justify-end">
              <button
                type="submit"
                disabled={savingSettings}
                className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold shadow-lg transition-all"
              >
                {savingSettings ? 'جاري الحفظ...' : 'حفظ الإعدادات 🚀'}
              </button>
            </div>
          </div>
        </form>
      )}

      {/* ── TAB 5: USERBOT POOL HEALTH ────────────────────────────────────── */}
      {activeTab === 'userbots' && (
        <div className="space-y-3 max-w-2xl">
          <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl shadow-sm">
            <h3 className="text-sm font-bold text-white flex items-center gap-2 mb-3">
              <Bot className="w-4 h-4 text-emerald-400" />
              <span>أسطول حسابات اليوزربوت المتصلة (Unified Userbot Pool)</span>
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed mb-4">
              يعمل النظام بنظام الحسابات المتعددة (Failover Pool). يدير النظام التناوب بين الحسابات آلياً لضمان عدم توقف المراسلة.
            </p>

            <div className="space-y-3">
              {userbots.map((b, i) => (
                <div key={i} className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold">
                      {i + 1}
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-white flex items-center gap-2">
                        <span>@{b.username}</span>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-normal">
                          {b.name === 'primary' ? 'الحساب الأساسي' : 'حساب الطوارئ والاحتياط'}
                        </span>
                      </h4>
                      <span className="text-[11px] text-slate-400">
                        تم إرسال {b.daily_contacts_sent} من أصل {b.max_daily_contacts} رسالة اليوم
                      </span>
                    </div>
                  </div>

                  <span className={`px-2.5 py-1 rounded-full text-[11px] font-bold border ${
                    b.is_healthy ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                  }`}>
                    {b.is_healthy ? 'نشط ومتصل 🟢' : 'يحتاج فحص 🔴'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── CHAT MODAL / CONVERSATION DRAWER ──────────────────────────────── */}
      {selectedCase && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4" dir="rtl">
          <div className="bg-slate-900 border-t sm:border border-slate-800 rounded-t-3xl sm:rounded-2xl w-full max-w-xl h-[85vh] sm:h-[600px] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="p-4 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold text-xs">
                  {(selectedCase.user_full_name || 'U')[0]}
                </div>
                <div>
                  <h3 className="text-xs font-bold text-white flex items-center gap-1.5">
                    <span>{selectedCase.user_full_name || `مستخدم ${selectedCase.telegram_user_id.slice(-4)}`}</span>
                    {selectedCase.user_username && <span className="text-slate-400 font-mono text-[10px]">(@{selectedCase.user_username})</span>}
                  </h3>
                  <span className="text-[10px] text-slate-400">قناة: {selectedCase.channel_title}</span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {selectedCase.status === 'UNCONTACTABLE' && (
                  <button
                    type="button"
                    onClick={() => handleRetryCase(selectedCase.id)}
                    className="px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-[11px] font-bold border border-emerald-500/20 transition-all flex items-center gap-1"
                  >
                    <RefreshCw className="w-3 h-3" />
                    <span>إعادة الجدولة</span>
                  </button>
                )}
                {getStatusBadge(selectedCase.status)}
                <button
                  onClick={() => setSelectedCase(null)}
                  className="w-7 h-7 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Chat Transcript Area */}
            <div className="flex-1 p-4 overflow-y-auto space-y-3 bg-slate-950/40 text-xs">
              {modalLoading ? (
                <div className="p-8 text-center text-slate-400">جاري تحميل سجل المحادثة...</div>
              ) : caseMessages.length === 0 ? (
                <div className="p-8 text-center text-slate-500 italic">
                  لم يتم تبادل أي رسائل بعد. الرسالة مجدولة للإرسال تلقائياً أو يمكنك المراسلة يدوياً الآن بالأسفل.
                </div>
              ) : (
                caseMessages.map((msg) => {
                  const isOutbound = msg.direction === 'OUTBOUND';
                  const isSystem = msg.sender_type === 'SYSTEM';

                  if (isSystem) {
                    return (
                      <div key={msg.id} className="text-center my-2">
                        <span className="inline-block px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-bold">
                          {msg.text}
                        </span>
                      </div>
                    );
                  }

                  return (
                    <div
                      key={msg.id}
                      className={`flex flex-col ${isOutbound ? 'items-start' : 'items-end'}`}
                    >
                      <div
                        className={`max-w-[80%] p-3 rounded-2xl leading-relaxed whitespace-pre-wrap ${
                          isOutbound
                            ? 'bg-slate-800 text-slate-100 rounded-tr-none'
                            : 'bg-emerald-600 text-white rounded-tl-none shadow-md'
                        }`}
                      >
                        {msg.text}
                      </div>
                      <span className="text-[9px] text-slate-500 mt-1 font-mono">
                        {isOutbound ? `اليوزربوت (@${msg.userbot_username || 'bot'})` : 'العضو'} •{' '}
                        {new Date(msg.sent_at).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  );
                })
              )}
            </div>

            {/* Manual Reply Input */}
            <form onSubmit={handleSendManualMessage} className="p-3 bg-slate-950 border-t border-slate-800 flex items-center gap-2">
              <input
                type="text"
                placeholder="اكتب رداً مخصصاً للعضو لإرساله عبر اليوزربوت..."
                disabled={sendingMessage}
                value={manualText}
                onChange={(e) => setManualText(e.target.value)}
                className="flex-1 px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white text-xs outline-none focus:border-emerald-500 disabled:opacity-40"
              />
              <button
                type="submit"
                disabled={sendingMessage || !manualText.trim()}
                className="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-xs font-bold transition-all flex items-center gap-1.5"
              >
                <Send className="w-3.5 h-3.5" />
                <span>إرسال</span>
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
