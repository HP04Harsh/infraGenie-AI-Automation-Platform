import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import Layout from "@/components/Layout";
import { Sparkles, ArrowLeft, Construction } from "lucide-react";

const labels = {
  provisioning: "Provisioning Agent",
  assessment: "Assessment Agent",
  migration: "Migration Agent",
  observability: "Observability Agent",
  optimization: "Optimization Agent",
  troubleshoot: "Troubleshoot Agent",
  itsm: "ITSM Agent",
  policy: "Policy & Compliance Agent",
};

export default function AgentPlaceholder() {
  const { agentKey } = useParams();
  const nav = useNavigate();
  const label = labels[agentKey] || "Agent";

  return (
    <Layout>
      <div data-testid={`agent-page-${agentKey}`} className="pt-10 max-w-3xl mx-auto text-center">
        <div className="mx-auto h-14 w-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-500 grid place-items-center shadow-[0_18px_40px_-16px_rgba(99,102,241,0.6)]">
          <Sparkles className="h-7 w-7 text-white" />
        </div>
        <h1 className="mt-5 text-[28px] font-semibold tracking-tight text-slate-900">{label}</h1>
        <p className="mt-2 text-[13.5px] text-slate-500">
          This agent will live here. We'll wire its UI next.
        </p>
        <div className="mt-6 inline-flex items-center gap-2 text-[12px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-3 py-1.5 rounded-full">
          <Construction className="h-3.5 w-3.5" /> Coming soon
        </div>
        <div className="mt-8">
          <button
            data-testid="agent-back-dashboard"
            onClick={() => nav("/dashboard")}
            className="h-10 px-4 rounded-xl border border-slate-200 text-[13px] font-semibold text-slate-700 hover:border-slate-300 hover:text-slate-900 inline-flex items-center gap-2"
          >
            <ArrowLeft className="h-4 w-4" /> Back to dashboard
          </button>
        </div>
      </div>
    </Layout>
  );
}
