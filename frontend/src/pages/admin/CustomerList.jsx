import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { Users, Search, PlusCircle, ShieldAlert, CheckCircle2, Clock } from 'lucide-react';

export default function CustomerList() {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [actionLoading, setActionLoading] = useState(null);

  useEffect(() => {
    fetchCustomers();
  }, []);

  const fetchCustomers = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/admin/customers');
      setCustomers(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleExtend = async (tenantId, days = 30) => {
    try {
      setActionLoading(tenantId);
      await apiClient.post(`/admin/customers/${tenantId}/subscription/extend?days=${days}`);
      alert(`Subscription extended by ${days} days!`);
      fetchCustomers();
    } catch (err) {
      alert('Failed to extend subscription');
    } finally {
      setActionLoading(null);
    }
  };

  const handleSuspend = async (tenantId) => {
    if (!window.confirm('Are you sure you want to suspend this customer? Automations will immediately stop.')) return;
    try {
      setActionLoading(tenantId);
      await apiClient.post(`/admin/customers/${tenantId}/subscription/suspend`);
      fetchCustomers();
    } catch (err) {
      alert('Failed to suspend subscription');
    } finally {
      setActionLoading(null);
    }
  };

  const filtered = customers.filter(c => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      c.name.toLowerCase().includes(term) ||
      c.owner_email.toLowerCase().includes(term) ||
      c.owner_name.toLowerCase().includes(term)
    );
  });

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Customer Management</h1>
          <p className="text-xs text-slate-400 mt-1">View, manage subscriptions, extend access, and monitor client channels.</p>
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search by name, email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-900 border border-slate-800 focus:border-purple-500 text-white text-xs outline-none"
          />
        </div>
      </div>

      {/* Customers Table */}
      {loading ? (
        <div className="p-12 text-center text-slate-400">Loading customers...</div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-lg">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/40 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  <th className="py-3.5 px-6">Customer / Tenant</th>
                  <th className="py-3.5 px-6">Owner</th>
                  <th className="py-3.5 px-6">Channels</th>
                  <th className="py-3.5 px-6">Plan</th>
                  <th className="py-3.5 px-6">Status / Remaining</th>
                  <th className="py-3.5 px-6 text-right">Admin Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-xs">
                {filtered.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-4 px-6 font-semibold text-white">
                      <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400 font-bold flex items-center justify-center text-xs">
                          {c.name.charAt(0)}
                        </div>
                        <div>
                          <p className="font-bold text-white">{c.name}</p>
                          <p className="text-[11px] text-slate-400 font-mono">{c.slug}</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <p className="text-slate-200 font-medium">{c.owner_name}</p>
                      <p className="text-slate-400 text-[11px]">{c.owner_email}</p>
                    </td>
                    <td className="py-4 px-6">
                      <span className="px-2 py-1 rounded bg-slate-950 border border-slate-800 font-semibold text-slate-300">
                        {c.channels_count} Connected
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      <span className="font-semibold text-purple-400">{c.plan_name}</span>
                    </td>
                    <td className="py-4 px-6">
                      <div className="flex items-center space-x-2">
                        {c.subscription_status === 'active' ? (
                          <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                        ) : (
                          <span className="w-2 h-2 rounded-full bg-rose-400"></span>
                        )}
                        <span className="font-semibold text-white capitalize">{c.subscription_status}</span>
                        <span className="text-slate-400">({c.days_remaining}d)</span>
                      </div>
                    </td>
                    <td className="py-4 px-6 text-right space-x-2">
                      <button
                        onClick={() => handleExtend(c.id, 30)}
                        disabled={actionLoading === c.id}
                        className="px-3 py-1.5 rounded-lg bg-emerald-600/20 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-600/30 text-[11px] font-semibold transition-colors"
                      >
                        +30 Days
                      </button>
                      {c.subscription_status === 'active' && (
                        <button
                          onClick={() => handleSuspend(c.id)}
                          disabled={actionLoading === c.id}
                          className="px-3 py-1.5 rounded-lg bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 text-[11px] font-semibold transition-colors"
                        >
                          Suspend
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
