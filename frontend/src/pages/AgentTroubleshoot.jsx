import React, { useState } from "react";
import Layout from "@/components/Layout";
import AskTenantAgent from "@/components/AskTenantAgent";
import { useTenantSummary } from "@/hooks/useTenantSummary";
import { RefreshCw, Wrench, AlertTriangle, Activity, ShieldAlert } from "lucide-react";

export default function AgentTroubleshoot() {
  const { data, loading, refresh } = useTenantSummary();
  const [refreshing, setRefreshing] = useState(false);
  const onRefresh = async () => { setRefreshing(true); await refresh(); setRefreshing(false); };

  return (
    <Layout>
      <div className="pt-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Troubleshoot Agent</h1>
            <p className="mt-1 text-[13px] text-slate-500">Live incident triage and remediation runbooks — grounded in your tenant&apos;s actual resources and alerts.</p>
          </div>
          <button data-testid="ts-refresh" onClick={onRefresh} className="h-9 px-3.5 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-[12.5px] font-semibold inline-flex items-center gap-1.5">
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>

        <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
          <Kpi icon={ShieldAlert} label="Secure Score" value={loading ? "…" : `${data?.secure_score ?? 0}/100`} tone={((data?.secure_score) || 0) >= 60 ? "emerald" : "amber"} testid="ts-kpi-secure" />
          <Kpi icon={Activity} label="Resources" value={loading ? "…" : (data?.resources ?? 0)} tone="indigo" testid="ts-kpi-resources" />
          <Kpi icon={AlertTriangle} label="VMs" value={loading ? "…" : (data?.vms ?? 0)} tone="violet" testid="ts-kpi-vms" />
          <Kpi icon={Wrench} label="Resource Groups" value={loading ? "…" : (data?.resource_groups ?? 0)} tone="rose" testid="ts-kpi-rgs" />
        </div>

        <div className="mt-6 grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-1 bg-white rounded-2xl border border-slate-200/80 p-5">
            <h3 className="text-[13.5px] font-semibold text-slate-900">Live tenant snapshot</h3>
            <div className="mt-3 space-y-2 text-[12px]">
              <div className="flex justify-between"><span className="text-slate-500">Resource Groups</span><span className="font-semibold text-slate-800">{data?.resource_groups ?? "—"}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Resources</span><span className="font-semibold text-slate-800">{data?.resources ?? "—"}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Virtual Machines</span><span className="font-semibold text-slate-800">{data?.vms ?? "—"}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Secure Score</span><span className="font-semibold text-slate-800">{data?.secure_score ?? "—"}/100</span></div>
            </div>
          </div>
          <div className="xl:col-span-2">
            <AskTenantAgent
              title="Ask the Troubleshoot Agent"
              placeholder="e.g. Why is my storage account slow? Show active alerts"
              hint="You are the Troubleshoot Agent. Diagnose issues in the user's tenant using tools (list_alerts, list_resources, get_secure_score, get_advisor_recommendations). Give clear step-by-step fixes."
              suggestedPrompts={[
                "Show my active alert rules",
                "What's my secure score and top security issues?",
                "Diagnose issues in my subscription",
                "Give me troubleshooting steps for underperforming resources",
              ]}
              testIdPrefix="ts-ask"
            />
          </div>
        </div>
      </div>
    </Layout>
  );
}

function Kpi({ icon: Icon, label, value, tone, testid }) {
  return (
    <div data-testid={testid} className="bg-white rounded-2xl border border-slate-200/80 p-4">
      <div className={`flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] font-semibold text-${tone}-600`}>
        <Icon className="h-3.5 w-3.5" /> {label}
      </div>
      <div className="mt-2 text-[26px] font-semibold tracking-tight text-slate-900">{value}</div>
    </div>
  );
}
