import React, { useState } from "react";
import Layout from "@/components/Layout";
import AskTenantAgent from "@/components/AskTenantAgent";
import { useTenantSummary } from "@/hooks/useTenantSummary";
import { RefreshCw, Activity, Server, Cloud, PieChart as PieIcon, Download, FileText } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";
import axios from "axios";
import { API } from "@/context/AuthContext";
import { toast } from "sonner";

const COLORS = ["#6366F1", "#8B5CF6", "#EC4899", "#F59E0B", "#10B981", "#3B82F6", "#EF4444", "#14B8A6"];

export default function AgentObservability() {
  const { data, loading, refresh } = useTenantSummary();
  const [refreshing, setRefreshing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const onRefresh = async () => { setRefreshing(true); await refresh(); setRefreshing(false); };

  const money = (v, c) => new Intl.NumberFormat(undefined, { style: "currency", currency: (c || "INR").toUpperCase(), minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v || 0);

  const typePie = Object.entries(data?.type_breakdown || {}).map(([name, value]) => ({ name, value }));
  const locBar = Object.entries(data?.location_breakdown || {}).map(([name, count]) => ({ name, count }));
  const rgBar = (data?.resource_groups_list || []).slice(0, 8).map((rg) => ({ name: rg.name, region: rg.location, val: 1 }));

  const exportPdf = async () => {
    setExporting(true);
    try {
      const r = await axios.post(`${API}/reports/generate`, {
        title: `Observability Snapshot — ${new Date().toISOString().slice(0, 10)}`,
        prompt: "Generate a full observability report: total RGs, resources, VMs, MTD cost, secure score, breakdown by type and location, top-10 resources by cost, active alerts. Include recommendations.",
        format: "pdf",
      }, { withCredentials: true });
      toast.success("Report generated");
      if (r.data.download_link) window.open(r.data.download_link, "_blank");
    } catch (e) {
      toast.error("Export failed", { description: e.response?.data?.detail || e.message });
    } finally { setExporting(false); }
  };

  const exportCsv = () => {
    const rows = [["Metric", "Value"],
      ["Resource Groups", data?.resource_groups ?? 0],
      ["Resources", data?.resources ?? 0],
      ["VMs", data?.vms ?? 0],
      ["MTD Cost", data?.monthly_cost ?? 0],
      ["Currency", data?.currency ?? "INR"],
      ["Secure Score", data?.secure_score ?? 0],
    ];
    const csv = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `observability-${Date.now()}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Layout>
      <div className="pt-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Observability Agent</h1>
            <p className="mt-1 text-[13px] text-slate-500">Live tenant dashboard — resources, cost, security, distribution — with refresh & export.</p>
          </div>
          <div className="flex gap-2">
            <button data-testid="obs-refresh" onClick={onRefresh} className="h-9 px-3.5 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-[12.5px] font-semibold inline-flex items-center gap-1.5">
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} /> Refresh
            </button>
            <button data-testid="obs-export-csv" onClick={exportCsv} className="h-9 px-3.5 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-[12.5px] font-semibold inline-flex items-center gap-1.5">
              <Download className="h-3.5 w-3.5" /> CSV
            </button>
            <button data-testid="obs-export-pdf" onClick={exportPdf} disabled={exporting} className="h-9 px-3.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[12.5px] font-semibold inline-flex items-center gap-1.5 disabled:opacity-60">
              <FileText className="h-3.5 w-3.5" /> {exporting ? "Generating…" : "PDF"}
            </button>
          </div>
        </div>

        {/* KPIs */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
          <ObsKpi icon={Cloud} label="Resource Groups" value={loading ? "…" : (data?.resource_groups ?? 0)} tone="indigo" testid="obs-kpi-rg" />
          <ObsKpi icon={Server} label="Resources" value={loading ? "…" : (data?.resources ?? 0)} tone="violet" testid="obs-kpi-res" />
          <ObsKpi icon={Activity} label="MTD Cost" value={loading ? "…" : money(data?.monthly_cost, data?.currency)} tone="amber" testid="obs-kpi-cost" />
          <ObsKpi icon={PieIcon} label="Secure Score" value={loading ? "…" : `${data?.secure_score ?? 0}/100`} tone={((data?.secure_score) || 0) >= 60 ? "emerald" : "rose"} testid="obs-kpi-score" />
        </div>

        {/* Charts */}
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl border border-slate-200/80 p-5">
            <h3 className="text-[13.5px] font-semibold text-slate-900">Resource type distribution</h3>
            <div className="mt-3 h-[240px]">
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={typePie} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                    {typePie.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200/80 p-5">
            <h3 className="text-[13.5px] font-semibold text-slate-900">Resources by location</h3>
            <div className="mt-3 h-[240px]">
              <ResponsiveContainer>
                <BarChart data={locBar}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#6366F1" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Summary table + agent chat */}
        <div className="mt-6 grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-1 bg-white rounded-2xl border border-slate-200/80 p-5">
            <h3 className="text-[13.5px] font-semibold text-slate-900">Resource groups</h3>
            <div className="mt-3 max-h-[340px] overflow-y-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-100 text-left">
                    <th className="py-2">Name</th><th className="py-2">Region</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.resource_groups_list || []).map((rg) => (
                    <tr key={rg.id} className="border-b border-slate-50">
                      <td className="py-2 text-slate-800 font-medium">{rg.name}</td>
                      <td className="py-2 text-slate-600">{rg.location}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="xl:col-span-2">
            <AskTenantAgent
              title="Ask the Observability Agent"
              placeholder="e.g. Show metrics for storage account strginfragenieindia"
              hint="You are the Observability Agent. Report metrics, health, and resource details. Use list_resources, list_vms, get_costs tools."
              suggestedPrompts={[
                "Give me a health summary of my tenant",
                "List my VMs with size and location",
                "Show storage accounts and their tier",
                "What resources are in resource group infragenie?",
              ]}
              testIdPrefix="obs-ask"
            />
          </div>
        </div>
      </div>
    </Layout>
  );
}

function ObsKpi({ icon: Icon, label, value, tone, testid }) {
  return (
    <div data-testid={testid} className="bg-white rounded-2xl border border-slate-200/80 p-4">
      <div className={`flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] font-semibold text-${tone}-600`}>
        <Icon className="h-3.5 w-3.5" /> {label}
      </div>
      <div className="mt-2 text-[26px] font-semibold tracking-tight text-slate-900">{value}</div>
    </div>
  );
}
