import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { Sliders, Plus, Check } from 'lucide-react';

export default function PlansManager() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/admin/plans');
      setPlans(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <h1 className="text-xl font-bold text-white tracking-tight">Plans & SaaS Capacity Configuration</h1>
        <p className="text-xs text-slate-400 mt-1">Configure subscription pricing tiers and resource limits per customer tenant.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {plans.map((p) => (
          <div key={p.id} className="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-base font-bold text-white">{p.name}</h3>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-950 text-slate-400">{p.slug}</span>
              </div>

              <div className="text-2xl font-extrabold text-white mb-4">
                ${p.price_monthly} <span className="text-xs text-slate-400 font-normal">/ mo</span>
              </div>

              <ul className="space-y-2 text-xs text-slate-300">
                <li className="flex items-center justify-between py-1 border-b border-slate-800/60">
                  <span className="text-slate-400">Channels Limit</span>
                  <strong className="text-white">{p.max_channels}</strong>
                </li>
                <li className="flex items-center justify-between py-1 border-b border-slate-800/60">
                  <span className="text-slate-400">Automations Limit</span>
                  <strong className="text-white">{p.max_automations}</strong>
                </li>
                <li className="flex items-center justify-between py-1 border-b border-slate-800/60">
                  <span className="text-slate-400">Messages Library</span>
                  <strong className="text-white">{p.max_messages}</strong>
                </li>
                <li className="flex items-center justify-between py-1">
                  <span className="text-slate-400">Daily Executions</span>
                  <strong className="text-white">{p.max_daily_executions}</strong>
                </li>
              </ul>
            </div>

            <div className="pt-4 mt-6 border-t border-slate-800 text-[11px] text-emerald-400 font-medium flex items-center">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-2"></span> Tier Active
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
