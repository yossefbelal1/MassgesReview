import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { 
  Users, Search, ShieldAlert, CheckCircle2, Clock, 
  Calendar, RefreshCw, X, ArrowLeft, ArrowRight, ShieldCheck, 
  Sliders, KeyRound, Trash2, Edit3, PauseCircle, PlayCircle, Plus,
  Radio, Workflow, Layers, AlertTriangle, ExternalLink, ChevronRight
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
  const [activeModalTab, setActiveModalTab] = useState('subscription'); // 'subscription', 'channels', 'security'

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
    <div className="space-y-6 max-w-7xl mx-auto" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">إدارة العملاء والمشتركين</h1>
          <p className="text-xs text-slate-400 mt-1">التحكم الشامل في اشتراكات العملاء، تمديد وتعديل الباقات، ومراقبة القنوات والأهداف.</p>
        </div>

        <button
          onClick={fetchCustomers}
          className="px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 text-xs font-semibold flex items-center justify-center gap-2 self-start sm:self-auto"
        >
          <RefreshCw className="w-4 h-4 text-emerald-400" />
          <span>تحديث القائمة</span>
        </button>
      </div>

      {/* KPI Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
          <span className="text-[11px] text-slate-400 font-medium block mb-1">إجمالي العملاء</span>
          <span className="text-2xl font-extrabold text-white">{customers.length}</span>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
          <span className="text-[11px] text-slate-400 font-medium block mb-1">اشتراكات نشطة</span>
          <span className="text-2xl font-extrabold text-emerald-400">{totalActive}</span>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
          <span className="text-[11px] text-slate-400 font-medium block mb-1">تنتهي خلال 7 أيام</span>
          <span className="text-2xl font-extrabold text-amber-400">{totalExpiringSoon}</span>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
          <span className="text-[11px] text-slate-400 font-medium block mb-1">اشتراكات معلقة / منتهية</span>
          <span className="text-2xl font-extrabold text-rose-400">{totalSuspended}</span>
        </div>
      </div>

      {/* Search & Filter Controls */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 flex flex-col md:flex-row items-center gap-3">
        <div className="relative w-full md:flex-1">
          <Search className="w-4 h-4 text-slate-500 absolute right-3 top-2.5" />
          <input
            type="text"
            placeholder="بحث باسم العميل، البريد الإلكتروني..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pr-9 pl-4 py-2 rounded-xl bg-slate-950 border border-slate-800 focus:border-emerald-500 text-white text-xs outline-none"
          />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-300 text-xs outline-none flex-1 md:flex-none"
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
            className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-300 text-xs outline-none flex-1 md:flex-none"
          >
            <option value="all">كافة الباقات</option>
            <option value="starter">Starter ($20)</option>
            <option value="pro">Pro ($40)</option>
            <option value="vip">VIP ($100)</option>
          </select>
        </div>
      </div>

      {/* Customers Table */}
      {loading ? (
        <div className="p-16 text-center text-slate-400 bg-slate-900 border border-slate-800 rounded-2xl">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500 mx-auto mb-3"></div>
          <span>جاري تحميل بيانات المشتركين...</span>
        </div>
      ) : filtered.length === 0 ? (
        <div className="p-16 text-center text-slate-400 bg-slate-900 border border-slate-800 rounded-2xl">
          لا يوجد عملاء يطابقون خيارات البحث.
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
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
                      {/* Customer / Tenant Info */}
                      <td className="py-4 px-6">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-slate-300 flex-shrink-0">
                            {c.owner_name?.charAt(0) || c.name?.charAt(0) || 'U'}
                          </div>
                          <div>
                            <div className="font-bold text-white flex items-center gap-1.5">
                              <span>{c.name}</span>
                              {c.owner_email === 'kamelyossef111@gmail.com' && (
                                <span className="text-[10px] bg-amber-500/10 border border-amber-500/20 text-amber-400 px-1.5 py-0.2 rounded font-mono">حسابك</span>
                              )}
                            </div>
                            <span className="text-[11px] text-slate-400">{c.owner_email}</span>
                          </div>
                        </div>
                      </td>

                      {/* Plan */}
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

                      {/* Channels Usage */}
                      <td className="py-4 px-6">
                        <div className="flex items-center gap-1.5 text-slate-300">
                          <Radio className="w-3.5 h-3.5 text-emerald-400" />
                          <span><strong>{c.channels_count}</strong> / {c.max_channels} قنوات</span>
                        </div>
                      </td>

                      {/* Status */}
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

                      {/* Days Remaining */}
                      <td className="py-4 px-6">
                        <span className={`font-bold ${isExpiring ? 'text-amber-400' : isExpired ? 'text-rose-400' : 'text-slate-200'}`}>
                          {c.days_remaining > 0 ? `${c.days_remaining} يوم متبقي` : 'منتهي الصلاحية'}
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="py-4 px-6">
                        <div className="flex items-center justify-center gap-2">
                          {/* Quick Extend +30 */}
                          <button
                            title="تمديد الاشتراك 30 يوم"
                            onClick={() => handleQuickExtend(c.id, 30)}
                            disabled={actionLoading === c.id}
                            className="px-2.5 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-400 text-[11px] font-semibold transition-all"
                          >
                            +30 يوم
                          </button>

                          {/* Toggle Suspend / Resume */}
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

                          {/* Full Control Modal Trigger */}
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
      )}

      {/* FULL CONTROL CUSTOMER MODAL */}
      {selectedCustomer && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4" dir="rtl">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold">
                  <Sliders className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <span>إدارة المشترك: {selectedCustomer.name}</span>
                    <span className="text-xs text-slate-400 font-normal">({selectedCustomer.owner_email})</span>
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">تعديل الخطة والمدة، فحص القنوات والأهداف، والتحكم بالأمان.</p>
                </div>
              </div>
              <button
                onClick={closeCustomerModal}
                className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Tabs Navigation */}
            <div className="flex border-b border-slate-800 bg-slate-950/20 px-6 gap-4">
              <button
                onClick={() => setActiveModalTab('subscription')}
                className={`py-3 text-xs font-semibold border-b-2 transition-all ${
                  activeModalTab === 'subscription'
                    ? 'border-emerald-500 text-emerald-400 font-bold'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                ⚙️ التحكم في الاشتراك والمدة
              </button>
              <button
                onClick={() => setActiveModalTab('channels')}
                className={`py-3 text-xs font-semibold border-b-2 transition-all ${
                  activeModalTab === 'channels'
                    ? 'border-emerald-500 text-emerald-400 font-bold'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                📡 قنوات وأهداف العميل ({customerDetails?.channels?.length || selectedCustomer.channels_count})
              </button>
              <button
                onClick={() => setActiveModalTab('security')}
                className={`py-3 text-xs font-semibold border-b-2 transition-all ${
                  activeModalTab === 'security'
                    ? 'border-emerald-500 text-emerald-400 font-bold'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                🔒 الأمان وكلمة المرور
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto flex-1 space-y-6">
              {/* TAB 1: SUBSCRIPTION CONTROLS */}
              {activeModalTab === 'subscription' && (
                <form onSubmit={handleSaveSubscription} className="space-y-6">
                  {/* Plan Selector */}
                  <div>
                    <label className="text-xs font-bold text-slate-300 block mb-2">تغيير الباقة المفعلة:</label>
                    <div className="grid grid-cols-3 gap-3">
                      {[
                        { slug: 'starter', name: 'Starter', price: '$20', channels: '1 قناة' },
                        { slug: 'pro', name: 'Pro', price: '$40', channels: '3 قنوات' },
                        { slug: 'vip', name: 'VIP', price: '$100', channels: '10 قنوات' }
                      ].map((p) => (
                        <button
                          type="button"
                          key={p.slug}
                          onClick={() => setEditPlanSlug(p.slug)}
                          className={`p-3 rounded-xl border text-right transition-all ${
                            editPlanSlug === p.slug
                              ? 'bg-emerald-500/10 border-emerald-500 text-emerald-400 ring-1 ring-emerald-500'
                              : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                          }`}
                        >
                          <div className="font-bold text-white text-xs">{p.name} ({p.price})</div>
                          <div className="text-[11px] text-slate-400 mt-1">{p.channels}</div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Status Selector */}
                  <div>
                    <label className="text-xs font-bold text-slate-300 block mb-2">حالة الاشتراك:</label>
                    <select
                      value={editStatus}
                      onChange={(e) => setEditStatus(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs outline-none focus:border-emerald-500"
                    >
                      <option value="active">نشط (Active)</option>
                      <option value="trial">فترة تجريبية (Trial)</option>
                      <option value="suspended">معلق / موقوف (Suspended)</option>
                      <option value="expired">منتهي (Expired)</option>
                    </select>
                  </div>

                  {/* Custom Expiry Date */}
                  <div>
                    <label className="text-xs font-bold text-slate-300 block mb-2">تاريخ انتهاء الاشتراك المحدد:</label>
                    <input
                      type="date"
                      value={editExpiryDate}
                      onChange={(e) => setEditExpiryDate(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs outline-none focus:border-emerald-500"
                    />

                    {/* Quick Extend Shortcuts */}
                    <div className="mt-2.5 flex items-center gap-2">
                      <span className="text-[11px] text-slate-400">إضافة سريعة:</span>
                      {[
                        { label: '+7 أيام', days: 7 },
                        { label: '+15 يوم', days: 15 },
                        { label: '+شهر', days: 30 },
                        { label: '+3 أشهر', days: 90 },
                        { label: '+سنة', days: 365 }
                      ].map((item) => (
                        <button
                          type="button"
                          key={item.days}
                          onClick={() => handleAddDaysToForm(item.days)}
                          className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-semibold transition-colors"
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Save Button */}
                  <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
                    <button
                      type="submit"
                      disabled={savingSub}
                      className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-lg shadow-emerald-950 transition-all flex items-center gap-2"
                    >
                      {savingSub ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                      <span>حفظ تعديلات الاشتراك</span>
                    </button>

                    <button
                      type="button"
                      onClick={closeCustomerModal}
                      className="px-4 py-2.5 rounded-xl bg-slate-800 text-slate-400 hover:text-white text-xs font-semibold"
                    >
                      إلغاء
                    </button>
                  </div>
                </form>
              )}

              {/* TAB 2: CHANNELS & AUTOMATIONS INSPECTOR */}
              {activeModalTab === 'channels' && (
                <div className="space-y-6">
                  {detailsLoading ? (
                    <div className="p-8 text-center text-slate-400">جاري فحص قنوات وأهداف العميل...</div>
                  ) : (
                    <>
                      {/* Channels Section */}
                      <div>
                        <h4 className="text-xs font-bold text-white mb-3 flex items-center gap-2">
                          <Radio className="w-4 h-4 text-emerald-400" />
                          <span>القنوات المربوطة ({customerDetails?.channels?.length || 0}):</span>
                        </h4>

                        {customerDetails?.channels?.length === 0 ? (
                          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-400 text-center">
                            لم يقم هذا العميل بربط أي قناة تيليجرام بعد.
                          </div>
                        ) : (
                          <div className="space-y-2">
                            {customerDetails?.channels?.map((ch) => (
                              <div key={ch.id} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs">
                                <div>
                                  <div className="font-bold text-white">{ch.title || 'قناة بدون اسم'}</div>
                                  <div className="text-[11px] text-slate-400 font-mono mt-0.5">{ch.chat_id}</div>
                                </div>
                                <span className={`px-2 py-1 rounded-md text-[10px] font-bold border ${
                                  ch.bot_is_admin 
                                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                                    : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                                }`}>
                                  {ch.bot_is_admin ? 'مشرف متصل ومفعل' : 'غير مكتمل الصلاحيات'}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Automations Section */}
                      <div>
                        <h4 className="text-xs font-bold text-white mb-3 flex items-center gap-2">
                          <Workflow className="w-4 h-4 text-emerald-400" />
                          <span>الكلمات المفتاحية والأهداف ({customerDetails?.automations?.length || 0}):</span>
                        </h4>

                        {customerDetails?.automations?.length === 0 ? (
                          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-400 text-center">
                            لم يقم هذا العميل بإنشاء أي كلمات مفتاحية بعد.
                          </div>
                        ) : (
                          <div className="grid grid-cols-2 gap-2">
                            {customerDetails?.automations?.map((auto) => (
                              <div key={auto.id} className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs">
                                <div className="font-bold text-emerald-400">{auto.trigger_keyword}</div>
                                <div className="text-[11px] text-slate-400 mt-1">{auto.name || 'بدون اسم'} ({auto.match_type})</div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* TAB 3: SECURITY & RESET PASSWORD */}
              {activeModalTab === 'security' && (
                <div className="space-y-6">
                  <form onSubmit={handleResetPassword} className="space-y-4">
                    <h4 className="text-xs font-bold text-white flex items-center gap-2">
                      <KeyRound className="w-4 h-4 text-amber-400" />
                      <span>إعادة تعيين كلمة مرور العميل:</span>
                    </h4>
                    <p className="text-xs text-slate-400">إذا نسي العميل كلمة مروره، يمكنك تعيين كلمة مرور جديدة له مباشرة.</p>

                    <div>
                      <input
                        type="text"
                        placeholder="اكتب كلمة المرور الجديدة (6 خانات على الأقل)..."
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs outline-none focus:border-emerald-500 font-mono"
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={savingPassword || !newPassword}
                      className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-slate-950 font-bold text-xs transition-colors flex items-center gap-2"
                    >
                      {savingPassword ? <RefreshCw className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
                      <span>تحديث كلمة المرور</span>
                    </button>
                  </form>

                  {/* Danger Zone: Delete Customer */}
                  <div className="pt-6 border-t border-rose-500/20 space-y-3">
                    <h4 className="text-xs font-bold text-rose-400 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4" />
                      <span>حذف المشترك نهائياً (Danger Zone):</span>
                    </h4>
                    <p className="text-xs text-slate-400">سيؤدي هذا إلى حذف حساب العميل وجميع قنواته وأتمتاته وسجل نشره نهائياً من قاعدة البيانات.</p>

                    <button
                      type="button"
                      onClick={handleDeleteCustomer}
                      className="px-4 py-2 rounded-xl bg-rose-600/10 border border-rose-500/30 hover:bg-rose-600 text-rose-400 hover:text-white font-bold text-xs transition-all flex items-center gap-2"
                    >
                      <Trash2 className="w-4 h-4" />
                      <span>حذف هذا المشترك نهائياً</span>
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
