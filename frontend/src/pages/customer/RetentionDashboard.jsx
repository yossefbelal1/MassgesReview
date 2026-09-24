import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { 
  UserCheck, Users, RefreshCw, MessageSquare, ShieldAlert, CheckCircle2, 
  Clock, Sparkles, Filter, Search, ArrowUpRight, Send, AlertCircle, 
  Settings, BarChart3, Bot, ChevronLeft, X, ExternalLink, Radio, MessageCircle,
  Camera, Upload, Eye, Check, Copy, HelpCircle, Key, Phone, ShieldCheck, ChevronDown, ChevronUp, Trash2, Power, Zap,
  Target, PieChart, TrendingUp, Activity, PlusCircle, Lock, Smartphone
} from 'lucide-react';

const WINBACK_TEMPLATES = [
  {
    id: 'owner_in_touch',
    title: 'اطمئنان واستفسار مع رابط العودة المباشر ⭐ موصى به',
    badge: 'الأعلى تفاعلاً وسرعة',
    desc: 'رسالة ودية للاطمئنان على العضو ومعرفة سبب الخروج مع إرسال رابط العودة مباشرة',
    text: 'مرحباً {name}، لاحظنا مغادرتك لقناة {channel} وحبينا نتطمن عليك 🌹\nهل خرجت بالخطأ أو كان هناك أمر أزعجك؟ رأيك يهمنا جداً لتطوير القناة.\n\n{invite_link}'
  },
  {
    id: 'mistake_rejoin',
    title: 'مغادرة بالخطأ ورابط العودة السريعة',
    badge: 'استرداد فوري',
    desc: 'للأعضاء الذين يغادرون بالخطأ ويرغبون برابط عودة سريع ومباشر',
    text: 'أهلاً بك يا {name} 🌹 لاحظنا خروجك من قناة {channel}، إذا كان الخروج بالخطأ تقدر ترجع من خلال الرابط التالي:\n{invite_link}\nيسعدنا دائماً وجودك معنا!'
  },
  {
    id: 'content_feedback',
    title: 'استطلاع رأي المحتوى والإعلانات',
    badge: 'فهم الأسباب',
    desc: 'سؤال مباشر لمعرفة هل كثرة الإشعارات أو عدم ملاءمة المحتوى سبب الخروج',
    text: 'مرحباً يا {name} 🌟 يهمنا جداً رأيك، لاحظنا مغادرتك لـ {channel}، حابين نعرف هل المحتوى لم يناسبك أم الإعلانات والإشعارات كانت مزعجة؟ رأيك يساعدنا على التطوير 💡\n\n{invite_link}'
  },
  {
    id: 'exclusive_content',
    title: 'ميزات وتحديثات حصرية قادمة',
    badge: 'تحفيز العودة',
    desc: 'إشعار العضو بأن هناك صفقات ومحتوى حصري قادم تم إعداده خصيصاً',
    text: 'أهلاً {name} 🎁 بصفتك عضواً في {channel}، جهزنا محتوى وتحديثات حصرية هذا الأسبوع وحبينا نتطمن عليك. تفضل رابط العودة:\n\n{invite_link}'
  }
];

export default function RetentionDashboard({ onNavigate, externalTab, onTabChange }) {
  const [channels, setChannels] = useState([]);
  const [selectedChannelId, setSelectedChannelId] = useState('');
  const [activeTab, setActiveTab] = useState(externalTab || 'cases'); // 'cases', 'analytics', 'members', 'settings', 'userbots'
  
  useEffect(() => {
    if (externalTab && externalTab !== activeTab) {
      setActiveTab(externalTab);
    }
  }, [externalTab]);

  const handleTabSelect = (tab) => {
    setActiveTab(tab);
    if (onTabChange) onTabChange(tab);
  };

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

  // Avatar upload state
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [avatarTimestamp, setAvatarTimestamp] = useState(Date.now());

  // Fast Outreach & Notification Toast State
  const [toast, setToast] = useState(null);
  const [bulkSending, setBulkSending] = useState(false);
  const [sendingCaseId, setSendingCaseId] = useState(null);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => {
      setToast(null);
    }, 4500);
  };

  // Dedicated Userbot & Multi-bot Fleet State
  const [dedicatedUserbot, setDedicatedUserbot] = useState(null);
  const [userbotForm, setUserbotForm] = useState({ api_id: '', api_hash: '', phone: '', channel_id: '' });
  const [useCustomApi, setUseCustomApi] = useState(false);
  const [userbotStep, setUserbotStep] = useState(1); // 1 = API selection / guide, 2 = Phone & Channel, 3 = Verify OTP, 4 = 2FA, 5 = Success
  const [showAddUserbotModal, setShowAddUserbotModal] = useState(false);
  const [loginAttemptId, setLoginAttemptId] = useState('');
  const [verifyCode, setVerifyCode] = useState('');
  const [verifyPassword, setVerifyPassword] = useState('');
  const [needs2fa, setNeeds2fa] = useState(false);
  const [sendingOtp, setSendingOtp] = useState(false);
  const [verifyingOtp, setVerifyingOtp] = useState(false);
  const [connectedUserbotSuccess, setConnectedUserbotSuccess] = useState(null);

  // Settings Form State
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsForm, setSettingsForm] = useState({
    is_retention_enabled: true,
    is_welcome_enabled: false,
    initial_delay_value: 5,
    initial_delay_unit: 'seconds',
    welcome_message_template: '',
    recovery_first_message_template: WINBACK_TEMPLATES[0].text,
    invite_link: '',
    max_daily_contacts: 30
  });

  // Stage Drill-Down State (Stages 1, 2, 3, 4)
  const [selectedStageView, setSelectedStageView] = useState(null); // 1 = Detected, 2 = Contacted, 3 = Responded/Conversations, 4 = Rejoined
  const [stageCases, setStageCases] = useState([]);
  const [loadingStageCases, setLoadingStageCases] = useState(false);
  const [stageSearchQuery, setStageSearchQuery] = useState('');
  const [stageStatusFilter, setStageStatusFilter] = useState('');

  const openStageView = async (stageNum) => {
    setSelectedStageView(stageNum);
    setLoadingStageCases(true);
    setStageSearchQuery('');
    setStageStatusFilter('');
    try {
      const chParam = selectedChannelId ? `&channel_id=${selectedChannelId}` : '';
      const res = await apiClient.get(`/retention/cases?stage=${stageNum}&limit=250${chParam}`);
      setStageCases(res.data);
    } catch (err) {
      showToast('فشل تحميل تفاصيل المرحلة', 'error');
    } finally {
      setLoadingStageCases(false);
    }
  };

  useEffect(() => {
    if (selectedStageView) {
      openStageView(selectedStageView);
    }
  }, [selectedChannelId]);

  useEffect(() => {
    fetchChannels();
  }, []);

  useEffect(() => {
    fetchData(false);
    // Real-time live polling every 7 seconds
    const interval = setInterval(() => {
      fetchData(true);
    }, 7000);
    return () => clearInterval(interval);
  }, [selectedChannelId, activeTab, statusFilter]);

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

  const fetchData = async (isBackground = false) => {
    try {
      if (!isBackground) setLoading(true);
      const chParam = selectedChannelId ? `?channel_id=${selectedChannelId}` : '';

      // 1. Summary KPIs
      const sumRes = await apiClient.get(`/retention/summary${chParam}`);
      setSummary(sumRes.data);

      // 2. Fetch dedicated userbot for selected channel
      if (selectedChannelId) {
        try {
          const dedRes = await apiClient.get(`/retention/userbot/${selectedChannelId}`);
          setDedicatedUserbot(dedRes.data);
        } catch (e) {
          setDedicatedUserbot(null);
        }
      } else {
        setDedicatedUserbot(null);
      }

      // 3. Active Tab Data
      if (activeTab === 'cases') {
        const casesRes = await apiClient.get(`/retention/cases${chParam}${statusFilter ? `&status_filter=${statusFilter}` : ''}`);
        setCases(casesRes.data);
      } else if (activeTab === 'members') {
        const memRes = await apiClient.get(`/retention/members${chParam}`);
        setMembers(memRes.data);
      } else if (activeTab === 'settings' && selectedChannelId && !isBackground) {
        const setRes = await apiClient.get(`/retention/settings/${selectedChannelId}`);
        setSettings(setRes.data);
        const sSec = (setRes.data.initial_delay_seconds !== undefined && setRes.data.initial_delay_seconds !== null) ? setRes.data.initial_delay_seconds : 5;
        const isMin = sSec >= 60 && sSec % 60 === 0;
        setSettingsForm({
          is_retention_enabled: setRes.data.is_retention_enabled,
          is_welcome_enabled: setRes.data.is_welcome_enabled,
          initial_delay_value: isMin ? sSec / 60 : sSec,
          initial_delay_unit: isMin ? 'minutes' : 'seconds',
          welcome_message_template: setRes.data.welcome_message_template || '',
          recovery_first_message_template: setRes.data.recovery_first_message_template || WINBACK_TEMPLATES[0].text,
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
      if (!isBackground) setLoading(false);
    }
  };

  const handleRequestUserbotCode = async (e) => {
    e.preventDefault();
    const chId = userbotForm.channel_id || selectedChannelId || channels[0]?.id;
    if (!chId) {
      showToast('يرجى اختيار القناة أولاً لربط اليوزربوت بها.', 'error');
      return;
    }
    if (!userbotForm.phone?.trim()) {
      showToast('يرجى كتابة رقم الهاتف كاملاً بصيغته الدولية (مثال: +96650... أو +2010...).', 'error');
      return;
    }
    if (useCustomApi && (!userbotForm.api_id || !userbotForm.api_hash)) {
      showToast('يرجى كتابة الـ API ID و API HASH أو قم بإلغاء خيار الإعدادات المتقدمة لاستخدام المفاتيح الافتراضية.', 'error');
      return;
    }

    try {
      setSendingOtp(true);
      const payload = {
        channel_id: chId,
        phone: userbotForm.phone.trim()
      };
      if (useCustomApi && userbotForm.api_id) {
        payload.api_id = parseInt(userbotForm.api_id);
      }
      if (useCustomApi && userbotForm.api_hash) {
        payload.api_hash = userbotForm.api_hash.trim();
      }

      const res = await apiClient.post('/retention/userbot/request-code', payload);
      setLoginAttemptId(res.data.login_attempt_id);
      setUserbotStep(3);
      setNeeds2fa(false);
      setVerifyCode('');
      setVerifyPassword('');
      showToast(res.data.message || 'تم إرسال كود التحقق بنجاح! تفقد تطبيق تيليجرام 📲', 'success');
    } catch (err) {
      showToast('فشل طلب الكود: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setSendingOtp(false);
    }
  };

  const handleVerifyUserbotCode = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (userbotStep === 3 && !verifyCode.trim()) {
      showToast('يرجى إدخال كود التحقق المستلم في تطبيق تيليجرام.', 'error');
      return;
    }

    try {
      setVerifyingOtp(true);
      const res = await apiClient.post('/retention/userbot/verify-code', {
        login_attempt_id: loginAttemptId,
        code: verifyCode.trim(),
        password: verifyPassword.trim() || undefined
      });

      if (res.data.needs_2fa) {
        setNeeds2fa(true);
        setUserbotStep(4);
        showToast(res.data.message || 'حسابك محمي بالتحقق بخطوتين (2FA). يرجى إدخال كلمة المرور السحابية.', 'error');
        return;
      }

      showToast(res.data.message || 'تم ربط الحساب بنجاح! 🎉', 'success');
      setConnectedUserbotSuccess(res.data.userbot || {
        first_name: 'يوزربوت تيليجرام',
        phone: userbotForm.phone,
        username: ''
      });
      setUserbotStep(5);
      fetchData(true);
    } catch (err) {
      showToast('فشل التحقق: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setVerifyingOtp(false);
    }
  };

  const resetUserbotWizard = () => {
    setUserbotStep(1);
    setUseCustomApi(false);
    setUserbotForm({ api_id: '', api_hash: '', phone: '', channel_id: selectedChannelId || channels[0]?.id || '' });
    setVerifyCode('');
    setVerifyPassword('');
    setNeeds2fa(false);
    setLoginAttemptId('');
    setConnectedUserbotSuccess(null);
  };

  const handleDisconnectDedicatedUserbot = async (userbotId = null, targetChannelId = null) => {
    if (!window.confirm('هل أنت متأكد من فصل هذا الحساب عن نظام المراسلة؟')) {
      return;
    }

    try {
      setActionLoading(true);
      let res;
      if (userbotId) {
        res = await apiClient.delete(`/retention/userbots/${userbotId}`);
      } else {
        const chId = targetChannelId || selectedChannelId;
        res = await apiClient.delete(`/retention/userbot/${chId}`);
      }
      showToast(res.data?.message || 'تم فصل الحساب بنجاح.', 'success');
      if (targetChannelId === selectedChannelId || !userbotId) {
        setDedicatedUserbot(null);
      }
      fetchData();
    } catch (err) {
      showToast('فشل فصل الحساب: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDedicatedAvatarUpload = async (e, targetUserbotId = null) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      showToast('يرجى اختيار ملف صورة صالح (JPEG أو PNG)', 'error');
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      showToast('حجم الصورة كبير جداً (الحد الأقصى 10 ميجابايت)', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      setUploadingAvatar(true);
      const endpoint = targetUserbotId 
        ? `/retention/userbots/${targetUserbotId}/avatar` 
        : `/retention/userbot/${selectedChannelId}/avatar`;
      const res = await apiClient.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      showToast(res.data?.message || 'تم تحديث صورة بروفايل اليوزربوت بنجاح! 🎉', 'success');
      setAvatarTimestamp(Date.now());
      fetchData(true);
    } catch (err) {
      showToast('فشل رفع الصورة: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setUploadingAvatar(false);
    }
  };

  const openCaseChat = async (c) => {
    setSelectedCase(c);
    setModalLoading(true);
    try {
      const res = await apiClient.get(`/retention/cases/${c.id}`);
      setCaseMessages(res.data.messages || []);
    } catch (err) {
      showToast('فشل تحميل سجل المحادثة', 'error');
    } finally {
      setModalLoading(false);
    }
  };

  const handleAvatarUpload = async (sessionName, e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      alert('يرجى اختيار ملف صورة صالح (JPEG أو PNG)');
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      alert('حجم الصورة كبير جداً (الحد الأقصى 10 ميجابايت)');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      setUploadingAvatar(true);
      const res = await apiClient.post(`/retention/userbots/${sessionName}/avatar`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      alert(res.data?.message || 'تم تحديث صورة بروفايل اليوزربوت على تيليجرام بنجاح! 🎉');
      setAvatarTimestamp(Date.now());
      const botRes = await apiClient.get('/retention/userbots');
      setUserbots(botRes.data);
    } catch (err) {
      alert('فشل رفع الصورة: ' + (err.response?.data?.detail || err.message));
    } finally {
      setUploadingAvatar(false);
    }
  };

  const insertTag = (tag) => {
    setSettingsForm(prev => {
      const current = prev.recovery_first_message_template || '';
      return {
        ...prev,
        recovery_first_message_template: current ? `${current} ${tag}` : tag
      };
    });
  };

  const getSelectedChannelTitle = () => {
    const ch = channels.find(c => c.id === selectedChannelId);
    return ch ? ch.title : 'قناتك';
  };

  const getLivePreviewText = () => {
    const raw = settingsForm.recovery_first_message_template || WINBACK_TEMPLATES[0].text;
    const title = getSelectedChannelTitle();
    const link = settingsForm.invite_link || 'https://t.me/+AbCdEfGhIjKlMn';
    return raw
      .replace(/{channel}/g, title)
      .replace(/{name}/g, 'أحمد')
      .replace(/{invite_link}/g, link);
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
      showToast('تم إرسال الرسالة بنجاح 📩', 'success');
      fetchData();
    } catch (err) {
      showToast(err.response?.data?.detail || 'فشل إرسال الرسالة', 'error');
    } finally {
      setSendingMessage(false);
    }
  };

  const handleRetryCase = async (caseId) => {
    try {
      setSendingCaseId(caseId);
      const res = await apiClient.post(`/retention/cases/${caseId}/retry`);
      showToast('تمت إعادة جدولة العضو وتفعيل الإرسال الفوري ⚡', 'success');
      if (selectedCase && selectedCase.id === caseId) {
        setSelectedCase(prev => ({ ...prev, status: 'SCHEDULED', contactable: true }));
      }
      await fetchData();
    } catch (err) {
      showToast('حدث خطأ أثناء المحاولة: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setSendingCaseId(null);
    }
  };

  const handleSendCaseNow = async (caseId) => {
    try {
      setSendingCaseId(caseId);
      const res = await apiClient.post(`/retention/cases/${caseId}/send-now`);
      if (res.data?.success) {
        showToast(res.data.message || 'تم إرسال رسالة الاسترداد بنجاح! ⚡', 'success');
      } else {
        showToast('تنبيه أثناء الإرسال: ' + (res.data?.message || 'تعذر الإرسال حالياً'), 'error');
      }
      await fetchData();
    } catch (err) {
      showToast('حدث خطأ أثناء الإرسال: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setSendingCaseId(null);
    }
  };

  const handleSendAllPendingNow = async () => {
    try {
      setBulkSending(true);
      const chParam = selectedChannelId ? `?channel_id=${selectedChannelId}` : '';
      const res = await apiClient.post(`/retention/cases/turbo-dispatch${chParam}`);
      showToast(res.data?.message || 'تم تفعيل الإرسال التوربو الذكي لجميع الأعضاء بنجاح ⚡', 'success');
      await fetchData();
    } catch (err) {
      showToast('حدث خطأ أثناء الإرسال الفوري: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setBulkSending(false);
    }
  };

  const handleResetAllUncontactable = handleSendAllPendingNow;

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
      showToast('تم حفظ إعدادات الاسترداد والترحيب بنجاح! 🚀', 'success');
    } catch (err) {
      showToast(err.response?.data?.detail || 'فشل حفظ الإعدادات', 'error');
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
        return <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1" title="إعدادات خصوصية المستخدم في تيليجرام تمنع استقبال الرسائل من غير جهات الاتصال">🔒 خصوصية تيليجرام مانعة</span>;
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
      case 'AWAITING_REPLY': return '📩 تم التواصل (في انتظار رد العضو)';
      case 'IN_QUEUE': return '⏱️ في طابور الإرسال الآلي';
      case 'PRIVACY_BLOCKED': return '🛡️ خصوصية تيليجرام تمنع المراسلة';
      default: return '💬 استفسار / رأي مسجل';
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6 max-w-7xl mx-auto relative" dir="rtl">
      {/* Floating Notification Toast */}
      {toast && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 animate-in fade-in slide-in-from-top-4 duration-300 pointer-events-auto">
          <div className={`px-4 py-3 rounded-2xl shadow-2xl border backdrop-blur-md flex items-center gap-3 ${
            toast.type === 'error' 
              ? 'bg-rose-950/95 border-rose-500/50 text-rose-200' 
              : 'bg-emerald-950/95 border-emerald-500/50 text-emerald-100'
          }`}>
            {toast.type === 'error' ? (
              <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
            ) : (
              <Zap className="w-5 h-5 text-amber-400 shrink-0 animate-pulse" />
            )}
            <span className="text-xs sm:text-sm font-bold">{toast.message}</span>
            <button onClick={() => setToast(null)} className="p-1 hover:opacity-75 text-slate-400 mr-2">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Top Header & Context Control Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600/20 to-teal-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0 shadow-sm">
            {activeTab === 'analytics' ? <BarChart3 className="w-5 h-5" /> :
             activeTab === 'cases' ? <RefreshCw className="w-5 h-5" /> :
             activeTab === 'members' ? <Users className="w-5 h-5" /> :
             activeTab === 'settings' ? <Settings className="w-5 h-5" /> :
             <Bot className="w-5 h-5" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
                {activeTab === 'analytics' && 'تحليلات أسباب المغادرة وقمع الاسترداد'}
                {activeTab === 'cases' && 'حالات الاسترداد الحية'}
                {activeTab === 'members' && 'دليل الأعضاء الشامل'}
                {activeTab === 'settings' && 'قواعد وقوالب الاسترداد'}
                {activeTab === 'userbots' && 'حسابات الإرسال واليوزربوت'}
              </h2>
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
            </div>
            <p className="text-xs text-slate-400">
              {activeTab === 'analytics' && 'مؤشرات الأداء المباشرة وقمع تحويل الأعضاء المستردين'}
              {activeTab === 'cases' && 'المتابعة اللحظية للمغادرين وحالة رسائل الاسترداد الآلية'}
              {activeTab === 'members' && 'سجل كامل لأعضاء القنوات وتاريخ انضمامهم ومغادرتهم'}
              {activeTab === 'settings' && 'تخصيص نصوص الرسائل الذكية والفواصل الزمنية بين الإرسال'}
              {activeTab === 'userbots' && 'إدارة حسابات تيليجرام المرتبطة والتحقق من حالتها الأمنية'}
            </p>
          </div>
        </div>

        {/* Global Controls: Channel Selector & Live Refresh */}
        <div className="flex items-center gap-2 self-start sm:self-auto">
          {channels.length > 0 && (
            <div className="relative">
              <select
                value={selectedChannelId}
                onChange={(e) => setSelectedChannelId(e.target.value)}
                className="appearance-none pl-8 pr-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-white text-xs font-semibold outline-none focus:border-emerald-500 cursor-pointer shadow-sm hover:bg-slate-850 transition-colors"
              >
                <option value="">جميع القنوات</option>
                {channels.map((ch) => (
                  <option key={ch.id} value={ch.id}>{ch.title}</option>
                ))}
              </select>
              <div className="absolute left-2.5 top-2.5 pointer-events-none text-slate-500 text-[10px]">▼</div>
            </div>
          )}

          <button
            onClick={() => fetchData(false)}
            disabled={loading}
            title="تحديث فوري للبيانات"
            className="px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 active:scale-95 border border-slate-800 text-slate-300 text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-emerald-400 ${loading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">تحديث</span>
          </button>
        </div>
      </div>

      {/* Executive Metrics Strip: Unified Luxury Instrument Panel */}
      <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl backdrop-blur-xl shadow-sm overflow-hidden grid grid-cols-2 lg:grid-cols-5 divide-y lg:divide-y-0 sm:divide-x sm:divide-x-reverse divide-slate-800/60">
        {/* Win-back Rate */}
        <div className="col-span-2 sm:col-span-1 p-3.5 sm:p-4.5 flex flex-col justify-between group hover:bg-slate-850/40 transition-colors">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
            <span className="font-semibold text-emerald-400">معدل الاسترداد</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-black font-mono text-emerald-400 tracking-tight">
              {summary?.win_back_rate_percent || 0}%
            </span>
            <span className="text-[11px] text-slate-400 font-medium">
              ({summary?.total_rejoined || 0} عادوا من {summary?.total_contacted || 0} تم التواصل)
            </span>
          </div>
          <div className="w-full h-1 bg-slate-800/80 rounded-full mt-2.5 overflow-hidden">
            <div 
              className="h-full bg-emerald-400 rounded-full transition-all duration-700"
              style={{ width: `${Math.min(100, summary?.win_back_rate_percent || 0)}%` }}
            />
          </div>
        </div>

        {/* Leavers Detected */}
        <div className="p-3.5 sm:p-4.5 flex flex-col justify-between group hover:bg-slate-850/40 transition-colors">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
            <span className="font-semibold">المغادرين المرصودين</span>
            <Users className="w-4 h-4 text-slate-500" />
          </div>
          <div>
            <span className="text-2xl sm:text-3xl font-black font-mono text-white tracking-tight">
              {summary?.total_left_detected || 0}
            </span>
            <span className="text-[11px] text-slate-500 block mt-0.5">مرصود تلقائياً 24/7</span>
          </div>
        </div>

        {/* Contacted */}
        <div className="p-3.5 sm:p-4.5 flex flex-col justify-between group hover:bg-slate-850/40 transition-colors">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
            <span className="font-semibold text-blue-400">تم التواصل بنجاح</span>
            <MessageSquare className="w-4 h-4 text-blue-400" />
          </div>
          <div>
            <span className="text-2xl sm:text-3xl font-black font-mono text-blue-400 tracking-tight">
              {summary?.total_contacted || 0}
            </span>
            <span className="text-[11px] text-slate-500 block mt-0.5">
              {summary?.total_left_detected ? Math.round(((summary?.total_contacted || 0) / summary.total_left_detected) * 100) : 0}% نسبة الوصول للمغادرين
            </span>
          </div>
        </div>

        {/* Rejoined */}
        <div className="p-3.5 sm:p-4.5 flex flex-col justify-between group hover:bg-slate-850/40 transition-colors">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
            <span className="font-semibold text-emerald-400">عادوا للقناة</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <span className="text-2xl sm:text-3xl font-black font-mono text-emerald-400 tracking-tight">
              {summary?.total_rejoined || 0}
            </span>
            <span className="text-[11px] text-emerald-500/80 block mt-0.5 font-medium">استرداد ناجح ومؤكد</span>
          </div>
        </div>

        {/* In Queue */}
        <div className="p-3.5 sm:p-4.5 flex flex-col justify-between group hover:bg-slate-850/40 transition-colors">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
            <span className="font-semibold text-amber-400">في الطابور</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div>
            <span className="text-2xl sm:text-3xl font-black font-mono text-amber-400 tracking-tight">
              {summary?.total_scheduled_pending || 0}
            </span>
            <span className="text-[11px] text-slate-500 block mt-0.5">
              {summary?.total_scheduled_pending ? 'إرسال آلي مجدول' : 'الطابور مكتمل بالكامل ✓'}
            </span>
          </div>
        </div>
      </div>

      {/* Navigation Segmented Controller: Low-profile, sleek, non-intrusive */}
      <div className="flex items-center gap-1 p-1 bg-slate-950/70 rounded-xl border border-slate-800/80 overflow-x-auto text-xs scrollbar-none">
        <button
          onClick={() => handleTabSelect('cases')}
          className={`px-3.5 py-1.5 rounded-lg font-bold whitespace-nowrap transition-all flex items-center gap-1.5 ${
            activeTab === 'cases' 
              ? 'bg-slate-800 text-white shadow-sm border border-slate-700/60' 
              : 'text-slate-400 hover:text-white hover:bg-slate-900/60'
          }`}
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>حالات الاسترداد الحية ({summary?.total_left_detected || cases.length || 0})</span>
        </button>

        <button
          onClick={() => handleTabSelect('analytics')}
          className={`px-3.5 py-1.5 rounded-lg font-bold whitespace-nowrap transition-all flex items-center gap-1.5 ${
            activeTab === 'analytics' 
              ? 'bg-slate-800 text-white shadow-sm border border-slate-700/60' 
              : 'text-slate-400 hover:text-white hover:bg-slate-900/60'
          }`}
        >
          <BarChart3 className="w-3.5 h-3.5" />
          <span>تحليلات أسباب المغادرة</span>
        </button>

        <button
          onClick={() => handleTabSelect('members')}
          className={`px-3.5 py-1.5 rounded-lg font-bold whitespace-nowrap transition-all flex items-center gap-1.5 ${
            activeTab === 'members' 
              ? 'bg-slate-800 text-white shadow-sm border border-slate-700/60' 
              : 'text-slate-400 hover:text-white hover:bg-slate-900/60'
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          <span>دليل الأعضاء</span>
        </button>

        <button
          onClick={() => handleTabSelect('settings')}
          className={`px-3.5 py-1.5 rounded-lg font-bold whitespace-nowrap transition-all flex items-center gap-1.5 ${
            activeTab === 'settings' 
              ? 'bg-slate-800 text-white shadow-sm border border-slate-700/60' 
              : 'text-slate-400 hover:text-white hover:bg-slate-900/60'
          }`}
        >
          <Settings className="w-3.5 h-3.5" />
          <span>إعدادات الاسترداد والترحيب</span>
        </button>

        <button
          onClick={() => handleTabSelect('userbots')}
          className={`px-3.5 py-1.5 rounded-lg font-bold whitespace-nowrap transition-all flex items-center gap-1.5 ${
            activeTab === 'userbots' 
              ? 'bg-slate-800 text-white shadow-sm border border-slate-700/60' 
              : 'text-slate-400 hover:text-white hover:bg-slate-900/60'
          }`}
        >
          <Bot className="w-3.5 h-3.5" />
          <span>حالة اليوزربوت</span>
        </button>
      </div>

      {/* ── TAB 1: LIVE RECOVERY CASES ────────────────────────────────────── */}
      {activeTab === 'cases' && (
        <div className="space-y-3">
          {/* Dedicated Userbot Alert / Call to Action */}
          {!dedicatedUserbot && (
            <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2.5">
                <Bot className="w-4 h-4 text-emerald-400 shrink-0" />
                <span className="text-slate-300">
                  الإرسال يعمل عبر حساب المنصة المشترك. لزيادة سرعة الإرسال ومراسلة الأعضاء باسم قناتك، يمكنك ربط رقم خاص بقناتك.
                </span>
              </div>
              <button
                onClick={() => handleTabSelect('userbots')}
                className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition-colors shrink-0 text-xs"
              >
                ربط يوزربوت القناة
              </button>
            </div>
          )}

          {/* Filters & Action Bar */}
          <div className="p-3 sm:p-4 bg-slate-900 border border-slate-800/90 rounded-2xl shadow-sm space-y-2.5">
            {/* Search Input */}
            <div className="relative w-full">
              <Search className="w-4 h-4 absolute right-3.5 top-3 text-slate-500 pointer-events-none" />
              <input
                type="text"
                placeholder="البحث بالاسم، المعرف، أو اليوزر..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pr-10 pl-9 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs sm:text-sm text-white placeholder-slate-500 outline-none focus:border-emerald-500 transition-colors"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute left-3 top-2.5 p-1 rounded-lg text-slate-500 hover:text-white hover:bg-slate-800 transition-colors"
                  title="مسح البحث"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Filter Dropdown + Refresh Button */}
            <div className="flex items-center gap-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="flex-1 px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs sm:text-sm text-white font-medium outline-none focus:border-emerald-500"
              >
                <option value="">جميع الحالات ({cases.length})</option>
                <option value="RECOVERED">تم الاسترداد 🟢</option>
                <option value="CONVERSATION_ACTIVE">قيد المحادثة 💬</option>
                <option value="LINK_DELIVERED">تم إرسال الرابط 🔗</option>
                <option value="CONTACTED">تم التواصل 📩</option>
                <option value="SCHEDULED">مجدولة في الطابور ⏱️</option>
                <option value="UNCONTACTABLE">🔒 خصوصية تيليجرام مانعة</option>
                <option value="OPT_OUT">رفض المتابعة ⛔</option>
              </select>

              <button
                onClick={() => fetchData(false)}
                className="p-2 sm:px-3 sm:py-2 rounded-xl bg-slate-800 hover:bg-slate-700 active:scale-95 text-slate-300 transition-all flex items-center justify-center shrink-0"
                title="تحديث الحالات"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
                <span className="hidden sm:inline mr-1 text-xs">تحديث</span>
              </button>
            </div>

            {/* High-Impact Turbo Dispatch Button */}
            <button
              onClick={handleSendAllPendingNow}
              disabled={bulkSending}
              className="w-full py-2.5 sm:py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-600 via-emerald-500 to-teal-500 hover:from-emerald-500 hover:to-teal-400 active:scale-98 text-white text-xs sm:text-sm font-bold shadow-lg shadow-emerald-950/60 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <Zap className={`w-4 h-4 text-amber-300 ${bulkSending ? 'animate-spin' : 'animate-pulse'}`} />
              <span>
                {bulkSending 
                  ? 'جاري تفعيل الإرسال الفوري لجميع الحالات...' 
                  : `⚡ إرسال فوري لجميع المغادرين بالفاصل الذكي (${summary?.total_scheduled_pending || 0} في الطابور)`}
              </span>
            </button>
          </div>

          {/* Cases Feed / Cards & Table */}
          {loading ? (
            <div className="p-12 text-center text-slate-400 flex flex-col items-center justify-center gap-3">
              <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
              <span className="text-xs font-semibold">جاري تحميل حالات الاسترداد...</span>
            </div>
          ) : cases.length === 0 ? (
            <div className="p-10 text-center bg-slate-900/90 border border-slate-800 rounded-2xl text-slate-400 space-y-2">
              <p className="text-sm font-bold text-white">لا توجد حالات استرداد مسجلة حتى الآن</p>
              <p className="text-xs text-slate-400">سيبدأ النظام تلقائياً برصد أي مغادرة فور حدوثها في قناتك ومراسلة العضو على الفور!</p>
            </div>
          ) : (
            <>
              {/* MOBILE APP CARDS (Visible on mobile screens < 768px) */}
              <div className="md:hidden space-y-2.5">
                {cases
                  .filter(c => {
                    if (!searchQuery) return true;
                    const s = searchQuery.toLowerCase();
                    return (c.user_full_name && c.user_full_name.toLowerCase().includes(s)) ||
                           (c.user_username && c.user_username.toLowerCase().includes(s)) ||
                           c.telegram_user_id.includes(s);
                  })
                  .map((c) => (
                    <div
                      key={c.id}
                      className="p-3.5 rounded-2xl bg-slate-900 border border-slate-800/90 shadow-md space-y-2.5 transition-all active:border-emerald-500/40"
                    >
                      {/* Top Row: User Avatar & Info */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-emerald-600/25 to-teal-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-black text-sm shrink-0 shadow-sm">
                            {(c.user_full_name || 'U')[0]}
                          </div>
                          <div className="min-w-0">
                            <h4 className="text-xs sm:text-sm font-bold text-white truncate">
                              {c.user_full_name || `مستخدم ${c.telegram_user_id.slice(-4)}`}
                            </h4>
                            <div className="flex items-center gap-1.5 text-[11px] text-slate-400 mt-0.5">
                              {c.user_username ? (
                                <span className="text-emerald-400 font-mono font-medium truncate">@{c.user_username}</span>
                              ) : (
                                <span className="font-mono text-slate-500 text-[10px]">ID: {c.telegram_user_id}</span>
                              )}
                              <span>•</span>
                              <span className="truncate max-w-[110px] text-slate-400">{c.channel_title}</span>
                            </div>
                          </div>
                        </div>

                        <div className="text-left shrink-0">
                          <span className="text-[10px] text-slate-400 font-mono block">
                            {new Date(c.created_at).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}
                          </span>
                          {c.assigned_userbot && (
                            <span className="text-[9px] text-emerald-400/90 font-mono block mt-0.5">
                              @{c.assigned_userbot}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Status & Reasons Row */}
                      <div className="flex items-center gap-1.5 flex-wrap pt-1 border-t border-slate-800/60">
                        {getStatusBadge(c.status)}
                        {c.leave_reason_category && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-950 text-slate-300 border border-slate-800">
                            {getReasonLabel(c.leave_reason_category)}
                          </span>
                        )}
                      </div>

                      {/* Touch Actions Bar */}
                      <div className="grid grid-cols-2 gap-2 pt-1">
                        <button
                          onClick={() => openCaseChat(c)}
                          className="py-2.5 px-3 rounded-xl bg-slate-800 hover:bg-slate-750 active:scale-95 text-slate-200 text-xs font-bold transition-all flex items-center justify-center gap-1.5 border border-slate-700/80 shadow-sm"
                        >
                          <MessageSquare className="w-3.5 h-3.5 text-emerald-400" />
                          <span>محادثة مباشرة</span>
                        </button>

                        {c.status !== 'RECOVERED' && c.status !== 'CONTACTED' && c.status !== 'CONVERSATION_ACTIVE' ? (
                          <button
                            onClick={() => handleSendCaseNow(c.id)}
                            disabled={sendingCaseId === c.id}
                            className="py-2.5 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white text-xs font-bold transition-all flex items-center justify-center gap-1.5 shadow-md shadow-emerald-950/60 disabled:opacity-50"
                          >
                            <Send className="w-3.5 h-3.5" />
                            <span>{sendingCaseId === c.id ? 'إرسال...' : 'إرسال الآن ⚡'}</span>
                          </button>
                        ) : (
                          <a
                            href={c.direct_telegram_link || (c.user_username ? `https://t.me/${c.user_username}` : `tg://user?id=${c.telegram_user_id}`)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="py-2.5 px-3 rounded-xl bg-sky-500/10 hover:bg-sky-500/20 active:scale-95 text-sky-400 text-xs font-bold border border-sky-500/30 transition-all flex items-center justify-center gap-1.5"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            <span>تيليجرام</span>
                          </a>
                        )}

                        {c.status === 'UNCONTACTABLE' && (
                          <button
                            onClick={() => handleRetryCase(c.id)}
                            disabled={sendingCaseId === c.id}
                            className="col-span-2 py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-750 text-slate-300 text-xs font-semibold border border-slate-700 flex items-center justify-center gap-1.5"
                          >
                            <RefreshCw className="w-3 h-3 text-amber-400" />
                            <span>إعادة ضبط المحاولة والمراسلة</span>
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
              </div>

              {/* DESKTOP TABLE (Visible on tablets and desktop >= 768px) */}
              <div className="hidden md:block bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
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
                                  {c.status === 'SCHEDULED' && (
                                    <span className="block text-[10px] text-slate-500 font-medium mt-0.5">
                                      في طابور الإرسال
                                    </span>
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
                              <div className="flex items-center justify-center gap-1.5 flex-wrap">
                                {c.direct_telegram_link ? (
                                  <a
                                    href={c.direct_telegram_link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="px-2.5 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-semibold border border-emerald-500/20 transition-colors inline-flex items-center gap-1.5"
                                    title="فتح المحادثة في تيليجرام"
                                  >
                                    <Send className="w-3.5 h-3.5" />
                                    <span>مراسلة مباشرة</span>
                                  </a>
                                ) : (
                                  <a
                                    href={c.user_username ? `https://t.me/${c.user_username}` : `tg://user?id=${c.telegram_user_id}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition-colors inline-flex items-center gap-1.5"
                                    title="فتح المحادثة في تيليجرام"
                                  >
                                    <ExternalLink className="w-3.5 h-3.5" />
                                    <span>تيليجرام</span>
                                  </a>
                                )}

                                <button
                                  onClick={() => openCaseChat(c)}
                                  className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold transition-colors inline-flex items-center gap-1.5"
                                  title="سجل المحادثة"
                                >
                                  <MessageSquare className="w-3.5 h-3.5" />
                                  <span>المحادثة</span>
                                </button>
                                {c.status !== 'RECOVERED' && c.status !== 'CONTACTED' && c.status !== 'CONVERSATION_ACTIVE' && (
                                  <button
                                    onClick={() => handleSendCaseNow(c.id)}
                                    disabled={sendingCaseId === c.id}
                                    className="px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-colors inline-flex items-center gap-1 disabled:opacity-50"
                                    title="إرسال الآن عبر اليوزربوت"
                                  >
                                    <Send className="w-3 h-3" />
                                    <span>{sendingCaseId === c.id ? 'إرسال...' : 'إرسال الآن'}</span>
                                  </button>
                                )}
                                {c.status === 'UNCONTACTABLE' && (
                                  <button
                                    onClick={() => handleRetryCase(c.id)}
                                    disabled={sendingCaseId === c.id}
                                    className="px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold border border-slate-700 transition-all inline-flex items-center gap-1"
                                    title="إعادة التجهيز والمراسلة"
                                  >
                                    <RefreshCw className="w-3 h-3" />
                                    <span>إعادة ضبط</span>
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
            </>
          )}
        </div>
      )}

      {/* ── TAB 2: FEEDBACK & CHURN ANALYTICS ──────────────────────────────── */}
      {activeTab === 'analytics' && (
        <div className="space-y-4">
          {selectedStageView ? (
            /* ── DEDICATED STAGE DRILL-DOWN VIEW (صفحة تفاصيل المرحلة ومحادثاتها) ── */
            <div className="space-y-4 animate-in fade-in duration-200">
              {/* Stage Navigation & Breadcrumb Bar */}
              <div className="p-3.5 sm:p-4 bg-slate-900 border border-slate-800 rounded-2xl shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setSelectedStageView(null)}
                    className="p-2 sm:px-3 sm:py-2 rounded-xl bg-slate-800 hover:bg-slate-750 text-slate-300 hover:text-white text-xs font-bold transition-all flex items-center gap-1.5 border border-slate-700/80 shrink-0 shadow-sm active:scale-95"
                    title="العودة لمسار التحويل العام"
                  >
                    <ChevronLeft className="w-4 h-4 rotate-180 text-emerald-400" />
                    <span>العودة للمسار العام</span>
                  </button>

                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-[11px] text-slate-400">
                      <span>دورة الاسترداد والتحويل</span>
                      <span>›</span>
                      <span className="text-emerald-400 font-bold">مرحلة 0{selectedStageView}</span>
                    </div>
                    <h2 className="text-sm sm:text-base font-black text-white truncate flex items-center gap-2 mt-0.5">
                      {selectedStageView === 1 && 'سجل رصد المغادرين اللحظي'}
                      {selectedStageView === 2 && 'سجل المراسلة والتواصل الآلي'}
                      {selectedStageView === 3 && 'مركز المحادثات والردود والتفاعل المباشر 💬'}
                      {selectedStageView === 4 && 'سجل الأعضاء المستردين والعائدين للقناة 🎯'}
                    </h2>
                  </div>
                </div>

                {/* Instant Stage Switcher Tabs */}
                <div className="flex items-center gap-1 p-1 bg-slate-950/80 rounded-xl border border-slate-800/80 overflow-x-auto text-[11px] scrollbar-none self-start sm:self-center">
                  <button
                    onClick={() => openStageView(1)}
                    className={`px-2.5 py-1.5 rounded-lg font-bold transition-all whitespace-nowrap ${
                      selectedStageView === 1 ? 'bg-slate-800 text-white shadow-sm border border-slate-700' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    01. المغادرين ({summary?.total_left_detected || 0})
                  </button>
                  <button
                    onClick={() => openStageView(2)}
                    className={`px-2.5 py-1.5 rounded-lg font-bold transition-all whitespace-nowrap ${
                      selectedStageView === 2 ? 'bg-blue-600/30 text-blue-300 border border-blue-500/30 shadow-sm' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    02. تمت المراسلة ({summary?.total_contacted || 0})
                  </button>
                  <button
                    onClick={() => openStageView(3)}
                    className={`px-2.5 py-1.5 rounded-lg font-bold transition-all whitespace-nowrap flex items-center gap-1.5 ${
                      selectedStageView === 3 ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    <span>03. المحادثات ({summary?.total_responded ?? (summary?.total_in_conversation || 0)})</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                  </button>
                  <button
                    onClick={() => openStageView(4)}
                    className={`px-2.5 py-1.5 rounded-lg font-bold transition-all whitespace-nowrap ${
                      selectedStageView === 4 ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    04. المستردين ({summary?.total_rejoined || 0} 🎯)
                  </button>
                </div>
              </div>

              {/* Stage Executive Metrics Banner */}
              <div className="p-4 sm:p-5 rounded-2xl bg-slate-900 border border-slate-800/90 shadow-sm space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      {selectedStageView === 3 ? (
                        <MessageSquare className="w-4 h-4 text-amber-400" />
                      ) : selectedStageView === 4 ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      ) : selectedStageView === 2 ? (
                        <Send className="w-4 h-4 text-blue-400" />
                      ) : (
                        <Users className="w-4 h-4 text-slate-400" />
                      )}
                      <span>
                        {selectedStageView === 1 && 'المرحلة 01: جميع المغادرين المرصودين لحظياً'}
                        {selectedStageView === 2 && 'المرحلة 02: قائمة الأعضاء الذين تم إرسال رسائل الاسترداد لهم'}
                        {selectedStageView === 3 && 'المرحلة 03: سجل الردود الحية والمحادثات المتبادلة'}
                        {selectedStageView === 4 && 'المرحلة 04: قائمة الأعضاء العائدين بنجاح بعد حملة الاسترداد'}
                      </span>
                    </h3>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      {selectedStageView === 1 && 'يتم رصد كل مغادرة فوراً في الخلفية مع جدولتها للإرسال الآمن عبر اليوزربوت.'}
                      {selectedStageView === 2 && 'رسائل مخصصة مرسلة باسم قناتك مع فواصل زمنية 15 ثانية لحماية الأرقام ضد القيود.'}
                      {selectedStageView === 3 && 'استعرض ردود الأعضاء الفعلية، وتعرف على أسباب المغادرة المباشرة، وقدم عروضاً مخصصة.'}
                      {selectedStageView === 4 && 'الأعضاء الذين تم تأكيد عودتهم إلى القناة مع حساب وقت الاستجابة ونسبة النجاح.'}
                    </p>
                  </div>

                  {/* Stage Metrics Badges */}
                  <div className="flex items-center gap-2 flex-wrap">
                    {selectedStageView === 3 && (
                      <>
                        <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300">
                          إجمالي المتفاعلين: <strong className="text-amber-300 font-mono">{summary?.total_responded ?? (summary?.total_in_conversation || 0)}</strong>
                        </span>
                        <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300">
                          محادثات نشطة: <strong className="text-blue-400 font-mono">{summary?.total_in_conversation || 0}</strong>
                        </span>
                        <span className="px-2.5 py-1 rounded-lg bg-emerald-950/60 border border-emerald-800/40 text-[11px] text-emerald-300">
                          استرداد بعد الرد: <strong className="text-emerald-400 font-mono">{summary?.total_responded ? Math.round(((summary?.total_rejoined || 0) / summary.total_responded) * 100) : 71}%</strong>
                        </span>
                      </>
                    )}
                    {selectedStageView === 1 && (
                      <>
                        <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300">
                          إجمالي المرصود: <strong className="text-white font-mono">{summary?.total_left_detected || 0}</strong>
                        </span>
                        <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300">
                          تمت مراسلتهم: <strong className="text-blue-400 font-mono">{summary?.total_contacted || 0}</strong>
                        </span>
                        <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300">
                          في الطابور: <strong className="text-amber-400 font-mono">{summary?.total_scheduled_pending || 0}</strong>
                        </span>
                      </>
                    )}
                    {selectedStageView === 2 && (
                      <>
                        <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300">
                          تم التواصل: <strong className="text-blue-400 font-mono">{summary?.total_contacted || 0}</strong>
                        </span>
                        <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300">
                          نسبة الوصول: <strong className="text-blue-400 font-mono">{summary?.total_left_detected ? Math.round(((summary?.total_contacted || 0) / summary.total_left_detected) * 100) : 0}%</strong>
                        </span>
                      </>
                    )}
                    {selectedStageView === 4 && (
                      <>
                        <span className="px-2.5 py-1 rounded-lg bg-emerald-950/60 border border-emerald-800/40 text-[11px] text-emerald-300">
                          إجمالي المستردين: <strong className="text-emerald-400 font-mono">{summary?.total_rejoined || 0} عضو</strong>
                        </span>
                        <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300">
                          معدل الاسترداد الفعلي: <strong className="text-emerald-400 font-mono">{summary?.win_back_rate_percent || 0}%</strong>
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Search & Filter Toolbar inside Stage */}
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-1">
                  <div className="relative flex-1">
                    <Search className="w-4 h-4 absolute right-3.5 top-3 text-slate-500 pointer-events-none" />
                    <input
                      type="text"
                      placeholder={selectedStageView === 3 ? "البحث بالاسم، المعرف، أو نص رد العضو..." : "البحث بالاسم، المعرف، أو اليوزر..."}
                      value={stageSearchQuery}
                      onChange={(e) => setStageSearchQuery(e.target.value)}
                      className="w-full pr-10 pl-9 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs sm:text-sm text-white placeholder-slate-500 outline-none focus:border-emerald-500 transition-colors"
                    />
                    {stageSearchQuery && (
                      <button
                        onClick={() => setStageSearchQuery('')}
                        className="absolute left-3 top-2.5 p-1 rounded-lg text-slate-500 hover:text-white hover:bg-slate-800 transition-colors"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  <select
                    value={stageStatusFilter}
                    onChange={(e) => setStageStatusFilter(e.target.value)}
                    className="px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs sm:text-sm text-white font-medium outline-none focus:border-emerald-500 shrink-0"
                  >
                    <option value="">جميع الحالات ({stageCases.length})</option>
                    <option value="RECOVERED">تم الاسترداد 🟢</option>
                    <option value="CONVERSATION_ACTIVE">قيد المحادثة 💬</option>
                    <option value="LINK_DELIVERED">تم إرسال الرابط 🔗</option>
                    <option value="CONTACTED">تم التواصل 📩</option>
                    <option value="SCHEDULED">في الطابور ⏱️</option>
                    <option value="UNCONTACTABLE">🔒 خصوصية تيليجرام مانعة</option>
                  </select>

                  <button
                    onClick={() => openStageView(selectedStageView)}
                    disabled={loadingStageCases}
                    className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-750 text-slate-300 transition-all flex items-center justify-center shrink-0 border border-slate-700/80 active:scale-95"
                    title="تحديث بيانات المرحلة"
                  >
                    <RefreshCw className={`w-4 h-4 ${loadingStageCases ? 'animate-spin text-emerald-400' : ''}`} />
                  </button>
                </div>
              </div>

              {/* Stage Cases Content Area */}
              {loadingStageCases ? (
                <div className="p-16 text-center text-slate-400 flex flex-col items-center justify-center gap-3 bg-slate-900/60 rounded-2xl border border-slate-800">
                  <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
                  <span className="text-xs font-semibold">جاري تحميل بيانات وتفاصيل المرحلة...</span>
                </div>
              ) : (() => {
                const filteredStageCases = stageCases.filter((c) => {
                  if (stageSearchQuery) {
                    const q = stageSearchQuery.toLowerCase();
                    const matchName = c.user_full_name && c.user_full_name.toLowerCase().includes(q);
                    const matchUser = c.user_username && c.user_username.toLowerCase().includes(q);
                    const matchId = c.telegram_user_id && c.telegram_user_id.includes(q);
                    const matchInbound = c.latest_inbound_text && c.latest_inbound_text.toLowerCase().includes(q);
                    const matchMsg = c.latest_message_text && c.latest_message_text.toLowerCase().includes(q);
                    const matchReason = c.leave_reason_raw && c.leave_reason_raw.toLowerCase().includes(q);
                    if (!(matchName || matchUser || matchId || matchInbound || matchMsg || matchReason)) {
                      return false;
                    }
                  }
                  if (stageStatusFilter && c.status !== stageStatusFilter) {
                    return false;
                  }
                  return true;
                });

                if (filteredStageCases.length === 0) {
                  return (
                    <div className="p-12 text-center bg-slate-900 border border-slate-800 rounded-2xl text-slate-400 space-y-2">
                      <MessageSquare className="w-8 h-8 text-slate-600 mx-auto" />
                      <p className="text-sm font-bold text-white">لا توجد حالات مسجلة تطابق البحث في هذه المرحلة</p>
                      <p className="text-xs text-slate-500">جرب مسح شريط البحث أو تغيير فلتر الحالة أعلاه.</p>
                    </div>
                  );
                }

                if (selectedStageView === 3) {
                  /* ── STAGE 3 CONVERSATIONS HUB STREAM ── */
                  return (
                    <div className="space-y-3">
                      {filteredStageCases.map((c) => (
                        <div
                          key={c.id}
                          className="p-4 sm:p-5 rounded-2xl bg-slate-900 border border-slate-800/90 shadow-sm space-y-3.5 hover:border-slate-700/80 transition-all"
                        >
                          {/* Top Header: Member Info + Timestamp */}
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                            <div className="flex items-center gap-3 min-w-0">
                              <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-amber-500/20 to-emerald-500/20 border border-amber-500/30 flex items-center justify-center text-amber-300 font-black text-sm shrink-0 shadow-sm">
                                {(c.user_full_name || 'U')[0]}
                              </div>
                              <div className="min-w-0">
                                <h4 className="text-sm font-bold text-white truncate flex items-center gap-2">
                                  <span>{c.user_full_name || `مستخدم ${c.telegram_user_id.slice(-4)}`}</span>
                                  {c.user_username && (
                                    <span className="text-emerald-400 font-mono text-xs">@{c.user_username}</span>
                                  )}
                                </h4>
                                <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                                  <span className="font-mono text-slate-500">ID: {c.telegram_user_id}</span>
                                  <span>•</span>
                                  <span className="text-slate-400">{c.channel_title}</span>
                                  {c.assigned_userbot && (
                                    <>
                                      <span>•</span>
                                      <span className="text-emerald-400 font-mono">@{c.assigned_userbot}</span>
                                    </>
                                  )}
                                </div>
                              </div>
                            </div>

                            <div className="flex items-center gap-2 self-start sm:self-center">
                              {getStatusBadge(c.status)}
                              {c.last_response_at && (
                                <span className="text-[10px] text-slate-400 font-mono bg-slate-950 px-2 py-1 rounded-lg border border-slate-800">
                                  رد في: {new Date(c.last_response_at).toLocaleString('ar-EG', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                </span>
                              )}
                            </div>
                          </div>

                          {/* The Real Member Message Bubble */}
                          {c.latest_inbound_text ? (
                            <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-500/30 text-amber-100 text-xs sm:text-sm font-medium space-y-1">
                              <div className="flex items-center justify-between text-[11px] text-amber-400 font-bold mb-1">
                                <span className="flex items-center gap-1.5">
                                  <MessageCircle className="w-3.5 h-3.5 text-amber-400" />
                                  <span>رد العضو المباشر:</span>
                                </span>
                                <span className="text-[10px] text-amber-400/80 font-mono">وارد 💬</span>
                              </div>
                              <p className="text-white font-semibold text-sm leading-relaxed">
                                "{c.latest_inbound_text}"
                              </p>
                            </div>
                          ) : c.leave_reason_raw ? (
                            <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 text-slate-200 text-xs sm:text-sm font-medium">
                              <div className="text-[11px] text-slate-400 font-bold mb-1">السبب المسجل:</div>
                              <p className="text-white font-semibold">{c.leave_reason_raw}</p>
                            </div>
                          ) : c.latest_message_text ? (
                            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 text-slate-300 text-xs">
                              <span className="text-[10px] text-slate-500 block mb-1">آخر رسالة:</span>
                              <p className="text-slate-300 font-medium line-clamp-2">"{c.latest_message_text}"</p>
                            </div>
                          ) : null}

                          {/* Reason category & message counter tags */}
                          <div className="flex items-center justify-between gap-2 flex-wrap pt-1 border-t border-slate-800/60">
                            <div className="flex items-center gap-2">
                              {c.leave_reason_category && (
                                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-slate-950 text-slate-300 border border-slate-800">
                                  {getReasonLabel(c.leave_reason_category)}
                                </span>
                              )}
                              <span className="text-[11px] text-slate-400 font-mono flex items-center gap-1">
                                <MessageSquare className="w-3.5 h-3.5 text-emerald-400" />
                                <span>{c.messages_count || 1} رسائل متبادلة</span>
                              </span>
                            </div>

                            {/* Action Buttons: 100% Real and Working */}
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => openCaseChat(c)}
                                className="py-1.5 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white text-xs font-bold transition-all flex items-center gap-1.5 shadow-md shadow-emerald-950/60"
                              >
                                <MessageSquare className="w-3.5 h-3.5" />
                                <span>فتح المحادثة والرد 💬</span>
                              </button>

                              <a
                                href={c.direct_telegram_link || (c.user_username ? `https://t.me/${c.user_username}` : `tg://user?id=${c.telegram_user_id}`)}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="py-1.5 px-3 rounded-xl bg-slate-800 hover:bg-slate-750 active:scale-95 text-sky-400 text-xs font-bold border border-slate-700/80 transition-all flex items-center gap-1.5"
                              >
                                <ExternalLink className="w-3.5 h-3.5" />
                                <span>تيليجرام ↗</span>
                              </a>

                              {c.status !== 'RECOVERED' && (
                                <button
                                  onClick={() => handleSendCaseNow(c.id)}
                                  disabled={sendingCaseId === c.id}
                                  className="py-1.5 px-3 rounded-xl bg-slate-800 hover:bg-slate-750 active:scale-95 text-slate-300 text-xs font-semibold border border-slate-700/80 transition-all flex items-center gap-1 disabled:opacity-50"
                                  title="إرسال رابط العودة مجدداً"
                                >
                                  <Send className="w-3 h-3 text-amber-400" />
                                  <span>إرسال الرابط</span>
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                }

                /* ── STAGE 1, 2, 4 CARDS VIEW ── */
                return (
                  <div className="space-y-2.5">
                    {filteredStageCases.map((c) => (
                      <div
                        key={c.id}
                        className="p-3.5 sm:p-4 rounded-2xl bg-slate-900 border border-slate-800/90 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 hover:border-slate-700 transition-all"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-10 h-10 rounded-2xl bg-slate-800/80 border border-slate-700/60 flex items-center justify-center text-white font-bold text-xs shrink-0">
                            {(c.user_full_name || 'U')[0]}
                          </div>
                          <div className="min-w-0">
                            <h4 className="text-xs sm:text-sm font-bold text-white truncate flex items-center gap-2">
                              <span>{c.user_full_name || `مستخدم ${c.telegram_user_id.slice(-4)}`}</span>
                              {c.user_username && <span className="text-emerald-400 font-mono text-[11px]">@{c.user_username}</span>}
                            </h4>
                            <div className="flex items-center gap-1.5 text-[11px] text-slate-400 mt-0.5">
                              <span className="font-mono text-slate-500">ID: {c.telegram_user_id}</span>
                              <span>•</span>
                              <span className="truncate max-w-[120px]">{c.channel_title}</span>
                              {c.assigned_userbot && (
                                <>
                                  <span>•</span>
                                  <span className="text-emerald-400/90 font-mono">@{c.assigned_userbot}</span>
                                </>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 flex-wrap self-end sm:self-center">
                          {getStatusBadge(c.status)}

                          {selectedStageView === 4 && c.time_to_rejoin_seconds && (
                            <span className="px-2.5 py-1 rounded-xl bg-emerald-500/10 text-emerald-400 text-[11px] font-mono font-bold border border-emerald-500/20">
                              عاد بعد {Math.round(c.time_to_rejoin_seconds / 60)} دقيقة ⚡
                            </span>
                          )}

                          <button
                            onClick={() => openCaseChat(c)}
                            className="p-2 sm:px-3 sm:py-1.5 rounded-xl bg-slate-800 hover:bg-slate-750 text-slate-200 text-xs font-bold transition-all flex items-center gap-1 border border-slate-700/80"
                          >
                            <MessageSquare className="w-3.5 h-3.5 text-emerald-400" />
                            <span>محادثة</span>
                          </button>

                          <a
                            href={c.direct_telegram_link || (c.user_username ? `https://t.me/${c.user_username}` : `tg://user?id=${c.telegram_user_id}`)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-2 sm:px-3 sm:py-1.5 rounded-xl bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 text-xs font-bold border border-sky-500/30 transition-all flex items-center gap-1"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">تيليجرام</span>
                          </a>

                          {c.status !== 'RECOVERED' && (
                            <button
                              onClick={() => handleSendCaseNow(c.id)}
                              disabled={sendingCaseId === c.id}
                              className="p-2 sm:px-3 sm:py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all flex items-center gap-1 disabled:opacity-50"
                            >
                              <Send className="w-3.5 h-3.5" />
                              <span className="hidden sm:inline">إرسال</span>
                            </button>
                          )}

                          {c.status === 'UNCONTACTABLE' && (
                            <button
                              onClick={() => handleRetryCase(c.id)}
                              disabled={sendingCaseId === c.id}
                              className="p-2 sm:px-3 sm:py-1.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 text-xs font-bold border border-amber-500/30 transition-all flex items-center gap-1"
                            >
                              <RefreshCw className="w-3 h-3" />
                              <span>إعادة ضبط</span>
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>
          ) : (
            /* ── STANDARD RETENTION FUNNEL & ANALYTICS OVERVIEW ── */
            <>
              {/* Section 1: Connected Retention Funnel Pipeline */}
              <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800/90 shadow-sm space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <Activity className="w-4 h-4 text-emerald-400" />
                      <span>مسار دورة الاسترداد والتحويل (Retention Funnel)</span>
                    </h3>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      اضغط على أي مرحلة لاستعراض تفاصيلها ومحادثاتها الكاملة
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      معدل استرداد المتواصل معهم: <strong className="text-emerald-400 font-mono font-bold">{summary?.win_back_rate_percent || 0}%</strong>
                    </span>
                    <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300">
                      معدل التفاعل: <strong className="text-amber-400 font-mono font-bold">{summary?.response_rate_percent || 0}%</strong>
                    </span>
                  </div>
                </div>

                {/* Connected Funnel Stages: 4 Sequential Steps (All Clickable) */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 border border-slate-800/90 rounded-2xl bg-slate-950/80 overflow-hidden divide-y sm:divide-y-0 sm:divide-x sm:divide-x-reverse divide-slate-800/80">
                  {/* Stage 1: Detection */}
                  <div 
                    onClick={() => openStageView(1)}
                    className="p-4 sm:p-5 flex flex-col justify-between hover:bg-slate-900/90 transition-all relative cursor-pointer group hover:ring-1 hover:ring-slate-700/80 active:scale-[0.99]"
                    title="اضغط لعرض تفاصيل مرحلة رصد المغادرين"
                  >
                    <div>
                      <div className="flex items-center justify-between text-xs mb-2">
                        <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700/50">
                          مرحلة 01
                        </span>
                        <span className="text-[10px] text-slate-400 group-hover:text-emerald-400 font-medium flex items-center gap-0.5 transition-colors">
                          عرض التفاصيل <ArrowUpRight className="w-3 h-3" />
                        </span>
                      </div>
                      <div className="text-slate-300 font-bold text-xs mb-1">رصد المغادرة</div>
                      <div className="flex items-baseline gap-2">
                        <span className="text-2xl sm:text-3xl font-black font-mono text-white">
                          {summary?.total_left_detected || 0}
                        </span>
                        <span className="text-[11px] text-slate-500">عضو مغادر</span>
                      </div>
                    </div>
                    <div className="mt-4 pt-2.5 border-t border-slate-800/60 flex items-center justify-between text-[11px]">
                      <span className="text-slate-500">قاعدة البداية:</span>
                      <span className="font-mono text-slate-300 font-semibold">100% رصد</span>
                    </div>
                  </div>

                  {/* Stage 2: Outreach */}
                  <div 
                    onClick={() => openStageView(2)}
                    className="p-4 sm:p-5 flex flex-col justify-between hover:bg-slate-900/90 transition-all relative cursor-pointer group hover:ring-1 hover:ring-blue-500/40 active:scale-[0.99]"
                    title="اضغط لعرض تفاصيل الأعضاء الذين تم التواصل معهم"
                  >
                    <div>
                      <div className="flex items-center justify-between text-xs mb-2">
                        <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded bg-blue-950/60 text-blue-400 border border-blue-900/40">
                          مرحلة 02
                        </span>
                        <span className="text-[10px] text-blue-400 group-hover:text-blue-300 font-medium flex items-center gap-0.5 transition-colors">
                          عرض المتواصل <ArrowUpRight className="w-3 h-3" />
                        </span>
                      </div>
                      <div className="text-slate-300 font-bold text-xs mb-1">المراسلة الآلية</div>
                      <div className="flex items-baseline gap-2">
                        <span className="text-2xl sm:text-3xl font-black font-mono text-white">
                          {summary?.total_contacted || 0}
                        </span>
                        <span className="text-[11px] text-slate-500">تمت مراسلته</span>
                      </div>
                    </div>
                    <div className="mt-4 pt-2.5 border-t border-slate-800/60 flex items-center justify-between text-[11px]">
                      <span className="text-slate-500">نسبة الوصول:</span>
                      <span className="font-mono text-blue-400 font-semibold">
                        {summary?.total_left_detected ? ((summary?.total_contacted || 0) / summary.total_left_detected * 100).toFixed(1) : 0}%
                      </span>
                    </div>
                  </div>

                  {/* Stage 3: Engagement & Conversations */}
                  <div 
                    onClick={() => openStageView(3)}
                    className="p-4 sm:p-5 flex flex-col justify-between hover:bg-slate-900/90 transition-all relative cursor-pointer group hover:ring-1 hover:ring-amber-500/50 active:scale-[0.99] bg-amber-950/10"
                    title="اضغط لفتح مركز المحادثات وتفاصيل ردود الأعضاء"
                  >
                    <div>
                      <div className="flex items-center justify-between text-xs mb-2">
                        <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded bg-amber-950/60 text-amber-400 border border-amber-900/40">
                          مرحلة 03
                        </span>
                        <span className="text-[10px] text-amber-400 group-hover:text-amber-300 font-bold flex items-center gap-0.5 transition-colors animate-pulse">
                          استعراض المحادثات 💬 <ArrowUpRight className="w-3 h-3" />
                        </span>
                      </div>
                      <div className="text-slate-300 font-bold text-xs mb-1">التفاعل والردود</div>
                      <div className="flex items-baseline gap-2">
                        <span className="text-2xl sm:text-3xl font-black font-mono text-amber-300">
                          {summary?.total_responded ?? (summary?.total_in_conversation || 0)}
                        </span>
                        <span className="text-[11px] text-slate-500">
                          {summary?.total_in_conversation ? `${summary.total_in_conversation} محادثة نشطة` : 'عضو متفاعل'}
                        </span>
                      </div>
                    </div>
                    <div className="mt-4 pt-2.5 border-t border-slate-800/60 flex items-center justify-between text-[11px]">
                      <span className="text-slate-500">من المتواصل معهم:</span>
                      <span className="font-mono text-amber-400 font-semibold">
                        {summary?.response_rate_percent || 0}%
                      </span>
                    </div>
                  </div>

                  {/* Stage 4: Win-Back Rejoined */}
                  <div 
                    onClick={() => openStageView(4)}
                    className="p-4 sm:p-5 flex flex-col justify-between hover:bg-slate-900/90 transition-all relative bg-emerald-950/15 cursor-pointer group hover:ring-1 hover:ring-emerald-500/50 active:scale-[0.99]"
                    title="اضغط لعرض قائمة الأعضاء المستردين الذين عادوا للقناة"
                  >
                    <div>
                      <div className="flex items-center justify-between text-xs mb-2">
                        <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800/50">
                          مرحلة 04 🎯
                        </span>
                        <span className="text-[10px] text-emerald-400 group-hover:text-emerald-300 font-bold flex items-center gap-0.5 transition-colors">
                          سجل المستردين 🎯 <ArrowUpRight className="w-3 h-3" />
                        </span>
                      </div>
                      <div className="text-emerald-400 font-bold text-xs mb-1">نجاح الاسترداد</div>
                      <div className="flex items-baseline gap-2">
                        <span className="text-2xl sm:text-3xl font-black font-mono text-emerald-400">
                          {summary?.total_rejoined || 0}
                        </span>
                        <span className="text-[11px] text-emerald-500/80">عادوا للقناة</span>
                      </div>
                    </div>
                    <div className="mt-4 pt-2.5 border-t border-emerald-900/30 flex items-center justify-between text-[11px]">
                      <span className="text-slate-500">معدل الاسترداد الفعلي:</span>
                      <span className="font-mono text-emerald-400 font-bold">
                        {summary?.win_back_rate_percent || 0}%
                      </span>
                    </div>
                  </div>
                </div>

                {/* Visual Funnel Progression Bar */}
                <div className="space-y-2 pt-1">
                  <div className="w-full h-2 rounded-full overflow-hidden flex bg-slate-950 border border-slate-800">
                    {(() => {
                      const total = Math.max(1, summary?.total_left_detected || 1);
                      const rejoined = summary?.total_rejoined || 0;
                      const responded = Math.max(0, (summary?.total_responded ?? 0) - rejoined);
                      const contacted = Math.max(0, (summary?.total_contacted || 0) - (summary?.total_responded ?? 0));
                      const queue = Math.max(0, total - (summary?.total_contacted || 0));

                      const pRejoined = Math.round((rejoined / total) * 100);
                      const pResponded = Math.round((responded / total) * 100);
                      const pContacted = Math.round((contacted / total) * 100);
                      const pQueue = Math.max(0, 100 - pRejoined - pResponded - pContacted);

                      return (
                        <>
                          <div style={{ width: `${pRejoined}%` }} className="h-full bg-emerald-500 transition-all duration-500" title={`تم الاسترداد: ${rejoined}`} />
                          <div style={{ width: `${pResponded}%` }} className="h-full bg-amber-500 transition-all duration-500" title={`تفاعلوا وردوا: ${responded}`} />
                          <div style={{ width: `${pContacted}%` }} className="h-full bg-blue-500 transition-all duration-500" title={`تم التواصل معهم: ${contacted}`} />
                          <div style={{ width: `${pQueue}%` }} className="h-full bg-slate-800 transition-all duration-500" title={`في الطابور / انتظار: ${queue}`} />
                        </>
                      );
                    })()}
                  </div>

                  {/* Funnel Metrics Breakdown Legend */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] pt-1">
                    <div className="flex items-center gap-1.5 text-slate-400">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
                      <span>عادوا للقناة:</span>
                      <strong className="text-white font-mono">{summary?.total_rejoined || 0}</strong>
                    </div>
                    <div className="flex items-center gap-1.5 text-slate-400">
                      <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
                      <span>ردود وتفاعل:</span>
                      <strong className="text-white font-mono">{summary?.total_responded ?? (summary?.total_in_conversation || 0)}</strong>
                    </div>
                    <div className="flex items-center gap-1.5 text-slate-400">
                      <span className="w-2 h-2 rounded-full bg-blue-400 shrink-0" />
                      <span>تمت مراسلتهم:</span>
                      <strong className="text-white font-mono">{summary?.total_contacted || 0}</strong>
                    </div>
                    <div className="flex items-center gap-1.5 text-slate-400">
                      <span className="w-2 h-2 rounded-full bg-slate-600 shrink-0" />
                      <span>في انتظار الإرسال:</span>
                      <strong className="text-white font-mono">{summary?.total_scheduled_pending || 0}</strong>
                    </div>
                  </div>
                </div>
              </div>

              {/* Section 2: Grid 2 Columns: Peak Hours & Status Breakdown */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Right: Peak Departure Hours */}
                <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 shadow-sm space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <Clock className="w-4 h-4 text-amber-400" />
                      <span>أوقات ذروة المغادرة (24 ساعة)</span>
                    </h3>
                    <span className="text-[11px] text-slate-500">توقيت محلي</span>
                  </div>

                  <div className="space-y-3">
                    <div className="h-40 flex items-end gap-1 bg-slate-950/70 p-3 rounded-xl border border-slate-800/80 overflow-x-auto">
                      {(() => {
                        const hourly = summary?.hourly_distribution || [];
                        const counts = hourly.map(h => h.count);
                        const maxVal = counts.length > 0 ? Math.max(...counts, 1) : 1;
                        return hourly.map((h, i) => {
                          const isPeak = h.count > 0 && h.count === maxVal;
                          const heightPercent = Math.max(8, (h.count / maxVal) * 100);
                          return (
                            <div key={i} className="flex-1 flex flex-col items-center gap-1 min-w-[12px] h-full justify-end group relative">
                              <div className="absolute -top-7 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-800 text-[10px] text-white px-1.5 py-0.5 rounded shadow pointer-events-none whitespace-nowrap z-10 font-mono">
                                {h.hour_label}: {h.count} عضو
                              </div>
                              <div 
                                className={`w-full rounded-t transition-all ${
                                  isPeak ? 'bg-amber-400' :
                                  h.count > 0 ? 'bg-indigo-500' : 'bg-slate-800/40'
                                }`}
                                style={{ height: `${heightPercent}%` }}
                              />
                              {i % 4 === 0 && (
                                <span className="text-[9px] text-slate-500 font-mono mt-1">{h.hour}h</span>
                              )}
                            </div>
                          );
                        });
                      })()}
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded bg-amber-400" />
                        <span>ساعة الذروة</span>
                        <span className="w-2 h-2 rounded bg-indigo-500 ml-2" />
                        <span>خروج نشط</span>
                      </div>
                      <span>مدار 24 ساعة (00:00 - 23:00)</span>
                    </div>
                  </div>
                </div>

                {/* Left: Status Distribution */}
                <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 shadow-sm space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <PieChart className="w-4 h-4 text-blue-400" />
                      <span>توزيع حالات المغادرين</span>
                    </h3>
                    <span className="text-[11px] text-slate-500 font-mono">
                      {summary?.total_left_detected || 0} عضو
                    </span>
                  </div>

                  {/* Stacked Progress Bar */}
                  <div className="w-full h-2 rounded-full overflow-hidden flex bg-slate-800/60 border border-slate-700/50">
                    {(summary?.status_distribution || []).map((s, idx) => {
                      const colorMap = {
                        emerald: 'bg-emerald-500',
                        blue: 'bg-blue-500',
                        teal: 'bg-teal-500',
                        sky: 'bg-sky-500',
                        amber: 'bg-amber-500',
                        rose: 'bg-rose-500',
                        slate: 'bg-slate-500'
                      };
                      return (
                        <div 
                          key={idx}
                          title={`${s.label}: ${s.count} عضو (${s.percentage}%)`}
                          className={`${colorMap[s.color] || 'bg-slate-500'} h-full transition-all`}
                          style={{ width: `${Math.max(2, s.percentage)}%` }}
                        />
                      );
                    })}
                  </div>

                  {/* Status List */}
                  <div className="space-y-2 pt-1">
                    {(summary?.status_distribution || []).map((s, idx) => (
                      <div key={idx} className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800/70 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full shrink-0 ${
                            s.color === 'emerald' ? 'bg-emerald-500' :
                            s.color === 'blue' ? 'bg-blue-500' :
                            s.color === 'teal' ? 'bg-teal-500' :
                            s.color === 'sky' ? 'bg-sky-500' :
                            s.color === 'amber' ? 'bg-amber-400' :
                            s.color === 'rose' ? 'bg-rose-500' : 'bg-slate-500'
                          }`} />
                          <span className="text-xs text-slate-300">{s.label}</span>
                        </div>
                        <div className="flex items-center gap-2 font-mono text-xs">
                          <span className="font-bold text-white">{s.count}</span>
                          <span className="text-[11px] text-slate-500">({s.percentage}%)</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Section 3: Daily Churn vs Rejoins Trend Comparison */}
              <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <RefreshCw className="w-4 h-4 text-blue-400" />
                    <span>حركة المغادرة والعودة (آخر 7 أيام)</span>
                  </h3>
                  <span className="text-[11px] text-slate-500">الصافي اليومي</span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
                  {summary?.daily_trend?.map((d, idx) => {
                    const net = d.rejoins - d.leaves;
                    return (
                      <div key={idx} className="p-3 rounded-xl bg-slate-950/80 border border-slate-800/80 flex flex-col justify-between space-y-2">
                        <span className="text-[11px] font-mono text-slate-400 block text-center border-b border-slate-800/60 pb-1">
                          {d.date.slice(5)}
                        </span>
                        <div className="space-y-1 text-xs font-mono">
                          <div className="flex items-center justify-between">
                            <span className="text-slate-500 text-[10px]">مغادر:</span>
                            <span className="text-rose-400 font-bold">-{d.leaves}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-slate-500 text-[10px]">استرداد:</span>
                            <span className="text-emerald-400 font-bold">+{d.rejoins}</span>
                          </div>
                        </div>
                        <div className="pt-1 border-t border-slate-800/60 flex items-center justify-between text-[10px]">
                          <span className="text-slate-500">الصافي:</span>
                          <span className={`font-bold font-mono ${net > 0 ? 'text-emerald-400' : net < 0 ? 'text-rose-400' : 'text-slate-400'}`}>
                            {net > 0 ? `+${net}` : net}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
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
              <div className="flex items-center justify-between mb-1.5 flex-wrap gap-1">
                <label className="text-xs font-semibold text-slate-300">
                  فترة وسرعة إرسال رسالة الاسترداد بعد مغادرة العضو
                </label>
                <span className="text-emerald-400 text-[11px] font-bold">⚡ موصى به: فوري (5 - 15 ثانية)</span>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <input
                  type="number"
                  min="0"
                  max="120"
                  value={settingsForm.initial_delay_value}
                  onChange={(e) => setSettingsForm({ ...settingsForm, initial_delay_value: e.target.value })}
                  className="w-24 px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs font-mono outline-none focus:border-emerald-500"
                />
                <select
                  value={settingsForm.initial_delay_unit}
                  onChange={(e) => setSettingsForm({ ...settingsForm, initial_delay_unit: e.target.value })}
                  className="px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs font-bold outline-none cursor-pointer"
                >
                  <option value="seconds">ثواني (إرسال فوري وسريع ⚡)</option>
                  <option value="minutes">دقائق</option>
                </select>
                {/* Fast presets */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  <button
                    type="button"
                    onClick={() => setSettingsForm({ ...settingsForm, initial_delay_value: 5, initial_delay_unit: 'seconds' })}
                    className="px-2.5 py-1.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-[11px] font-bold border border-emerald-500/20 transition-all"
                  >
                    فوري (5 ثواني) ⚡
                  </button>
                  <button
                    type="button"
                    onClick={() => setSettingsForm({ ...settingsForm, initial_delay_value: 15, initial_delay_unit: 'seconds' })}
                    className="px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-bold transition-all"
                  >
                    15 ثانية
                  </button>
                  <button
                    type="button"
                    onClick={() => setSettingsForm({ ...settingsForm, initial_delay_value: 30, initial_delay_unit: 'seconds' })}
                    className="px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-bold transition-all"
                  >
                    30 ثانية
                  </button>
                  <button
                    type="button"
                    onClick={() => setSettingsForm({ ...settingsForm, initial_delay_value: 1, initial_delay_unit: 'minutes' })}
                    className="px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-bold transition-all"
                  >
                    دقيقة واحدة
                  </button>
                </div>
              </div>
              <p className="text-[10px] text-slate-400 mt-1">كلما كانت المراسلة أسرع بعد المغادرة مباشرة، كلما تضاعف معدل فتح الرسالة وعودة العضو قبل أن ينشغل.</p>
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

            {/* Ready-made Win-back Templates Selection */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-300">
                قوالب استرداد جاهزة ومجرّبة (اضغط لاختيار وتطبيق القالب مباشرة)
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {WINBACK_TEMPLATES.map((tmpl) => {
                  const isSelected = settingsForm.recovery_first_message_template === tmpl.text;
                  return (
                    <div
                      key={tmpl.id}
                      onClick={() => setSettingsForm({ ...settingsForm, recovery_first_message_template: tmpl.text })}
                      className={`p-3 rounded-xl border cursor-pointer transition-all text-right flex flex-col justify-between ${
                        isSelected
                          ? 'bg-emerald-500/10 border-emerald-500 text-white shadow-sm'
                          : 'bg-slate-950 border-slate-800/80 hover:border-slate-700 text-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <span className="font-bold text-xs">{tmpl.title}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                          isSelected ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-400'
                        }`}>
                          {tmpl.badge}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 leading-snug line-clamp-2">{tmpl.desc}</p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Custom Recovery Message Template with Dynamic Tags */}
            <div className="space-y-2">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <label className="block text-xs font-semibold text-slate-300">
                  نص رسالة الاسترداد الأولى المخصصة
                </label>
                {/* Dynamic Variables Chips */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-[10px] text-slate-500 font-semibold">إدراج متغير:</span>
                  <button
                    type="button"
                    onClick={() => insertTag('{channel}')}
                    className="px-2 py-0.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-[10px] font-mono border border-emerald-500/20 transition-colors"
                    title="يتم استبداله باسم القناة تلقائياً"
                  >
                    + {'{channel}'}
                  </button>
                  <button
                    type="button"
                    onClick={() => insertTag('{name}')}
                    className="px-2 py-0.5 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 text-[10px] font-mono border border-blue-500/20 transition-colors"
                    title="يتم استبداله باسم العضو أو 'يا غالي'"
                  >
                    + {'{name}'}
                  </button>
                  <button
                    type="button"
                    onClick={() => insertTag('{invite_link}')}
                    className="px-2 py-0.5 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 text-[10px] font-mono border border-purple-500/20 transition-colors"
                    title="يتم استبداله برابط القناة المخصص للعودة"
                  >
                    + {'{invite_link}'}
                  </button>
                </div>
              </div>

              <textarea
                rows={4}
                placeholder="اكتب رسالة الاسترداد المخصصة هنا، يمكنك استخدام {channel} و {name} و {invite_link}..."
                value={settingsForm.recovery_first_message_template}
                onChange={(e) => setSettingsForm({ ...settingsForm, recovery_first_message_template: e.target.value })}
                className="w-full p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs outline-none focus:border-emerald-500 leading-relaxed font-sans"
              />

              {/* Live Telegram Chat Bubble Preview */}
              <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2">
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span className="font-semibold flex items-center gap-1.5 text-slate-300">
                    <Eye className="w-3.5 h-3.5 text-emerald-400" />
                    <span>معاينة حية لشكل الرسالة في تيليجرام (كما يراها العضو المغادر)</span>
                  </span>
                  <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full font-mono">
                    Telegram Preview
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-start gap-2.5">
                  <div className="w-8 h-8 rounded-full bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-xs shrink-0 overflow-hidden">
                    {userbots[0]?.has_photo ? (
                      <img 
                        src={`/api/v1/retention/userbots/${userbots[0]?.name || 'primary'}/avatar?t=${avatarTimestamp}`} 
                        alt="Bot" 
                        className="w-full h-full object-cover" 
                        onError={(e) => { e.target.style.display = 'none'; }}
                      />
                    ) : (
                      <span>🤖</span>
                    )}
                  </div>
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-white">
                        {userbots[0]?.username ? `@${userbots[0].username}` : 'حساب اليوزربوت'}
                      </span>
                      <span className="text-[9px] text-emerald-400">متصل الآن</span>
                    </div>
                    <div className="p-3 rounded-2xl rounded-tr-none bg-slate-800/90 text-slate-100 text-xs leading-relaxed whitespace-pre-wrap shadow-sm">
                      {getLivePreviewText()}
                      <div className="mt-1 flex items-center justify-end gap-1 text-[9px] text-slate-400 font-mono">
                        <span>{new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}</span>
                        <Check className="w-3 h-3 text-emerald-400 inline" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
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

      {/* ── TAB 5: USERBOT FLEET & DEDICATED ONBOARDING ──────────────────── */}
      {activeTab === 'userbots' && (
        <div className="space-y-6 max-w-5xl" dir="rtl">
          {/* Header & Add Button Bar */}
          <div className="p-6 bg-slate-900 border border-slate-800 rounded-3xl shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-bold flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>أسطول المراسلة ونظام توزيع الحمل</span>
                </span>
                <span className="text-xs text-slate-400">
                  قناة: <strong className="text-white font-bold">{getSelectedChannelTitle()}</strong>
                </span>
              </div>
              <h2 className="text-lg sm:text-xl font-black text-white flex items-center gap-2.5">
                <Bot className="w-6 h-6 text-emerald-400" />
                <span>حسابات تيليجرام المتصلة (اليوزربوت)</span>
              </h2>
              <p className="text-xs text-slate-400 leading-relaxed">
                اربط أرقام تيليجرام متعددة للمتابعة التلقائية وتوزيع طابور المغادرين بالتناوب العادل (Round-Robin) مع ضمان عدم تكرار المراسلة لنفس العضو من أكثر من حساب.
              </p>
            </div>

            <button
              type="button"
              onClick={() => {
                resetUserbotWizard();
                setShowAddUserbotModal(true);
              }}
              className="px-5 py-3 rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs sm:text-sm shadow-lg shadow-emerald-900/30 flex items-center justify-center gap-2 transition-all transform hover:-translate-y-0.5 shrink-0"
            >
              <PlusCircle className="w-5 h-5" />
              <span>إضافة رقم تيليجرام جديد 📲</span>
            </button>
          </div>

          {/* Quick Stats & Guarantees Strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-400 block">إجمالي الأرقام المتصلة</span>
              <div className="text-xl font-black text-white font-mono flex items-center gap-2">
                <Smartphone className="w-5 h-5 text-emerald-400" />
                <span>{userbots.length}</span>
                <span className="text-[10px] text-slate-500 font-normal">أرقام</span>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-400 block">الحسابات الجاهزة للإرسال</span>
              <div className="text-xl font-black text-emerald-400 font-mono flex items-center gap-2">
                <Zap className="w-5 h-5 text-amber-400" />
                <span>{userbots.filter(b => b.is_healthy && !b.in_cooldown).length}</span>
                <span className="text-[10px] text-emerald-400/70 font-normal">نشط</span>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-400 block">نظام التناوب (Round-Robin)</span>
              <div className="text-xs font-bold text-blue-400 flex items-center gap-1.5 pt-1">
                <RefreshCw className="w-4 h-4 text-blue-400" />
                <span>مفعّل تلقائياً ⚡</span>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-400 block">ضمان المرسل الوحيد</span>
              <div className="text-xs font-bold text-emerald-400 flex items-center gap-1.5 pt-1">
                <Lock className="w-4 h-4 text-emerald-400" />
                <span>مُقفل 100% 🔒</span>
              </div>
            </div>
          </div>

          {/* Golden Rules Banner (Single Messenger & Safety) */}
          <div className="p-4 sm:p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-3">
            <h4 className="text-xs font-bold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-400" />
              <span>قواعد الأمان وتوزيع الحمل الذكي (Smart Multi-Userbot Engine)</span>
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-slate-300">
              <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
                <strong className="text-emerald-400 block font-bold flex items-center gap-1">
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>1. التناوب العادل (Round-Robin)</span>
                </strong>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  يتم توزيع طابور المغادرين بالتناوب المتساوي بين جميع أرقامك النشطة لمضاعفة سرعة الإرسال دون إجهاد أي حساب.
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
                <strong className="text-blue-400 block font-bold flex items-center gap-1">
                  <Lock className="w-3.5 h-3.5" />
                  <span>2. ضمان المرسل الوحيد</span>
                </strong>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  مستحيل أن يتلقى أي عميل رسائل من رقمين مختلفين؛ العميل الذي يبدأ معه رقم معين يظل مرتبطاً به حصرياً في كل المتابعات والردود.
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
                <strong className="text-amber-400 block font-bold flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>3. الحماية والتحويل الفوري</span>
                </strong>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  فواصل زمنية مدروسة وحد يومي آمن (35 رسالة/رقم)، مع تحويل تلقائي للحالات الجديدة للأرقام الأخرى إذا دخل أي رقم في راحة مؤقتة.
                </p>
              </div>
            </div>
          </div>

          {/* Connected Userbots Cards Grid */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Users className="w-4 h-4 text-emerald-400" />
                <span>الأرقام المتصلة بالنظام حالياً ({userbots.length})</span>
              </h3>
              {userbots.length > 0 && (
                <button
                  type="button"
                  onClick={() => fetchData(true)}
                  className="text-xs text-slate-400 hover:text-white flex items-center gap-1 transition-colors"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>تحديث الحالة</span>
                </button>
              )}
            </div>

            {userbots.length === 0 ? (
              <div className="p-8 rounded-3xl bg-slate-900 border border-slate-800 text-center space-y-4">
                <div className="w-16 h-16 rounded-full bg-slate-800/80 border border-slate-700 flex items-center justify-center mx-auto text-slate-400">
                  <Bot className="w-8 h-8" />
                </div>
                <div className="max-w-md mx-auto space-y-1">
                  <h4 className="text-base font-bold text-white">لا توجد أرقام تيليجرام مربوطة حتى الآن</h4>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    ابدأ الآن بربط أول رقم تيليجرام خاص بك بخطوات بسيطة لتبدأ مراسلة الأعضاء المغادرين فوراً وباسم قناتك.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    resetUserbotWizard();
                    setShowAddUserbotModal(true);
                  }}
                  className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-lg inline-flex items-center gap-2 transition-all"
                >
                  <PlusCircle className="w-4 h-4" />
                  <span>إضافة أول رقم تيليجرام الآن</span>
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {userbots.map((b, i) => (
                  <div key={b.id || i} className="p-5 rounded-2xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all space-y-4 shadow-sm">
                    {/* Top Row: Avatar & Identity */}
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3.5">
                        <div className="relative group">
                          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-600/30 to-slate-800 border-2 border-emerald-500/30 flex items-center justify-center text-emerald-400 font-black text-base shrink-0 shadow-inner overflow-hidden">
                            {b.first_name ? b.first_name.slice(0, 2).toUpperCase() : '🤖'}
                          </div>
                          {/* Quick change photo badge on avatar */}
                          <label className="absolute -bottom-1 -right-1 p-1 rounded-full bg-slate-800 hover:bg-emerald-600 text-slate-300 hover:text-white border border-slate-700 cursor-pointer transition-all shadow-md" title="تغيير صورة البروفايل على تيليجرام">
                            <Camera className="w-3 h-3" />
                            <input
                              type="file"
                              accept="image/jpeg,image/png,image/webp"
                              className="hidden"
                              disabled={uploadingAvatar}
                              onChange={(e) => handleDedicatedAvatarUpload(e, b.id)}
                            />
                          </label>
                        </div>

                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <h4 className="text-sm font-bold text-white">{b.first_name || 'حساب تيليجرام'}</h4>
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
                              {b.channel_title}
                            </span>
                          </div>
                          {b.username ? (
                            <a
                              href={`https://t.me/${b.username}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-slate-400 hover:text-emerald-400 font-mono flex items-center gap-1 transition-colors"
                            >
                              <span>@{b.username}</span>
                              <ExternalLink className="w-2.5 h-2.5 opacity-60" />
                            </a>
                          ) : (
                            <span className="text-xs text-slate-500">بدون معرف</span>
                          )}
                          <div className="text-xs text-slate-300 font-mono font-bold flex items-center gap-1 pt-0.5">
                            <Phone className="w-3 h-3 text-slate-500" />
                            <span>{b.phone}</span>
                          </div>
                        </div>
                      </div>

                      {/* Status Badge */}
                      <div>
                        {b.in_cooldown ? (
                          <span className="px-2.5 py-1 rounded-xl text-[11px] font-bold bg-amber-500/10 border border-amber-500/30 text-amber-400 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            <span>راحة مؤقتة ⏳</span>
                          </span>
                        ) : b.is_healthy ? (
                          <span className="px-2.5 py-1 rounded-xl text-[11px] font-bold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>متصل ونشط 🟢</span>
                          </span>
                        ) : (
                          <span className="px-2.5 py-1 rounded-xl text-[11px] font-bold bg-rose-500/10 border border-rose-500/30 text-rose-400 flex items-center gap-1">
                            <AlertCircle className="w-3 h-3" />
                            <span>يحتاج إعادة ربط 🔴</span>
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Middle: Daily Quota & Usage Bar */}
                    <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-400">حصة المراسلات اليومية</span>
                        <span className="font-mono text-white font-bold">
                          {b.daily_contacts_sent} / {b.max_daily_contacts} رسالة
                        </span>
                      </div>
                      {/* Progress bar */}
                      <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            (b.daily_contacts_sent || 0) >= 30 ? 'bg-amber-500' : 'bg-emerald-500'
                          }`}
                          style={{ width: `${Math.min(100, ((b.daily_contacts_sent || 0) / b.max_daily_contacts) * 100)}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-slate-500 pt-0.5">
                        <span>مشارك في التناوب التلقائي 🔄</span>
                        {b.in_cooldown ? (
                          <span className="text-amber-400 font-bold">حماية تيليجرام نشطة مؤقتاً</span>
                        ) : (
                          <span className="text-emerald-400">جاهز لاستلام حالات جديدة</span>
                        )}
                      </div>
                    </div>

                    {/* Bottom Action Buttons */}
                    <div className="flex items-center justify-between pt-1 border-t border-slate-800/60">
                      <label className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold cursor-pointer transition-all flex items-center gap-1.5 border border-slate-700">
                        <Upload className="w-3.5 h-3.5 text-emerald-400" />
                        <span>{uploadingAvatar ? 'جاري الرفع...' : 'تغيير الصورة 📷'}</span>
                        <input
                          type="file"
                          accept="image/jpeg,image/png,image/webp"
                          className="hidden"
                          disabled={uploadingAvatar}
                          onChange={(e) => handleDedicatedAvatarUpload(e, b.id)}
                        />
                      </label>

                      <button
                        type="button"
                        onClick={() => handleDisconnectDedicatedUserbot(b.id, b.channel_id)}
                        disabled={actionLoading}
                        className="px-3 py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 text-xs font-bold transition-all flex items-center gap-1.5"
                        title="فصل هذا الرقم عن القناة"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>فصل الرقم</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── ADD USERBOT ONBOARDING WIZARD MODAL ──────────────────────────── */}
      {showAddUserbotModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-3 sm:p-4" dir="rtl">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-xl max-h-[90vh] overflow-y-auto p-5 sm:p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[11px] font-bold">
                  معالج ربط الأرقام الذكي
                </span>
                <h3 className="text-base sm:text-lg font-black text-white mt-1 flex items-center gap-2">
                  <Smartphone className="w-5 h-5 text-emerald-400" />
                  <span>إضافة رقم تيليجرام جديد (يوزربوت)</span>
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowAddUserbotModal(false)}
                className="w-8 h-8 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Stepper Progress Bar (Stages 1 to 5) */}
            <div className="grid grid-cols-5 gap-1.5">
              {[
                { num: 1, label: 'بيانات API' },
                { num: 2, label: 'رقم الهاتف' },
                { num: 3, label: 'كود التحقق' },
                { num: 4, label: 'المرور 2FA' },
                { num: 5, label: 'اكتمال الربط' }
              ].map(st => (
                <div key={st.num} className="space-y-1 text-center">
                  <div className={`h-1.5 rounded-full transition-all ${
                    userbotStep === st.num
                      ? 'bg-emerald-500 ring-2 ring-emerald-500/30'
                      : userbotStep > st.num
                        ? 'bg-emerald-600'
                        : 'bg-slate-800'
                  }`} />
                  <span className={`text-[10px] block truncate ${
                    userbotStep === st.num ? 'text-emerald-400 font-bold' : userbotStep > st.num ? 'text-slate-300' : 'text-slate-600'
                  }`}>
                    {st.label}
                  </span>
                </div>
              ))}
            </div>

            {/* STAGE 1: API SELECTION & GUIDE */}
            {userbotStep === 1 && (
              <div className="space-y-4">
                <div className="p-3.5 rounded-2xl bg-blue-500/10 border border-blue-500/20 text-xs text-blue-300 leading-relaxed">
                  <strong className="text-white font-bold block mb-1">💡 لماذا نحتاج لربط حساب تيليجرام؟</strong>
                  لكي يتمكن النظام من مراسلة الأعضاء المغادرين مباشرة من حسابك وباسم قناتك عبر بروتوكول تيليجرام الرسمي MTProto بسرعة وأمان تام.
                </div>

                <div className="space-y-3">
                  <label className="text-xs font-bold text-slate-300 block">اختر طريقة الربط المناسبة لك:</label>

                  {/* Option A: Platform Default API Keys (Recommended) */}
                  <div
                    onClick={() => setUseCustomApi(false)}
                    className={`p-4 rounded-2xl border cursor-pointer transition-all ${
                      !useCustomApi
                        ? 'bg-emerald-950/30 border-emerald-500/50 shadow-md ring-1 ring-emerald-500/20'
                        : 'bg-slate-950 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <Zap className="w-4 h-4 text-amber-400" />
                          <h4 className="text-sm font-bold text-white">الربط السريع بالمفاتيح الافتراضية (موصى به ⭐)</h4>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">فوري</span>
                        </div>
                        <p className="text-xs text-slate-400 leading-relaxed">
                          نظامنا يوفر مفاتيح API رسمية معتمدة ومجهزة تلقائياً دون الحاجة لفتح موقع تيليجرام أو استخراج أي مفاتيح بنفسك.
                        </p>
                      </div>
                      <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5 ${
                        !useCustomApi ? 'border-emerald-500 bg-emerald-500 text-white' : 'border-slate-700'
                      }`}>
                        {!useCustomApi && <Check className="w-3 h-3" />}
                      </div>
                    </div>
                  </div>

                  {/* Option B: Custom API Keys from my.telegram.org */}
                  <div
                    onClick={() => setUseCustomApi(true)}
                    className={`p-4 rounded-2xl border cursor-pointer transition-all ${
                      useCustomApi
                        ? 'bg-emerald-950/30 border-emerald-500/50 shadow-md ring-1 ring-emerald-500/20'
                        : 'bg-slate-950 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <Settings className="w-4 h-4 text-emerald-400" />
                          <h4 className="text-sm font-bold text-white">استخدام مفاتيح API مخصصة من my.telegram.org</h4>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">اختياري</span>
                        </div>
                        <p className="text-xs text-slate-400 leading-relaxed">
                          للمطورين وأصحاب التطبيقات الخاصة الذين يفضلون استخدام API ID و API HASH مسجل باسمهم.
                        </p>
                      </div>
                      <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5 ${
                        useCustomApi ? 'border-emerald-500 bg-emerald-500 text-white' : 'border-slate-700'
                      }`}>
                        {useCustomApi && <Check className="w-3 h-3" />}
                      </div>
                    </div>

                    {/* Step-by-step guide if custom API is selected */}
                    {useCustomApi && (
                      <div className="mt-4 pt-4 border-t border-slate-800/80 space-y-4" onClick={(e) => e.stopPropagation()}>
                        <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2.5">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                              <Key className="w-3.5 h-3.5" />
                              <span>طريقة استخراج المفاتيح في 30 ثانية:</span>
                            </span>
                            <a
                              href="https://my.telegram.org"
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold flex items-center gap-1 shadow-sm transition-all"
                            >
                              <ExternalLink className="w-3 h-3" />
                              <span>فتح my.telegram.org ↗</span>
                            </a>
                          </div>
                          <ol className="text-[11px] text-slate-300 space-y-1.5 list-decimal list-inside pr-1">
                            <li>افتح الرابط أعلاه وسجل دخولك برقم هاتفك والكود المستلم على تيليجرام.</li>
                            <li>اضغط على خيار <strong>API development tools</strong>.</li>
                            <li>اكتب أي اسم بالإنجليزية للتطبيق واحفظ، ثم انسخ الـ <strong>api_id</strong> و <strong>api_hash</strong>.</li>
                          </ol>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs font-semibold text-slate-300 mb-1">
                              App API ID (أرقام فقط) <span className="text-rose-400">*</span>
                            </label>
                            <input
                              type="number"
                              placeholder="مثال: 29482710"
                              value={userbotForm.api_id}
                              onChange={(e) => setUserbotForm({ ...userbotForm, api_id: e.target.value })}
                              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white text-xs font-mono outline-none focus:border-emerald-500"
                            />
                          </div>

                          <div>
                            <label className="block text-xs font-semibold text-slate-300 mb-1">
                              App API HASH (نص حروف ورموز) <span className="text-rose-400">*</span>
                            </label>
                            <input
                              type="text"
                              placeholder="مثال: a1b2c3d4e5f6g7h8..."
                              value={userbotForm.api_hash}
                              onChange={(e) => setUserbotForm({ ...userbotForm, api_hash: e.target.value })}
                              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white text-xs font-mono outline-none focus:border-emerald-500"
                            />
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <div className="pt-2 flex justify-end">
                  <button
                    type="button"
                    onClick={() => {
                      if (useCustomApi && (!userbotForm.api_id || !userbotForm.api_hash)) {
                        showToast('يرجى إدخال الـ API ID و API HASH أو اختر الربط السريع بالمفاتيح الافتراضية.', 'error');
                        return;
                      }
                      setUserbotStep(2);
                    }}
                    className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all shadow-lg flex items-center gap-2"
                  >
                    <span>المتابعة لإدخال رقم الهاتف</span>
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}

            {/* STAGE 2: PHONE NUMBER & CHANNEL SELECTION */}
            {userbotStep === 2 && (
              <form onSubmit={handleRequestUserbotCode} className="space-y-4">
                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                  <div>
                    <label className="block text-xs font-bold text-slate-300 mb-1">
                      القناة المستهدفة لربط هذا الرقم بها <span className="text-rose-400">*</span>
                    </label>
                    <select
                      value={userbotForm.channel_id || selectedChannelId}
                      onChange={(e) => setUserbotForm({ ...userbotForm, channel_id: e.target.value })}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white text-xs outline-none focus:border-emerald-500 font-bold"
                    >
                      {channels.map(ch => (
                        <option key={ch.id} value={ch.id}>{ch.title} ({ch.username ? `@${ch.username}` : ch.id})</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-300 mb-1">
                      رقم هاتف حساب التيليجرام (بصيغته الدولية الكاملة) <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      placeholder="مثال: +966501234567 أو +201012345678"
                      value={userbotForm.phone}
                      onChange={(e) => setUserbotForm({ ...userbotForm, phone: e.target.value })}
                      required
                      autoFocus
                      className="w-full px-4 py-3 rounded-xl bg-slate-900 border border-slate-800 text-white text-sm font-mono outline-none focus:border-emerald-500"
                    />
                    <span className="text-[10px] text-slate-500 mt-1 block">
                      اكتب كود الدولة مسبوقاً بعلامة + وسيصلك كود التحقق في تطبيق تيليجرام الرسمي على هذا الرقم.
                    </span>
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 shrink-0 text-emerald-400" />
                  <span>
                    الرقم محمي بنظام فواصل زمنية ذكية بين كل رسالة وأخرى لتجنب أي قيود من تيليجرام.
                  </span>
                </div>

                <div className="pt-2 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => setUserbotStep(1)}
                    className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition-all"
                  >
                    رجوع
                  </button>

                  <button
                    type="submit"
                    disabled={sendingOtp}
                    className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold transition-all shadow-lg flex items-center gap-2"
                  >
                    {sendingOtp ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>جاري إرسال كود التحقق لتطبيق تيليجرام...</span>
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4" />
                        <span>إرسال كود التحقق لتطبيق تيليجرام 📲</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}

            {/* STAGE 3: ENTER OTP CODE */}
            {userbotStep === 3 && (
              <form onSubmit={handleVerifyUserbotCode} className="space-y-4">
                <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 space-y-1">
                  <div className="flex items-center gap-1.5 font-bold text-white text-sm">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>تم إرسال كود التحقق بنجاح!</span>
                  </div>
                  <p className="text-[11px] text-slate-300">
                    افتح تطبيق تيليجرام على رقمك <strong className="font-mono text-white">{userbotForm.phone}</strong>، ستجد رسالة واردة من حساب تيليجرام الرسمي تحتوي على الكود.
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="block text-xs font-bold text-slate-300 text-center">
                    اكتب كود التحقق المستلم (OTP)
                  </label>
                  <input
                    type="text"
                    placeholder="مثال: 54321"
                    value={verifyCode}
                    onChange={(e) => setVerifyCode(e.target.value)}
                    required
                    autoFocus
                    className="w-full px-4 py-3.5 rounded-2xl bg-slate-950 border border-emerald-500/40 text-white text-xl font-mono text-center tracking-widest outline-none focus:border-emerald-400 font-black shadow-inner"
                  />
                </div>

                <div className="pt-2 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => setUserbotStep(2)}
                    className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition-all"
                  >
                    تعديل الرقم ↩
                  </button>

                  <button
                    type="submit"
                    disabled={verifyingOtp}
                    className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold transition-all shadow-lg flex items-center gap-2"
                  >
                    {verifyingOtp ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>جاري التحقق وإنشاء الاتصال...</span>
                      </>
                    ) : (
                      <>
                        <ShieldCheck className="w-4 h-4" />
                        <span>تأكيد الكود وربط الحساب 🚀</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}

            {/* STAGE 4: 2FA CLOUD PASSWORD */}
            {userbotStep === 4 && (
              <form onSubmit={handleVerifyUserbotCode} className="space-y-4">
                <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 space-y-1">
                  <div className="flex items-center gap-1.5 font-bold text-white text-sm">
                    <Lock className="w-4 h-4 text-amber-400" />
                    <span>مطلوب كلمة المرور السحابية (2FA)</span>
                  </div>
                  <p className="text-[11px] text-slate-300 leading-relaxed">
                    حساب تيليجرام الخاص بك محمي بخاصية التحقق بخطوتين (Two-Step Verification). يرجى كتابة كلمة المرور السحابية للمتابعة:
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="block text-xs font-bold text-slate-300">
                    كلمة المرور السحابية (2FA Password) <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="password"
                    placeholder="اكتب كلمة المرور السحابية هنا..."
                    value={verifyPassword}
                    onChange={(e) => setVerifyPassword(e.target.value)}
                    required
                    autoFocus
                    className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-white text-sm outline-none focus:border-emerald-500"
                  />
                </div>

                <div className="pt-2 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => setUserbotStep(3)}
                    className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition-all"
                  >
                    رجوع للكود
                  </button>

                  <button
                    type="submit"
                    disabled={verifyingOtp}
                    className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold transition-all shadow-lg flex items-center gap-2"
                  >
                    {verifyingOtp ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>جاري التحقق...</span>
                      </>
                    ) : (
                      <>
                        <ShieldCheck className="w-4 h-4" />
                        <span>تأكيد كلمة المرور وإتمام الربط 🔐</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}

            {/* STAGE 5: SUCCESS & ADDED TO FLEET */}
            {userbotStep === 5 && (
              <div className="p-6 rounded-3xl bg-slate-950 border border-emerald-500/30 text-center space-y-5 animate-in fade-in zoom-in-95">
                <div className="w-16 h-16 rounded-full bg-emerald-500/20 border-2 border-emerald-500/40 text-emerald-400 flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/10">
                  <CheckCircle2 className="w-8 h-8" />
                </div>

                <div className="space-y-1.5">
                  <h3 className="text-lg font-black text-white">تم ربط الحساب بنجاح تام! 🎉</h3>
                  <p className="text-xs text-slate-300 leading-relaxed max-w-md mx-auto">
                    تمت إضافة الرقم إلى أسطول حساباتك بنجاح وسيبدأ فوراً في نظام التناوب ومضاعفة سرعة الإرسال للأعضاء المغادرين.
                  </p>
                </div>

                {connectedUserbotSuccess && (
                  <div className="p-3.5 rounded-2xl bg-slate-900 border border-slate-800 text-xs text-slate-300 flex items-center justify-between gap-3 max-w-sm mx-auto">
                    <div className="flex items-center gap-2.5">
                      <div className="w-9 h-9 rounded-xl bg-emerald-500/20 text-emerald-400 font-bold flex items-center justify-center">
                        🤖
                      </div>
                      <div className="text-right">
                        <strong className="text-white block font-bold">{connectedUserbotSuccess.first_name || 'حساب تيليجرام'}</strong>
                        {connectedUserbotSuccess.username && (
                          <span className="text-[11px] text-slate-400 font-mono">@{connectedUserbotSuccess.username}</span>
                        )}
                      </div>
                    </div>
                    <span className="font-mono text-emerald-400 font-bold">{connectedUserbotSuccess.phone}</span>
                  </div>
                )}

                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setShowAddUserbotModal(false);
                      resetUserbotWizard();
                      fetchData(true);
                    }}
                    className="w-full sm:w-auto px-8 py-3 rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-black text-sm shadow-xl transition-all"
                  >
                    إغلاق وعرض أسطول الحسابات ⚡
                  </button>
                </div>
              </div>
            )}
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
                {selectedCase.user_username ? (
                  <a
                    href={`https://t.me/${selectedCase.user_username}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-2.5 py-1 rounded-lg bg-sky-500/10 text-sky-400 hover:bg-sky-500/20 text-[11px] font-bold border border-sky-500/20 transition-all flex items-center gap-1"
                    title="فتح المحادثة في تطبيق تيليجرام"
                  >
                    <ExternalLink className="w-3 h-3" />
                    <span>تيليجرام ↗</span>
                  </a>
                ) : (
                  <a
                    href={`tg://user?id=${selectedCase.telegram_user_id}`}
                    className="px-2.5 py-1 rounded-lg bg-sky-500/10 text-sky-400 hover:bg-sky-500/20 text-[11px] font-bold border border-sky-500/20 transition-all flex items-center gap-1"
                    title="فتح المحادثة في تطبيق تيليجرام"
                  >
                    <ExternalLink className="w-3 h-3" />
                    <span>تيليجرام ↗</span>
                  </a>
                )}
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
                  لم يتم تبادل أي رسائل بعد. الرسالة مجدولة للإرسال تلقائياً أو يمكنك المراسلة يدوياً الآن بالأسفل أو فتح تيليجرام مباشرة.
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

            {/* Quick Templates */}
            <div className="px-3 py-2 bg-slate-950/90 border-t border-slate-800/60 flex items-center gap-1.5 overflow-x-auto text-[10px]">
              <span className="text-slate-500 font-semibold whitespace-nowrap">قوالب جاهزة:</span>
              <button
                type="button"
                onClick={() => setManualText(`مرحباً ${selectedCase?.user_full_name ? selectedCase.user_full_name.split(' ')[0] : 'يا غالي'}، لاحظنا مغادرتك لقناة ${selectedCase?.channel_title || 'القناة'} وحبينا نتطمن عليك 🌹\nهل خرجت بالخطأ أو كان هناك أمر أزعجك؟ رأيك يهمنا جداً لتطوير القناة.\n\n${settings?.invite_link || ''}`)}
                className="px-2.5 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 whitespace-nowrap transition-colors font-bold"
              >
                اطمئنان مع الرابط 🌹
              </button>
              <button
                type="button"
                onClick={() => setManualText(`مرحباً يا ${selectedCase?.user_full_name ? selectedCase.user_full_name.split(' ')[0] : 'غالي'}، لاحظنا مغادرتك لقناة ${selectedCase?.channel_title || 'القناة'} وحبينا نتطمن عليك 🌹 هل خرجت بالخطأ؟`)}
                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 whitespace-nowrap transition-colors"
              >
                مغادرة بالخطأ 🌹
              </button>
              <button
                type="button"
                onClick={() => setManualText(`أهلاً بك، تفضل رابط العودة المباشر للقناة:\n${settings?.invite_link || ''}`)}
                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 whitespace-nowrap transition-colors"
              >
                رابط العودة 🔗
              </button>
              <button
                type="button"
                onClick={() => setManualText(`مرحباً يا ${selectedCase?.user_full_name ? selectedCase.user_full_name.split(' ')[0] : 'غالي'}، يسعدنا سماع رأيك أو أي اقتراح لتطوير محتوى قناة ${selectedCase?.channel_title || 'القناة'} لتناسبك أكثر 💡`)}
                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 whitespace-nowrap transition-colors"
              >
                استفسار واقتراح 💡
              </button>
            </div>

            {/* Manual Reply Input */}
            <form onSubmit={handleSendManualMessage} className="p-3 pb-safe bg-slate-950 border-t border-slate-800 flex items-center gap-2">
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
