import React, { useState, useEffect } from "react";
import axios from "axios";
import Layout from "@/components/Layout";
import AskTenantAgent from "@/components/AskTenantAgent";
import { API } from "@/context/AuthContext";
import { RefreshCw, ShieldCheck, FileCheck2, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function AgentPolicy() {
  const [compliance, setCompliance] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.post(`${API}/tenant/chat`, {
        messages: [{ role: "user", content: "Call get_compliance_scores tool and return the raw result." }],
        hint: "You are the Compliance Agent. Always call get_compliance_scores to get framework scores.",
      }, { withCredentials: true, timeout: 60000 });
      // Extract JSON from reply
      const m = /\{[\s\S]*\}/.exec(r.data.reply || "");
      if (m) {
        try { setCompliance(JSON.parse(m[0])); }
        catch { setCompliance({ raw: r.data.reply }); }
      } else {
        setCompliance({ raw: r.data.reply });
      }
    } catch (e) {
      setCompliance({ error: e.response?.data?.detail || e.message });
      toast.error("Failed to load compliance", { description: e.message });
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const scoreColor = (s) => s >= 80 ? "text-emerald-600" : s >= 60 ? "text-amber-600" : "text-rose-600";

  return (
    <Layout>
      <div className="pt-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Policy &amp; Compliance Agent</h1>
            <p className="mt-1 text-[13px] text-slate-500">Live policy assignments and per-framework compliance scores (GDPR, HIPAA, ISO 27001, SOC 2, PCI DSS).</p>
          </div>
          <button data-testid="pc-refresh" onClick={load} className="h-9 px-3.5 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-[12.5px] font-semibold inline-flex items-center gap-1.5">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>

        {/* Framework gauges */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
          {loading ? (
            [1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="bg-white rounded-2xl border border-slate-200/80 p-5">
                <div className="h-3 w-20 bg-slate-100 rounded animate-pulse" />
                <div className="h-8 w-16 bg-slate-100 rounded mt-3 animate-pulse" />
              </div>
            ))
          ) : ((compliance?.frameworks) || [
            { name: "GDPR", score: 0 }, { name: "HIPAA", score: 0 }, { name: "ISO 27001", score: 0 }, { name: "SOC 2", score: 0 }, { name: "PCI DSS", score: 0 }
          ]).map((f) => (
            <div key={f.name} data-testid={`gauge-${f.name.toLowerCase().replace(/\s/g,'')}`} className="bg-white rounded-2xl border border-slate-200/80 p-5">
              <div className="text-[11px] uppercase tracking-[0.14em] font-semibold text-slate-500">{f.name}</div>
              <div className={`mt-2 text-[28px] font-bold ${scoreColor(f.score || 0)}`}>{f.score ?? 0}<span className="text-[14px] text-slate-400 font-medium">/100</span></div>
              <div className="mt-2 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                <div className={`h-full rounded-full ${f.score >= 80 ? "bg-emerald-500" : f.score >= 60 ? "bg-amber-500" : "bg-rose-500"}`} style={{ width: `${Math.min(100, f.score || 0)}%` }} />
              </div>
              {f.matches != null && <div className="mt-1.5 text-[10.5px] text-slate-500">{f.matches} policy state matches</div>}
            </div>
          ))}
        </div>

        {compliance?.overall_score != null && (
          <div className="mt-4 bg-white rounded-2xl border border-slate-200/80 p-5">
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-6 w-6 text-indigo-500" />
              <div>
                <div className="text-[12px] uppercase tracking-[0.14em] font-semibold text-slate-500">Overall compliance</div>
                <div className={`text-[26px] font-bold ${scoreColor(compliance.overall_score)}`}>
                  {compliance.overall_score}/100
                  <span className="ml-2 text-[13px] font-normal text-slate-500">({compliance.compliant_states || 0} / {compliance.total_states || 0} states compliant)</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="mt-6 grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-1 bg-white rounded-2xl border border-slate-200/80 p-5">
            <div className="flex items-center gap-2">
              <FileCheck2 className="h-4 w-4 text-emerald-500" />
              <h3 className="text-[13.5px] font-semibold text-slate-900">What we scan</h3>
            </div>
            <ul className="mt-3 space-y-1.5 text-[12px] text-slate-600">
              <li>• Azure Policy compliance states</li>
              <li>• Regulatory framework matches (GDPR, HIPAA, ISO 27001, SOC 2, PCI DSS)</li>
              <li>• Defender for Cloud secure score</li>
              <li>• Remediation via Azure Policy remediation tasks (with approval)</li>
            </ul>
          </div>
          <div className="xl:col-span-2">
            <AskTenantAgent
              title="Ask the Compliance Agent"
              placeholder="e.g. Which resources are non-compliant with GDPR?"
              hint="You are the Compliance Agent. Use list_policy_assignments, get_compliance_scores, and other tools. Advise on remediation and rollback."
              suggestedPrompts={[
                "Give me current GDPR compliance status",
                "List all policy assignments",
                "Which resources are non-compliant?",
                "Suggest policies to enforce tagging",
              ]}
              testIdPrefix="pc-ask"
            />
          </div>
        </div>
      </div>
    </Layout>
  );
}
