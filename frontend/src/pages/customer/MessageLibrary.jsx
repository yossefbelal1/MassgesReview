import React, { useState, useEffect } from 'react';
import apiClient from '../../api/client';
import { Layers, Sparkles, CheckCircle2, ShieldCheck } from 'lucide-react';

export default function MessageLibrary() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('ALL');

  useEffect(() => {
    fetchMessages();
  }, [categoryFilter]);

  const fetchMessages = async () => {
    try {
      setLoading(true);
      const url = categoryFilter === 'ALL' ? '/messages/' : `/messages/?category=${categoryFilter}`;
      const res = await apiClient.get(url);
      setMessages(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const categories = ['ALL', 'Results', 'Social Proof', 'Reviews', 'VIP Feedback', 'General'];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Central Real Reviews Bank</h1>
          <p className="text-xs text-slate-400 mt-1">
            Real authentic member reviews pre-configured and managed centrally by ReviewFlow.
          </p>
        </div>
        <div className="px-3.5 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold flex items-center space-x-1.5 self-start sm:self-auto">
          <ShieldCheck className="w-4 h-4" />
          <span>Central Bank Active (-1003969850866)</span>
        </div>
      </div>

      {/* Info Banner */}
      <div className="bg-emerald-950/20 border border-emerald-500/20 rounded-2xl p-4 flex items-center space-x-3 text-xs text-slate-300">
        <Sparkles className="w-5 h-5 text-emerald-400 flex-shrink-0" />
        <p>
          <strong className="text-white">Plug & Play Protection:</strong> All reviews are verified authentic forwards from real traders (e.g. Hossam_Vip, Eng. Hazem, المعلم بيومي, etc.). Whenever your TP trigger fires, the system automatically rotates and forwards these real reviews to your channel.
        </p>
      </div>

      {/* Category Pills */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-1">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategoryFilter(cat)}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-medium transition-all ${
              categoryFilter === cat
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="p-12 text-center text-slate-400">Loading messages...</div>
      ) : messages.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center">
          <Layers className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-bold text-white mb-1">Message Library is empty</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto mb-6">
            Add real messages from your source bank so you can easily include them in your automated trade sequence workflows.
          </p>
          <button
            onClick={() => setModalOpen(true)}
            className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-all inline-flex items-center space-x-2"
          >
            <Plus className="w-4 h-4" />
            <span>Add First Message</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {messages.map((m) => (
            <div key={m.id} className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 transition-all shadow-md flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between mb-3">
                  <span className="text-[11px] font-semibold px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                    {m.category}
                  </span>
                  <span className="text-[10px] text-emerald-400 font-semibold px-2 py-0.5 rounded-full bg-emerald-950/60 border border-emerald-500/30 flex items-center space-x-1">
                    <CheckCircle2 className="w-3 h-3 inline" />
                    <span>Verified Real</span>
                  </span>
                </div>
                
                <h3 className="text-sm font-bold text-white mb-2">{m.title}</h3>
                
                {m.text_preview && (
                  <p className="text-xs text-slate-300 line-clamp-3 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 mb-3">
                    "{m.text_preview}"
                  </p>
                )}
              </div>

              <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                <span>Central Bank Forward</span>
                <span className="text-emerald-400 font-semibold">Ref #{m.source_message_id}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
