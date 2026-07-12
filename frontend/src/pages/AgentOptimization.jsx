import React, { useState } from "react";
import Layout from "@/components/Layout";
import AskTenantAgent from "@/components/AskTenantAgent";
import { useTenantSummary } from "@/hooks/useTenantSummary";
import { RefreshCw, TrendingDown, Coins, Zap, PiggyBank, Loader2 } from "lucide-react";

export default function AgentOptimization() {
  const { data, loading, refresh } = useTenantSummary();
  const [refreshing, setRefreshing] = useState(false);
  const onRefresh = async () => { setRefreshing(true); await refresh(); setRefreshing(false); };

  const money = (v, c) => new Intl.NumberFormat(undefined, { style: "currency", currency: (c || "INR").toUpperCase(), minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v || 0);

  return (
    <Layout>
      <div className="pt-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Optimization Agent</h1>
            <p className="mt-1 text-[13px] text-slate-500">Real-time cost intelligence, rightsizing, and savings recommendations from your Azure tenant.</p>
          </div>
          <button data-testid="opt-refresh" onClick={onRefresh} className="h-9 px-3.5 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-[12.5px] font-semibold inline-flex items-center gap-1.5">
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>

        {/* KPI cards */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard icon={Coins} label="MTD Spend" value={loading ? "…" : money(data?.monthly_cost, data?.currency)} accent="amber" testid="opt-kpi-mtd" />
          <KpiCard icon={TrendingDown} label="Resources" value={loading ? "…" : (data?.resources ?? 0)} accent="indigo" testid="opt-kpi-resources" />
          <KpiCard icon={Zap} label="VMs Running" value={loading ? "…" : (data?.vms ?? 0)} accent="violet" testid="opt-kpi-vms" />
          <KpiCard icon={PiggyBank} label="Resource Groups" value={loading ? "…" : (data?.resource_groups ?? 0)} accent="emerald" testid="opt-kpi-rgs" />
        </div>

        <div className="mt-6 grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-1 space-y-4">
            <div className="bg-white rounded-2xl border border-slate-200/80 p-5">
              <h3 className="text-[13.5px] font-semibold text-slate-900">Resource type mix</h3>
              <p className="text-[11px] text-slate-500 mt-0.5">Breakdown from live tenant scan</p>
              <ul className="mt-3 space-y-1.5">
                {loading ? <div className="flex items-center gap-2 text-slate-400 text-[12px]"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading…</div>
                : Object.entries(data?.type_breakdown || {}).map(([k, v]) => (
                  <li key={k} className="flex justify-between text-[12px]">
                    <span className="text-slate-600 font-mono">{k}</span>
                    <span className="font-semibold text-slate-800">{v}</span>
                  </li>
                ))}
                {!loading && Object.keys(data?.type_breakdown || {}).length === 0 && (
                  <li className="text-[12px] text-slate-400 italic">No resources found in tenant.</li>
                )}
              </ul>
            </div>
            <div className="bg-white rounded-2xl border border-slate-200/80 p-5">
              <h3 className="text-[13.5px] font-semibold text-slate-900">Locations</h3>
              <ul className="mt-3 space-y-1.5">
                {loading ? null : Object.entries(data?.location_breakdown || {}).map(([k, v]) => (
                  <li key={k} className="flex justify-between text-[12px]">
                    <span className="text-slate-600">{k}</span>
                    <span className="font-semibold text-slate-800">{v}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div className="xl:col-span-2">
            <AskTenantAgent
              title="Ask the Cost Agent"
              placeholder="e.g. Top 10 most expensive resources this month"
              hint="You are the Cost Agent. Focus on cost optimisation, rightsizing, and FinOps advice. Always pull real data via tools."
              suggestedPrompts={[
                "Top 10 most expensive resources with cost",
                "What is my MTD spend?",
                "Any idle VMs I can shut down?",
                "Recommend cost savings for my subscription",
                "Get all Advisor cost recommendations",
              ]}
              testIdPrefix="opt-ask"
            />
          </div>
        </div>
      </div>
    </Layout>
  );
}

function KpiCard({ icon: Icon, label, value, accent, testid }) {
  const tones = {
    indigo: "from-indigo-500/10 to-indigo-500/0 text-indigo-600",
    amber: "from-amber-500/10 to-amber-500/0 text-amber-600",
    violet: "from-violet-500/10 to-violet-500/0 text-violet-600",
    emerald: "from-emerald-500/10 to-emerald-500/0 text-emerald-600",
    rose: "from-rose-500/10 to-rose-500/0 text-rose-600",
  };
  return (
    <div data-testid={testid} className={`bg-gradient-to-br ${tones[accent] || tones.indigo} bg-white rounded-2xl border border-slate-200/80 p-4`}>
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] font-semibold">
        <Icon className="h-3.5 w-3.5" /> {label}
      </div>
      <div className="mt-2 text-[26px] font-semibold tracking-tight text-slate-900">{value}</div>
    </div>
  );
}
