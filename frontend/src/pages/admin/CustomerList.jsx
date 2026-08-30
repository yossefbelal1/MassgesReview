import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { 
  Users, Search, ShieldAlert, CheckCircle2, Clock, 
  Calendar, RefreshCw, X, ArrowLeft, ArrowRight, ShieldCheck, 
  Sliders, KeyRound, Trash2, Edit3, PauseCircle, PlayCircle, Plus,
  Radio, Workflow, Layers, AlertTriangle, ExternalLink, ChevronRight,
  Sparkles, Check
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
  const [activeModalTab, setActiveModalTab] = useState('subscription');

  // Edit Subscription Form State
  const [editPlanSlug, setEditPlanSlug] = useState('pro');
  const [editStatus, setEditStatus] = useState('active');
  const [editExpiryDate, setEditExpiryDate] = useState('');
  const [savingSub, setSavingSub] = useState(false);

  // Reset Password State
  const [newPassword, setNewPassword] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    fetchCustomers();
  }, []);

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

  const closeCustomerModal = () => {
    setSelectedCustomer(null);
    setCustomerDetails(null);
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
      alert('تم تحديث بيانات اشتراك العميل بنجاح!');
      await fetchCustomers();
      closeCustomerModal();
    } catch (err) {
      alert(err.response?.data?.detail || 'فشل حفظ تعديلات الاشتراك');
    } finally {
      setSavingSub(false);
    }
  };

  // Add Days Quick Shortcut inside Modal
  const handleAddDaysToForm = (days) => {
    const base = editExpiryDate ? new Date(editExpiryDate) : new Date();
    base.setDate(base.getDate() + days);
    setEditExpiryDate(base.toISOString().split('T')[0]);
  };

  // Reset Customer Password
  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (!selectedCustomer || !newPassword) return;

    try {
      setSavingPassword(true);
      const res = await apiClient.post(`/admin/customers/${selectedCustomer.id}/reset-password`, {
        new_password: newPassword
      });
      alert(res.data.message || 'تم تعيين كلمة المرور الجديدة بنجاح');
      setNewPassword('');
    } catch (err) {
      alert(err.response?.data?.detail || 'فشل تعيين كلمة المرور');
    } finally {
      setSavingPassword(false);
    }
  };

  // Delete Customer
  const handleDeleteCustomer = async () => {
    if (!selectedCustomer) return;
    const confirmName = window.prompt(`تحذير أمني: لحذف هذا المشترك وكافة قنواته وبياناته نهائياً، اكتب اسم المشترك (${selectedCustomer.name}):`);
    if (confirmName !== selectedCustomer.name) {
      alert('لم يتم الحذف: الاسم غير متطابق.');
      return;
    }

    try {
      setActionLoading(selectedCustomer.id);
      await apiClient.delete(`/admin/customers/${selectedCustomer.id}`);
      alert('تم حذف المشترك بنجاح.');
      closeCustomerModal();
      await fetchCustomers();
    } catch (err) {
      alert('فشل حذف المشترك');
    } finally {
      setActionLoading(null);
    }
  };

  // Filtering
  const filtered = customers.filter(c => {
    const term = searchTerm.toLowerCase().trim();
    const matchSearch = !term || (
      c.name?.toLowerCase().includes(term) ||
      c.owner_email?.toLowerCase().includes(term) ||
      c.owner_name?.toLowerCase().includes(term) ||
      c.slug?.toLowerCase().includes(term)
    );

    const matchStatus = statusFilter === 'all' || c.subscription_status === statusFilter;
    const matchPlan = planFilter === 'all' || c.plan_slug === planFilter;

    return matchSearch && matchStatus && matchPlan;
  });

  const totalActive = customers.filter(c => c.subscription_status === 'active' || c.subscription_status === 'trial').length;
  const totalSuspended = customers.filter(c => c.subscription_status === 'suspended').length;
  const totalExpiringSoon = customers.filter(c => c.days_remaining <= 7 && c.days_remaining > 0 && c.subscription_status === 'active').length;

  return (
    <div className="space-y-4 sm:space-y-6 max-w-7xl mx-auto" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-lg sm:text-xl font-bold text-white tracking-tight">إدارة العملاء والمشتركين</h1>
          <p className="text-[11px] sm:text-xs text-slate-400 mt-0.5">التحكم في اشتراكات العملاء، تمديد الباقات، ومراقبة القنوات.</p>
        </div>

        <button
          onClick={fetchCustomers}
          className="px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 text-xs font-semibold flex items-center justify-center gap-1.5 self-start sm:self-auto"
        >
          <RefreshCw className="w-4 h-4 text-emerald-400" />
          <span>تحديث القائمة</span>
        </button>
      </div>

      {/* KPI Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3.5 sm:p-4">
          <span className="text-[10px] sm:text-[11px] text-slate-400 font-medium block mb-1">إجمالي العملاء</span>
          <span className="text-xl sm:text-2xl font-extrabold text-white">{customers.length}</span>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3.5 sm:p-4">
          <span className="text-[10px] sm:text-[11px] text-slate-400 font-medium block mb-1">الاشتراكات النشطة</span>
          <span className="text-xl sm:text-2xl font-extrabold text-emerald-400">{totalActive}</span>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3.5 sm:p-4">
          <span className="text-[10px] sm:text-[11px] text-slate-400 font-medium block mb-1">تنتهي قريباً</span>
          <span className="text-xl sm:text-2xl font-extrabold text-amber-400">{totalExpiringSoon}</span>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3.5 sm:p-4">
          <span className="text-[10px] sm:text-[11px] text-slate-400 font-medium block mb-1">المعلقة / المتوقفة</span>
          <span className="text-xl sm:text-2xl font-extrabold text-rose-400">{totalSuspended}</span>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3.5 sm:p-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-500 absolute right-3 top-2.5 sm:top-3" />
          <input
            type="text"
            placeholder="بحث بالاسم، البريد، أو المعرف..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pr-9 pl-4 py-2 sm:py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-xs outline-none"
          />
        </div>

        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="flex-1 sm:flex-none px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs outline-none"
          >
            <option value="all">كافة الحالات</option>
            <option value="active">نشط</option>
            <option value="trial">تجريبي</option>
            <option value="suspended">معلق</option>
            <option value="expired">منتهي</option>
          </select>

          <select
            value={planFilter}
            onChange={(e) => setPlanFilter(e.target.value)}
            className="flex-1 sm:flex-none px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs outline-none"
          >
            <option value="all">كافة الباقات</option>
            <option value="starter">Starter ($20)</option>
            <option value="pro">Pro ($40)</option>
            <option value="vip">VIP ($100)</option>
          </select>
        </div>
      </div>

      {/* Customers List & Table */}
      {loading ? (
        <div className="p-12 text-center text-slate-400 bg-slate-900 border border-slate-800 rounded-2xl">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500 mx-auto mb-3"></div>
          <span>جاري تحميل بيانات المشتركين...</span>
        </div>
      ) : filtered.length === 0 ? (
        <div className="p-12 text-center text-slate-400 bg-slate-900 border border-slate-800 rounded-2xl">
          لا يوجد عملاء يطابقون خيارات البحث.
        </div>
      ) : (
        <>
          {/* Mobile Customer Cards (< lg) */}
          <div className="lg:hidden space-y-3">
            {filtered.map((c) => {
              const isExpiring = c.days_remaining <= 7 && c.days_remaining > 0 && c.subscription_status === 'active';
              const isSuspended = c.subscription_status === 'suspended';
              const isExpired = c.days_remaining === 0 || c.subscription_status === 'expired';

              return (
                <div 
                  key={c.id} 
                  className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3 shadow-md"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2.5 overflow-hidden">
                      <div className="w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-slate-300 text-sm flex-shrink-0">
                        {c.owner_name?.charAt(0) || c.name?.charAt(0) || 'U'}
                      </div>
                      <div className="overflow-hidden">
                        <h4 className="text-xs font-bold text-white truncate">{c.name}</h4>
                        <p className="text-[11px] text-slate-400 truncate">{c.owner_email}</p>
                      </div>
                    </div>

                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border flex-shrink-0 ${
                      isSuspended
                        ? 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                        : isExpired
                        ? 'bg-slate-800 border-slate-700 text-slate-400'
                        : isExpiring
                        ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                        : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                    }`}>
                      {c.subscription_status === 'active' ? 'نشط' :
                       c.subscription_status === 'trial' ? 'تجريبي' :
                       c.subscription_status === 'suspended' ? 'معلق' : 'منتهي'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="p-2 rounded-xl bg-slate-950/60 border border-slate-800/80">
                      <span className="text-[10px] text-slate-400 block">الباقة</span>
                      <strong className="text-emerald-400 text-xs font-bold">{c.plan_name}</strong>
                    </div>
                    <div className="p-2 rounded-xl bg-slate-950/60 border border-slate-800/80">
                      <span className="text-[10px] text-slate-400 block">القنوات المربوطة</span>
                      <strong className="text-white text-xs">{c.channels_count} / {c.max_channels}</strong>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-slate-800 flex items-center justify-between gap-2">
                    <span className={`text-[11px] font-bold ${isExpiring ? 'text-amber-400' : isExpired ? 'text-rose-400' : 'text-slate-300'}`}>
                      {c.days_remaining > 0 ? `${c.days_remaining} يوم متبقي` : 'منتهي الصلاحية'}
                    </span>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => handleQuickExtend(c.id, 30)}
                        disabled={actionLoading === c.id}
                        className="px-2.5 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-bold"
                      >
                        +30 يوم
                      </button>

                      <button
                        onClick={() => openCustomerModal(c)}
                        className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[10px] font-bold flex items-center gap-1"
                      >
                        <Sliders className="w-3 h-3" />
                        <span>إدارة</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Desktop Table (>= lg) */}
          <div className="hidden lg:block bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-right border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-950/60 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                    <th className="py-4 px-6">المشترك / الحساب</th>
                    <th className="py-4 px-6">الباقة المفعلة</th>
                    <th className="py-4 px-6">القنوات المربوطة</th>
                    <th className="py-4 px-6">حالة الاشتراك</th>
                    <th className="py-4 px-6">المدة المتبقية</th>
                    <th className="py-4 px-6 text-center">إجراءات الإدارة السريعة</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-xs">
                  {filtered.map((c) => {
                    const isExpiring = c.days_remaining <= 7 && c.days_remaining > 0 && c.subscription_status === 'active';
                    const isSuspended = c.subscription_status === 'suspended';
                    const isExpired = c.days_remaining === 0 || c.subscription_status === 'expired';

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
                          <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold border inline-block ${
                            c.plan_slug === 'vip' 
                              ? 'bg-amber-500/10 border-amber-500/20 text-amber-300' 
                              : c.plan_slug === 'pro'
                              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                              : 'bg-slate-800 border-slate-700 text-slate-300'
                          }`}>
                            {c.plan_name} (${c.plan_price || 0})
                          </span>
                        </td>

                        <td className="py-4 px-6">
                          <div className="flex items-center gap-1.5 text-slate-300">
                            <Radio className="w-3.5 h-3.5 text-emerald-400" />
                            <span><strong>{c.channels_count}</strong> / {c.max_channels} قنوات</span>
                          </div>
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
                              <Sliders className="w-3.5 h-3.5" />
                              <span>تحكم كامل</span>
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

      {/* FULL CONTROL CUSTOMER MODAL (Mobile-Friendly Slide-Up / Dialog) */}
      {selectedCustomer && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4" dir="rtl">
          <div className="bg-slate-900 border-t sm:border border-slate-800 rounded-t-3xl sm:rounded-2xl w-full max-w-2xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
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
                className={`py-3 text-xs font-bold border-b-2 transition-colors whitespace-nowrap ${
                  activeModalTab === 'channels'
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                القنوات والأهداف ({customerDetails?.channels?.length || 0})
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

              {activeModalTab === 'channels' && (
                <div className="space-y-3">
                  {detailsLoading ? (
                    <div className="p-8 text-center text-slate-400">جاري تحميل القنوات...</div>
                  ) : !customerDetails?.channels || customerDetails.channels.length === 0 ? (
                    <div className="p-8 text-center text-slate-400 bg-slate-950 rounded-xl">
                      لا توجد قنوات مربوطة لهذا المشترك حتى الآن.
                    </div>
                  ) : (
                    customerDetails.channels.map((ch) => (
                      <div key={ch.id} className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                        <div>
                          <h4 className="text-xs font-bold text-white">{ch.title}</h4>
                          <p className="text-[10px] text-slate-400 font-mono">{ch.telegram_chat_id}</p>
                        </div>
                        <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded font-bold">
                          {ch.automations_count || 0} أتمتة
                        </span>
                      </div>
                    ))
                  )}
                </div>
              )}

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
