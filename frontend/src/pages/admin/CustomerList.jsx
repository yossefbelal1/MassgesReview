import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { 
  Users, Search, ShieldAlert, CheckCircle2, Clock, 
  Calendar, RefreshCw, X, ArrowLeft, ArrowRight, ShieldCheck, 
  Sliders, KeyRound, Trash2, Edit3, PauseCircle, PlayCircle, Plus,
  Radio, Workflow, Layers, AlertTriangle, ExternalLink, ChevronRight,
  Sparkles, Check, Zap, Hash, MessageSquare, ToggleLeft, ToggleRight
} from 'lucide-react';

export default function CustomerList() {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [planFilter, setPlanFilter] = useState('all');
  const [actionLoading, setActionLoading] = useState(null);

  // Selected customer for full management modal
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [customerDetails, setCustomerDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [activeModalTab, setActiveModalTab] = useState('subscription'); // 'subscription' | 'channels' | 'security'

  // Edit Subscription Form State
  const [editPlanSlug, setEditPlanSlug] = useState('pro');
  const [editStatus, setEditStatus] = useState('active');
  const [editExpiryDate, setEditExpiryDate] = useState('');
  const [savingSub, setSavingSub] = useState(false);

  // Reset Password State
  const [newPassword, setNewPassword] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);

  // Admin Automations & Trigger Management State
  const [editingAuto, setEditingAuto] = useState(null);
  const [isAddingAuto, setIsAddingAuto] = useState(false);
  const [autoForm, setAutoForm] = useState({
    name: '',
    trigger_value: '',
    trigger_type: 'contains',
    channel_id: '',
    reviews_count: 2,
    initial_delay_seconds: 5.0,
    delay_seconds: 4.0,
    is_active: true
  });
  const [savingAuto, setSavingAuto] = useState(false);

  useEffect(() => {
    fetchCustomers();
  }, []);

  useEffect(() => {
    if (selectedCustomer) {
      document.body.classList.add('modal-open');
    } else {
      document.body.classList.remove('modal-open');
    }
    return () => {
      document.body.classList.remove('modal-open');
    };
  }, [selectedCustomer]);

  const fetchCustomers = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/admin/customers');
      setCustomers(res.data);
    } catch (err) {
      console.error('Failed to fetch customers:', err);
    } finally {
      setLoading(false);
    }
  };

  const openCustomerModal = async (c) => {
    setSelectedCustomer(c);
    setEditPlanSlug(c.plan_slug || 'pro');
    setEditStatus(c.subscription_status || 'active');
    setEditExpiryDate(c.expires_at ? c.expires_at.split('T')[0] : '');
    setNewPassword('');
    setActiveModalTab('subscription');
    setEditingAuto(null);
    setIsAddingAuto(false);

    try {
      setDetailsLoading(true);
      const res = await apiClient.get(`/admin/customers/${c.id}`);
      setCustomerDetails(res.data);
    } catch (err) {
      console.error('Failed to fetch customer details:', err);
    } finally {
      setDetailsLoading(false);
    }
  };

  const refreshCustomerDetails = async (tenantId) => {
    try {
      const res = await apiClient.get(`/admin/customers/${tenantId}`);
      setCustomerDetails(res.data);
      await fetchCustomers();
    } catch (err) {
      console.error('Failed to refresh details:', err);
    }
  };

  const closeCustomerModal = () => {
    setSelectedCustomer(null);
    setCustomerDetails(null);
    setEditingAuto(null);
    setIsAddingAuto(false);
  };

  // Quick Extend (+N Days)
  const handleQuickExtend = async (tenantId, days = 30) => {
    try {
      setActionLoading(tenantId);
      await apiClient.post(`/admin/customers/${tenantId}/subscription/extend?days=${days}`);
      await fetchCustomers();
    } catch (err) {
      alert('فشل تمديد الاشتراك');
    } finally {
      setActionLoading(null);
    }
  };

  // Toggle Suspend / Resume
  const handleToggleStatus = async (tenantId, currentStatus) => {
    try {
      setActionLoading(tenantId);
      if (currentStatus === 'suspended') {
        await apiClient.post(`/admin/customers/${tenantId}/subscription/resume`);
      } else {
        if (!window.confirm('هل أنت متأكد من إيقاف اشتراك هذا العميل مؤقتاً؟ ستتوقف أتمتة النشر الخاصة به فوراً.')) return;
        await apiClient.post(`/admin/customers/${tenantId}/subscription/suspend`);
      }
      await fetchCustomers();
      if (selectedCustomer && selectedCustomer.id === tenantId) {
        openCustomerModal({ ...selectedCustomer, subscription_status: currentStatus === 'suspended' ? 'active' : 'suspended' });
      }
    } catch (err) {
      alert('فشل تحديث حالة الاشتراك');
    } finally {
      setActionLoading(null);
    }
  };

  // Save Full Subscription Edits
  const handleSaveSubscription = async (e) => {
    e.preventDefault();
    if (!selectedCustomer) return;

    try {
      setSavingSub(true);
      await apiClient.post(`/admin/customers/${selectedCustomer.id}/subscription/update`, {
        plan_slug: editPlanSlug,
        status: editStatus,
        expires_at: editExpiryDate ? new Date(editExpiryDate).toISOString() : null
      });
      await fetchCustomers();
      await refreshCustomerDetails(selectedCustomer.id);
      alert('تم تحديث بيانات اشتراك العميل بنجاح!');
    } catch (err) {
      alert('حدث خطأ أثناء تحديث الاشتراك');
    } finally {
      setSavingSub(false);
    }
  };

  // Reset Customer Password
  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (!selectedCustomer || !newPassword) return;

    try {
      setSavingPassword(true);
      await apiClient.post(`/admin/customers/${selectedCustomer.id}/reset-password`, {
        new_password: newPassword
      });
      setNewPassword('');
      alert('تم تعيين كلمة المرور الجديدة للمشترك بنجاح!');
    } catch (err) {
      alert('فشل إعادة تعيين كلمة المرور');
    } finally {
      setSavingPassword(false);
    }
  };

  // Delete Customer Account
  const handleDeleteCustomer = async () => {
    if (!selectedCustomer) return;
    const confirmName = window.prompt(`تحذير أمني: لحذف العميل نهائياً، يرجى كتابة اسمه للتأكيد: "${selectedCustomer.name}"`);
    if (confirmName !== selectedCustomer.name) {
      if (confirmName !== null) alert('لم يتم تأكيد الاسم بشكل صحيح. تم إلغاء العملية.');
      return;
    }

    try {
      setActionLoading(selectedCustomer.id);
      await apiClient.delete(`/admin/customers/${selectedCustomer.id}`);
      closeCustomerModal();
      await fetchCustomers();
      alert('تم حذف حساب العميل وبياناته بنجاح.');
    } catch (err) {
      alert('فشل حذف حساب العميل');
    } finally {
      setActionLoading(null);
    }
  };

  const handleAddDaysToForm = (days) => {
    const base = editExpiryDate ? new Date(editExpiryDate) : new Date();
    base.setDate(base.getDate() + days);
    setEditExpiryDate(base.toISOString().split('T')[0]);
  };

  // ── Admin Automations Actions ──
  const startAddAutomation = (channelId = '') => {
    setEditingAuto(null);
    setAutoForm({
      name: 'ارباحكم ياخواتي',
      trigger_value: 'ارباحكم',
      trigger_type: 'contains',
      channel_id: channelId || (customerDetails?.channels?.[0]?.id || ''),
      reviews_count: 2,
      initial_delay_seconds: 5.0,
      delay_seconds: 4.0,
      is_active: true
    });
    setIsAddingAuto(true);
  };

  const startEditAutomation = (auto) => {
    setIsAddingAuto(false);
    setEditingAuto(auto);
    setAutoForm({
      name: auto.name || '',
      trigger_value: auto.trigger_value || '',
      trigger_type: auto.trigger_type || 'contains',
      channel_id: auto.channel_id || '',
      reviews_count: auto.reviews_count || 2,
      initial_delay_seconds: auto.initial_delay_seconds || 5.0,
      delay_seconds: auto.delay_seconds || 4.0,
      is_active: auto.is_active
    });
  };

  const handleSaveAutomation = async (e) => {
    e.preventDefault();
    if (!selectedCustomer) return;

    try {
      setSavingAuto(true);
      if (editingAuto) {
        // Update existing automation
        await apiClient.put(`/admin/automations/${editingAuto.id}`, autoForm);
        alert('تم تعديل الهدف والكلمة المفتاحية بنجاح!');
      } else {
        // Create new automation
        await apiClient.post(`/admin/customers/${selectedCustomer.id}/automations`, autoForm);
        alert('تم إضافة الهدف الجديد لهذا العميل بنجاح!');
      }
      setEditingAuto(null);
      setIsAddingAuto(false);
      await refreshCustomerDetails(selectedCustomer.id);
    } catch (err) {
      alert('فشل حفظ الأتمتة: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSavingAuto(false);
    }
  };

  const handleToggleAuto = async (autoId) => {
    try {
      await apiClient.post(`/admin/automations/${autoId}/toggle`);
      await refreshCustomerDetails(selectedCustomer.id);
    } catch (err) {
      alert('فشل تغيير حالة الأتمتة');
    }
  };

  const handleDeleteAuto = async (autoId, autoName) => {
    if (!window.confirm(`هل أنت متأكد من حذف الهدف "${autoName}"؟`)) return;
    try {
      await apiClient.delete(`/admin/automations/${autoId}`);
      await refreshCustomerDetails(selectedCustomer.id);
    } catch (err) {
      alert('فشل حذف الهدف');
    }
  };

  // Filter customers
  const filteredCustomers = customers.filter((c) => {
    const matchesSearch = 
      (c.name && c.name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (c.owner_email && c.owner_email.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (c.owner_name && c.owner_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (c.keywords && c.keywords.some(k => k.toLowerCase().includes(searchTerm.toLowerCase())));

    const matchesStatus = 
      statusFilter === 'all' ? true :
      statusFilter === 'active' ? c.subscription_status === 'active' :
      statusFilter === 'trial' ? c.subscription_status === 'trial' :
      statusFilter === 'suspended' ? c.subscription_status === 'suspended' :
      statusFilter === 'expiring' ? (c.days_remaining <= 7 && c.days_remaining > 0) :
      statusFilter === 'expired' ? (c.days_remaining === 0 || c.subscription_status === 'expired') : true;

    const matchesPlan = planFilter === 'all' ? true : c.plan_slug === planFilter;

    return matchesSearch && matchesStatus && matchesPlan;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/60 p-4 sm:p-6 rounded-2xl sm:rounded-3xl border border-slate-800 backdrop-blur-xl">
        <div>
          <div className="flex items-center gap-2.5 mb-1.5">
            <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <Users className="w-4 h-4" />
            </div>
            <h1 className="text-lg sm:text-xl font-black text-white tracking-tight">إدارة العملاء والقنوات والكلمات</h1>
          </div>
          <p className="text-xs text-slate-400">
            متابعة المشتركين، ضبط الباقات، وتعديل كلمات وأهداف القنوات مباشرة لتوفير الراحة للعميل.
          </p>
        </div>

        <button
          onClick={fetchCustomers}
          disabled={loading}
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800/80 hover:bg-slate-800 border border-slate-700/80 text-slate-200 text-xs font-semibold transition-all active:scale-98 shadow-sm"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
          <span>تحديث القائمة</span>
        </button>
      </div>

      {/* Filter & Search Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="relative">
          <Search className="absolute right-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="بحث بالاسم، الإيميل، أو الكلمة المفتاحية (مثال: TP1, ارباحكم)..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-4 pr-10 py-2.5 rounded-xl bg-slate-900/80 border border-slate-800 focus:border-emerald-500 text-white text-xs placeholder-slate-500 outline-none transition-colors"
          />
        </div>

        <div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full px-3 py-2.5 rounded-xl bg-slate-900/80 border border-slate-800 text-slate-300 text-xs outline-none focus:border-emerald-500"
          >
            <option value="all">جميع الحالات</option>
            <option value="active">نشط (Active)</option>
            <option value="trial">تجريبي (Trial)</option>
            <option value="expiring">ينتهي قريباً (أقل من 7 أيام)</option>
            <option value="suspended">معلق مؤقتاً</option>
            <option value="expired">منتهي الصلاحية</option>
          </select>
        </div>

        <div>
          <select
            value={planFilter}
            onChange={(e) => setPlanFilter(e.target.value)}
            className="w-full px-3 py-2.5 rounded-xl bg-slate-900/80 border border-slate-800 text-slate-300 text-xs outline-none focus:border-emerald-500"
          >
            <option value="all">جميع الباقات</option>
            <option value="starter">الباقة الأساسية (Starter)</option>
            <option value="pro">الباقة الاحترافية (Pro)</option>
            <option value="vip">باقة النخبة (VIP)</option>
          </select>
        </div>
      </div>

      {/* Customers List / Table */}
      {loading ? (
        <div className="p-12 text-center text-slate-400 bg-slate-900/40 rounded-2xl border border-slate-800 flex flex-col items-center gap-3">
          <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
          <span className="text-xs">جاري تحميل بيانات المشتركين وأهدافهم...</span>
        </div>
      ) : filteredCustomers.length === 0 ? (
        <div className="p-12 text-center text-slate-400 bg-slate-900/40 rounded-2xl border border-slate-800">
          <p className="text-xs">لا يوجد مشتركون مطابقون لخيارات البحث المحددة.</p>
        </div>
      ) : (
        <>
          {/* Mobile Cards View */}
          <div className="grid grid-cols-1 gap-3 md:hidden">
            {filteredCustomers.map((c) => {
              const isExpired = c.days_remaining === 0 || c.subscription_status === 'expired';
              const isExpiring = c.days_remaining <= 7 && c.days_remaining > 0 && c.subscription_status === 'active';
              const isSuspended = c.subscription_status === 'suspended';

              return (
                <div key={c.id} className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-3 shadow-sm">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="text-sm font-bold text-white flex items-center gap-2">
                        <span>{c.name}</span>
                      </h3>
                      <p className="text-[11px] text-slate-400">{c.owner_email}</p>
                    </div>

                    <span className={`px-2 py-0.5 rounded-lg text-[10px] font-bold border ${
                      c.plan_slug === 'vip' 
                        ? 'bg-amber-500/10 border-amber-500/20 text-amber-300' 
                        : c.plan_slug === 'pro'
                        ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                        : 'bg-slate-800 border-slate-700 text-slate-300'
                    }`}>
                      {c.plan_name}
                    </span>
                  </div>

                  {/* Keywords Tag List */}
                  {c.keywords && c.keywords.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                      <span className="text-[10px] text-slate-400 font-semibold">الكلمات:</span>
                      {c.keywords.map((kw, i) => (
                        <span key={i} className="px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono text-[10px] font-bold">
                          {kw}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-slate-800/60">
                    <div>
                      <span className="text-slate-400 text-[10px] block">القنوات:</span>
                      <span className="text-slate-200 font-semibold">{c.channels_count} / {c.max_channels} قنوات</span>
                    </div>
                    <div>
                      <span className="text-slate-400 text-[10px] block">المدة المتبقية:</span>
                      <span className={`font-bold ${isExpiring ? 'text-amber-400' : isExpired ? 'text-rose-400' : 'text-slate-200'}`}>
                        {c.days_remaining > 0 ? `${c.days_remaining} يوم` : 'منتهي'}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-2 border-t border-slate-800/60">
                    <button
                      onClick={() => handleQuickExtend(c.id, 30)}
                      disabled={actionLoading === c.id}
                      className="flex-1 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-400 text-xs font-bold transition-all text-center"
                    >
                      +30 يوم
                    </button>

                    <button
                      onClick={() => openCustomerModal(c)}
                      className="flex-1 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-white text-xs font-bold transition-all flex items-center justify-center gap-1"
                    >
                      <Sliders className="w-3.5 h-3.5 text-emerald-400" />
                      <span>الكلمات والتحكم</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Desktop Table View */}
          <div className="hidden md:block rounded-2xl bg-slate-900/60 border border-slate-800 overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-right text-xs text-slate-300">
                <thead className="bg-slate-950/60 text-slate-400 uppercase text-[11px] font-bold border-b border-slate-800">
                  <tr>
                    <th className="py-3.5 px-6">المشترك</th>
                    <th className="py-3.5 px-6">الباقة والسعة</th>
                    <th className="py-3.5 px-6">الكلمات المفتاحية المراقبة</th>
                    <th className="py-3.5 px-6">الحالة</th>
                    <th className="py-3.5 px-6">المدة المتبقية</th>
                    <th className="py-3.5 px-6 text-center">إجراءات سريعة وتحكم</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {filteredCustomers.map((c) => {
                    const isExpired = c.days_remaining === 0 || c.subscription_status === 'expired';
                    const isExpiring = c.days_remaining <= 7 && c.days_remaining > 0 && c.subscription_status === 'active';
                    const isSuspended = c.subscription_status === 'suspended';

                    return (
                      <tr key={c.id} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-4 px-6">
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-slate-300 flex-shrink-0">
                              {c.owner_name?.charAt(0) || c.name?.charAt(0) || 'U'}
                            </div>
                            <div>
                              <div className="font-bold text-white flex items-center gap-1.5">
                                <span>{c.name}</span>
                              </div>
                              <span className="text-[11px] text-slate-400">{c.owner_email}</span>
                            </div>
                          </div>
                        </td>

                        <td className="py-4 px-6">
                          <div className="space-y-1">
                            <span className={`px-2.5 py-0.5 rounded-lg text-xs font-semibold border inline-block ${
                              c.plan_slug === 'vip' 
                                ? 'bg-amber-500/10 border-amber-500/20 text-amber-300' 
                                : c.plan_slug === 'pro'
                                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                                : 'bg-slate-800 border-slate-700 text-slate-300'
                            }`}>
                              {c.plan_name} (${c.plan_price || 0})
                            </span>
                            <div className="text-[11px] text-slate-400 flex items-center gap-1">
                              <Radio className="w-3 h-3 text-emerald-400" />
                              <span>{c.channels_count} / {c.max_channels} قنوات</span>
                            </div>
                          </div>
                        </td>

                        <td className="py-4 px-6">
                          {c.keywords && c.keywords.length > 0 ? (
                            <div className="flex flex-wrap gap-1 max-w-xs">
                              {c.keywords.map((kw, i) => (
                                <span key={i} className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono text-[11px] font-semibold">
                                  {kw}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-500 italic text-[11px]">لا توجد كلمات بعد</span>
                          )}
                        </td>

                        <td className="py-4 px-6">
                          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${
                            isSuspended
                              ? 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                              : isExpired
                              ? 'bg-slate-800 border-slate-700 text-slate-400'
                              : isExpiring
                              ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                              : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                          }`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${
                              isSuspended ? 'bg-rose-400' : isExpired ? 'bg-slate-400' : isExpiring ? 'bg-amber-400' : 'bg-emerald-400'
                            }`} />
                            <span>
                              {c.subscription_status === 'active' ? 'نشط' :
                               c.subscription_status === 'trial' ? 'تجريبي' :
                               c.subscription_status === 'suspended' ? 'معلق' : 'منتهي'}
                            </span>
                          </span>
                        </td>

                        <td className="py-4 px-6">
                          <span className={`font-bold ${isExpiring ? 'text-amber-400' : isExpired ? 'text-rose-400' : 'text-slate-200'}`}>
                            {c.days_remaining > 0 ? `${c.days_remaining} يوم متبقي` : 'منتهي الصلاحية'}
                          </span>
                        </td>

                        <td className="py-4 px-6">
                          <div className="flex items-center justify-center gap-2">
                            <button
                              title="تمديد الاشتراك 30 يوم"
                              onClick={() => handleQuickExtend(c.id, 30)}
                              disabled={actionLoading === c.id}
                              className="px-2.5 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-400 text-[11px] font-semibold transition-all"
                            >
                              +30 يوم
                            </button>

                            <button
                              title={isSuspended ? 'استئناف وتفعيل الاشتراك' : 'إيقاف الاشتراك مؤقتاً'}
                              onClick={() => handleToggleStatus(c.id, c.subscription_status)}
                              disabled={actionLoading === c.id}
                              className={`p-1.5 rounded-lg border text-[11px] font-semibold transition-all ${
                                isSuspended
                                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/20'
                                  : 'bg-rose-500/10 border-rose-500/20 text-rose-400 hover:bg-rose-500/20'
                              }`}
                            >
                              {isSuspended ? <PlayCircle className="w-4 h-4" /> : <PauseCircle className="w-4 h-4" />}
                            </button>

                            <button
                              title="لوحة التحكم الشاملة بهذا العميل"
                              onClick={() => openCustomerModal(c)}
                              className="px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 hover:border-emerald-500 hover:text-emerald-400 text-slate-200 text-[11px] font-semibold transition-all flex items-center gap-1.5"
                            >
                              <Sliders className="w-3.5 h-3.5 text-emerald-400" />
                              <span>الكلمات والتحكم</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* FULL CONTROL CUSTOMER MODAL */}
      {selectedCustomer && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4" dir="rtl">
          <div className="bg-slate-900 border-t sm:border border-slate-800 rounded-t-3xl sm:rounded-2xl w-full max-w-3xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="p-4 sm:p-6 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
              <div className="flex items-center gap-3 overflow-hidden">
                <div className="w-9 sm:w-10 h-9 sm:h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold flex-shrink-0">
                  <Sliders className="w-4 sm:w-5 h-4 sm:h-5" />
                </div>
                <div className="overflow-hidden">
                  <h3 className="text-sm sm:text-base font-bold text-white truncate">
                    إدارة المشترك: {selectedCustomer.name}
                  </h3>
                  <p className="text-[11px] text-slate-400 truncate">{selectedCustomer.owner_email}</p>
                </div>
              </div>
              <button
                onClick={closeCustomerModal}
                className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition-colors flex-shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Tabs Navigation */}
            <div className="flex border-b border-slate-800 bg-slate-950/20 px-4 sm:px-6 gap-2 sm:gap-4 overflow-x-auto">
              <button
                onClick={() => setActiveModalTab('subscription')}
                className={`py-3 text-xs font-bold border-b-2 transition-colors whitespace-nowrap ${
                  activeModalTab === 'subscription'
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                الاشتراك والمدة
              </button>
              <button
                onClick={() => setActiveModalTab('channels')}
                className={`py-3 text-xs font-bold border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5 ${
                  activeModalTab === 'channels'
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Zap className="w-3.5 h-3.5" />
                <span>القنوات والكلمات المفتاحية ({customerDetails?.automations?.length || 0})</span>
              </button>
              <button
                onClick={() => setActiveModalTab('security')}
                className={`py-3 text-xs font-bold border-b-2 transition-colors whitespace-nowrap ${
                  activeModalTab === 'security'
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                الأمان وإعادة التعيين
              </button>
            </div>

            {/* Modal Body Content */}
            <div className="p-4 sm:p-6 overflow-y-auto flex-1 space-y-4 text-xs">
              {/* TAB 1: SUBSCRIPTION */}
              {activeModalTab === 'subscription' && (
                <form onSubmit={handleSaveSubscription} className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                        الباقة المخصصة
                      </label>
                      <select
                        value={editPlanSlug}
                        onChange={(e) => setEditPlanSlug(e.target.value)}
                        className="w-full px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs outline-none"
                      >
                        <option value="starter">الباقة الأساسية - Starter ($20 - 1 قناة)</option>
                        <option value="pro">الباقة الاحترافية - Pro ($40 - 3 قنوات)</option>
                        <option value="vip">باقة النخبة - VIP ($100 - 10 قنوات)</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                        حالة الاشتراك
                      </label>
                      <select
                        value={editStatus}
                        onChange={(e) => setEditStatus(e.target.value)}
                        className="w-full px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs outline-none"
                      >
                        <option value="active">نشط (Active)</option>
                        <option value="trial">تجريبي (Trial)</option>
                        <option value="suspended">معلق مؤقتاً (Suspended)</option>
                        <option value="expired">منتهي الصلاحية (Expired)</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                      تاريخ انتهاء الاشتراك
                    </label>
                    <input
                      type="date"
                      value={editExpiryDate}
                      onChange={(e) => setEditExpiryDate(e.target.value)}
                      className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs outline-none font-mono"
                    />
                    <div className="flex items-center gap-2 mt-2">
                      <span className="text-[11px] text-slate-400">إضافة سريعة:</span>
                      <button
                        type="button"
                        onClick={() => handleAddDaysToForm(30)}
                        className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px]"
                      >
                        +30 يوم
                      </button>
                      <button
                        type="button"
                        onClick={() => handleAddDaysToForm(90)}
                        className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px]"
                      >
                        +3 أشهر
                      </button>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-slate-800 flex justify-end gap-2.5">
                    <button
                      type="button"
                      onClick={closeCustomerModal}
                      className="px-4 py-2.5 rounded-xl bg-slate-800 text-slate-300 text-xs font-semibold"
                    >
                      إلغاء
                    </button>
                    <button
                      type="submit"
                      disabled={savingSub}
                      className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold shadow-lg transition-all"
                    >
                      {savingSub ? 'جاري الحفظ...' : 'حفظ بيانات الاشتراك'}
                    </button>
                  </div>
                </form>
              )}

              {/* TAB 2: CHANNELS & AUTOMATIONS MANAGER */}
              {activeModalTab === 'channels' && (
                <div className="space-y-4">
                  {detailsLoading ? (
                    <div className="p-8 text-center text-slate-400">جاري تحميل القنوات والأهداف...</div>
                  ) : (
                    <>
                      {/* Top Action Bar */}
                      <div className="flex items-center justify-between bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                        <div>
                          <span className="text-xs font-bold text-white block">الأهداف والكلمات المفتاحية المراقبة</span>
                          <span className="text-[11px] text-slate-400">يمكنك تعديل أي كلمة أو إضافة كلمات جديدة نيابة عن العميل فوراً.</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => startAddAutomation()}
                          className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-md transition-all"
                        >
                          <Plus className="w-4 h-4" />
                          <span>إضافة هدف جديد</span>
                        </button>
                      </div>

                      {/* Inline Form (Create or Edit Automation) */}
                      {(isAddingAuto || editingAuto) && (
                        <form onSubmit={handleSaveAutomation} className="p-4 rounded-2xl bg-slate-950 border border-emerald-500/40 space-y-3 animate-in fade-in zoom-in-95 duration-100">
                          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                            <h4 className="font-bold text-emerald-400 text-xs flex items-center gap-1.5">
                              <Zap className="w-4 h-4" />
                              <span>{editingAuto ? `تعديل الهدف: ${editingAuto.name}` : 'إضافة هدف مراقبة جديد للعميل'}</span>
                            </h4>
                            <button
                              type="button"
                              onClick={() => { setEditingAuto(null); setIsAddingAuto(false); }}
                              className="text-slate-400 hover:text-white"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div>
                              <label className="block text-[11px] font-semibold text-slate-300 mb-1">اسم الهدف</label>
                              <input
                                type="text"
                                placeholder="مثال: الهدف الأول TP1 أو ارباحكم"
                                value={autoForm.name}
                                onChange={(e) => setAutoForm({ ...autoForm, name: e.target.value })}
                                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-white text-xs outline-none focus:border-emerald-500"
                                required
                              />
                            </div>

                            <div>
                              <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                                الكلمة المفتاحية المراقبة (Trigger Keyword)
                              </label>
                              <input
                                type="text"
                                placeholder="مثال: TP1 أو ارباحكم"
                                value={autoForm.trigger_value}
                                onChange={(e) => setAutoForm({ ...autoForm, trigger_value: e.target.value })}
                                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-emerald-400 font-mono font-bold text-xs outline-none focus:border-emerald-500"
                                required
                              />
                            </div>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                            <div>
                              <label className="block text-[11px] font-semibold text-slate-300 mb-1">القناة المستهدفة</label>
                              <select
                                value={autoForm.channel_id}
                                onChange={(e) => setAutoForm({ ...autoForm, channel_id: e.target.value })}
                                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-white text-xs outline-none"
                              >
                                {customerDetails?.channels?.map((ch) => (
                                  <option key={ch.id} value={ch.id}>{ch.title}</option>
                                ))}
                              </select>
                            </div>

                            <div>
                              <label className="block text-[11px] font-semibold text-slate-300 mb-1">نوع المطابقة</label>
                              <select
                                value={autoForm.trigger_type}
                                onChange={(e) => setAutoForm({ ...autoForm, trigger_type: e.target.value })}
                                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-white text-xs outline-none"
                              >
                                <option value="contains">تتضمن الكلمة (Contains - موصى به)</option>
                                <option value="exact">مطابقة تامة (Exact)</option>
                                <option value="prefix">تبدأ بالكلمة (Prefix)</option>
                              </select>
                            </div>

                            <div>
                              <label className="block text-[11px] font-semibold text-slate-300 mb-1">عدد الريفيوهات للنشر</label>
                              <select
                                value={autoForm.reviews_count}
                                onChange={(e) => setAutoForm({ ...autoForm, reviews_count: parseInt(e.target.value) })}
                                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-white text-xs outline-none font-bold text-emerald-400"
                              >
                                <option value={1}>1 رسالة ريفيو</option>
                                <option value={2}>2 رسائل ريفيو</option>
                                <option value={3}>3 رسائل ريفيو</option>
                                <option value={4}>4 رسائل ريفيو</option>
                                <option value={5}>5 رسائل ريفيو</option>
                              </select>
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <label className="block text-[11px] font-semibold text-slate-300 mb-1">تأخير أول ريفيو (ثواني)</label>
                              <input
                                type="number"
                                min="1"
                                max="60"
                                value={autoForm.initial_delay_seconds}
                                onChange={(e) => setAutoForm({ ...autoForm, initial_delay_seconds: parseFloat(e.target.value) || 5.0 })}
                                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-white text-xs outline-none"
                              />
                            </div>
                            <div>
                              <label className="block text-[11px] font-semibold text-slate-300 mb-1">فاصل زمني بين الرسائل (ثواني)</label>
                              <input
                                type="number"
                                min="1"
                                max="60"
                                value={autoForm.delay_seconds}
                                onChange={(e) => setAutoForm({ ...autoForm, delay_seconds: parseFloat(e.target.value) || 4.0 })}
                                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-white text-xs outline-none"
                              />
                            </div>
                          </div>

                          <div className="flex justify-end gap-2 pt-2">
                            <button
                              type="button"
                              onClick={() => { setEditingAuto(null); setIsAddingAuto(false); }}
                              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
                            >
                              إلغاء
                            </button>
                            <button
                              type="submit"
                              disabled={savingAuto}
                              className="px-6 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold shadow-md"
                            >
                              {savingAuto ? 'جاري الحفظ...' : editingAuto ? 'حفظ التعديلات' : 'إضافة الهدف الآن'}
                            </button>
                          </div>
                        </form>
                      )}

                      {/* Channels and Their Automations List */}
                      {!customerDetails?.channels || customerDetails.channels.length === 0 ? (
                        <div className="p-8 text-center text-slate-400 bg-slate-950 rounded-2xl border border-slate-800">
                          لا توجد قنوات مربوطة لهذا المشترك حتى الآن.
                        </div>
                      ) : (
                        customerDetails.channels.map((ch) => {
                          const channelAutos = customerDetails.automations?.filter(a => a.channel_id === ch.id) || [];

                          return (
                            <div key={ch.id} className="rounded-2xl bg-slate-950 border border-slate-800 overflow-hidden shadow-sm">
                              {/* Channel Title Bar */}
                              <div className="p-3.5 bg-slate-900/60 border-b border-slate-800 flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                  <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold">
                                    <Radio className="w-3.5 h-3.5" />
                                  </div>
                                  <div>
                                    <h4 className="text-xs font-bold text-white flex items-center gap-2">
                                      <span>{ch.title}</span>
                                      <span className="text-[10px] text-slate-400 font-mono font-normal">({ch.chat_id})</span>
                                    </h4>
                                  </div>
                                </div>

                                <div className="flex items-center gap-2">
                                  <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                                    ch.bot_is_admin 
                                      ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                                      : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                                  }`}>
                                    {ch.bot_is_admin ? 'مشرف مفعل' : 'البوت ليس مشرف'}
                                  </span>

                                  <button
                                    type="button"
                                    onClick={() => startAddAutomation(ch.id)}
                                    className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-emerald-400 text-[11px] font-bold border border-slate-700 flex items-center gap-1"
                                  >
                                    <Plus className="w-3 h-3" />
                                    <span>هدف للقناة</span>
                                  </button>
                                </div>
                              </div>

                              {/* Channel Automations */}
                              <div className="p-3 space-y-2">
                                {channelAutos.length === 0 ? (
                                  <div className="py-4 text-center text-slate-500 text-xs italic">
                                    لا توجد أهداف مراقبة لهذه القناة بعد. انقر على "هدف للقناة" لإضافة كلمات مفتاحية.
                                  </div>
                                ) : (
                                  channelAutos.map((auto) => (
                                    <div key={auto.id} className="p-3 rounded-xl bg-slate-900/60 border border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:border-slate-700 transition-colors">
                                      <div className="space-y-1">
                                        <div className="flex items-center gap-2">
                                          <span className="font-bold text-white text-xs">{auto.name}</span>
                                          <span className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono text-xs font-bold">
                                            {auto.trigger_value}
                                          </span>
                                          <span className="text-[10px] text-slate-400">({auto.trigger_type})</span>
                                        </div>

                                        <div className="flex items-center gap-3 text-[11px] text-slate-400">
                                          <span>📦 {auto.reviews_count || 2} ريفيو</span>
                                          <span>⏱️ تأخير: {auto.initial_delay_seconds || 5}ث / فاصل: {auto.delay_seconds || 4}ث</span>
                                          <span>⚡ عدد مرات النشر: {auto.total_executions || 0}</span>
                                        </div>
                                      </div>

                                      <div className="flex items-center gap-2 self-end sm:self-center">
                                        <button
                                          type="button"
                                          onClick={() => handleToggleAuto(auto.id)}
                                          className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-all ${
                                            auto.is_active
                                              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                                              : 'bg-slate-800 border-slate-700 text-slate-400'
                                          }`}
                                        >
                                          {auto.is_active ? 'نشط 🟢' : 'معطل ⚪'}
                                        </button>

                                        <button
                                          type="button"
                                          onClick={() => startEditAutomation(auto)}
                                          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
                                          title="تعديل الهدف والكلمة"
                                        >
                                          <Edit3 className="w-3.5 h-3.5 text-emerald-400" />
                                        </button>

                                        <button
                                          type="button"
                                          onClick={() => handleDeleteAuto(auto.id, auto.name)}
                                          className="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 transition-colors"
                                          title="حذف الهدف"
                                        >
                                          <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                      </div>
                                    </div>
                                  ))
                                )}
                              </div>
                            </div>
                          );
                        })
                      )}
                    </>
                  )}
                </div>
              )}

              {/* TAB 3: SECURITY & RESET */}
              {activeModalTab === 'security' && (
                <div className="space-y-6">
                  <form onSubmit={handleResetPassword} className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                    <h4 className="font-bold text-white text-xs flex items-center gap-1.5">
                      <KeyRound className="w-4 h-4 text-amber-400" />
                      <span>تعيين كلمة مرور جديدة للمشترك</span>
                    </h4>
                    <input
                      type="password"
                      placeholder="أدخل كلمة المرور الجديدة..."
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white text-xs outline-none"
                    />
                    <button
                      type="submit"
                      disabled={savingPassword || !newPassword}
                      className="w-full py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-xs font-bold transition-all"
                    >
                      {savingPassword ? 'جاري التعيين...' : 'تحديث كلمة المرور'}
                    </button>
                  </form>

                  <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-500/30 space-y-2">
                    <h4 className="font-bold text-rose-400 text-xs">منطقة الخطر: حذف الحساب</h4>
                    <p className="text-[11px] text-slate-400">حذف هذا المشترك سيحذف كافة قنواته وأتمتاته وسجلاته فوراً من السيرفر.</p>
                    <button
                      type="button"
                      onClick={handleDeleteCustomer}
                      className="w-full py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition-all flex items-center justify-center gap-1.5"
                    >
                      <Trash2 className="w-4 h-4" />
                      <span>حذف المشترك نهائياً</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
