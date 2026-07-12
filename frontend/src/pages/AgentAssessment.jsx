import React, { useState, useEffect } from "react";
import Layout from "@/components/Layout";
import { API } from "@/context/AuthContext";
import axios from "axios";
import { ClipboardCheck, Play, Loader2, Download, FileText, Clock, CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";
import { stripMarkdown } from "@/lib/markdown";

export default function AgentAssessment() {
  const [catalog, setCatalog] = useState([]);
  const [results, setResults] = useState({});
  const [running, setRunning] = useState({});      // { key: {status,started_at,steps:[]} }
  const [timeline, setTimeline] = useState([]);    // global timeline

  useEffect(() => {
    axios.get(`${API}/assessments/catalog`, { withCredentials: true }).then((r) => setCatalog(r.data.assessments || []));
  }, []);

  const addStep = (msg, tone = "info") => {
    setTimeline((prev) => [...prev, { at: new Date().toISOString(), msg, tone }]);
  };

  const run = async (key, label) => {
    if (running[key]) return;
    setRunning((p) => ({ ...p, [key]: { status: "running", started: Date.now() } }));
    addStep(`Started ${label} assessment`, "info");
    try {
      addStep(`Fetching tenant data & running analysis…`, "info");
      const r = await axios.post(`${API}/assessments/${key}/run`, {}, { withCredentials: true, timeout: 180000 });
      // Extract score from reply text if present
      const scoreMatch = /(\d{1,3})\s*\/\s*100/.exec(r.data.result || "");
      const scoreNum = scoreMatch ? parseInt(scoreMatch[1]) : null;
      // Extract short summary (first paragraph after "Executive summary" or the first ~2 sentences)
      const text = (r.data.result || "").replace(/^#+\s.*\n/gm, "").trim();
      const firstPara = text.split(/\n{2,}/)[0].slice(0, 400);
      setResults((prev) => ({ ...prev, [key]: {
        score: scoreNum, summary: firstPara, full: r.data.result, tools: r.data.tools || [],
      }}));
      addStep(`✓ ${label} assessment complete${scoreNum != null ? ` — score ${scoreNum}/100` : ""}`, "success");
      setRunning((p) => ({ ...p, [key]: { status: "done" } }));
      toast.success(`${label} complete`);
    } catch (e) {
      addStep(`✗ ${label} failed: ${e.response?.data?.detail || e.message}`, "error");
      setRunning((p) => ({ ...p, [key]: { status: "error", error: e.message } }));
      toast.error("Assessment failed", { description: e.response?.data?.detail || e.message });
    }
  };

  const exportReport = async (key, label) => {
    const res = results[key];
    if (!res) return;
    try {
      const r = await axios.post(`${API}/reports/generate`, {
        title: `${label} Assessment Report`,
        prompt: `Generate a detailed ${label} assessment report on the user's Azure tenant. Include scoring, findings, and remediation actions. Pull live data.`,
        format: "pdf",
      }, { withCredentials: true, timeout: 180000 });
      if (r.data.download_link) window.open(r.data.download_link, "_blank");
      toast.success("PDF ready — saved to your Azure Blob storage");
    } catch (e) { toast.error("Export failed", { description: e.response?.data?.detail || e.message }); }
  };

  const exportCsv = (key, label) => {
    const res = results[key];
    if (!res) return;
    const rows = [
      ["Field", "Value"],
      ["Assessment", label],
      ["Score", res.score ?? "n/a"],
      ["Summary", (res.summary || "").replace(/"/g, '""').replace(/\n/g, " ")],
      ["Tools called", (res.tools || []).map((t) => t.tool).join(";")],
    ];
    const csv = rows.map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `${key}-assessment.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Layout>
      <div className="pt-8">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 grid place-items-center text-white shadow-lg">
            <ClipboardCheck className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Assessment Agent</h1>
            <p className="mt-0.5 text-[13px] text-slate-500">Run in-depth tenant assessments across 6 dimensions. Live timeline as they execute. Download as PDF (saved to your Azure Blob) or CSV.</p>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 xl:grid-cols-4 gap-6">
          <div className="xl:col-span-3 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {catalog.map((a) => {
              const state = running[a.key];
              const res = results[a.key];
              const isRunning = state?.status === "running";
              return (
                <div key={a.key} data-testid={`asmt-${a.key}`} className="bg-white rounded-2xl border border-slate-200/80 p-5">
                  <div className="flex items-start justify-between gap-2">
                    <div className="text-[15px] font-semibold text-slate-900">{a.label}</div>
                    {res?.score != null && (
                      <div className={`text-[13px] font-bold px-2 py-0.5 rounded-lg ${res.score >= 80 ? "bg-emerald-50 text-emerald-700" : res.score >= 60 ? "bg-amber-50 text-amber-700" : "bg-rose-50 text-rose-700"}`}>
                        {res.score}/100
                      </div>
                    )}
                  </div>
                  <div className="mt-1 text-[12px] text-slate-500 line-clamp-2">{a.desc}</div>

                  {res && (
                    <div className="mt-3 p-3 rounded-lg bg-slate-50 border border-slate-100 text-[12px] text-slate-700 max-h-[120px] overflow-y-auto">
                      {stripMarkdown(res.summary)}
                    </div>
                  )}

                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      data-testid={`asmt-${a.key}-run`}
                      onClick={() => run(a.key, a.label)}
                      disabled={isRunning}
                      className="h-9 px-3.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[12.5px] font-semibold inline-flex items-center gap-1.5 disabled:opacity-60"
                    >
                      {isRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                      {isRunning ? "Running…" : (res ? "Re-run" : "Run assessment")}
                    </button>
                    {res && (
                      <>
                        <button data-testid={`asmt-${a.key}-pdf`} onClick={() => exportReport(a.key, a.label)} className="h-9 px-3 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-[12px] font-semibold inline-flex items-center gap-1.5">
                          <FileText className="h-3.5 w-3.5" /> PDF
                        </button>
                        <button data-testid={`asmt-${a.key}-csv`} onClick={() => exportCsv(a.key, a.label)} className="h-9 px-3 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-[12px] font-semibold inline-flex items-center gap-1.5">
                          <Download className="h-3.5 w-3.5" /> CSV
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Live timeline */}
          <div className="xl:col-span-1">
            <div className="bg-white rounded-2xl border border-slate-200/80 p-5 sticky top-4">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-indigo-500" />
                <h3 className="text-[13.5px] font-semibold text-slate-900">Live timeline</h3>
              </div>
              <div className="mt-3 max-h-[520px] overflow-y-auto space-y-2">
                {timeline.length === 0 ? (
                  <div className="text-[12px] text-slate-400 italic">No activity yet. Click a "Run assessment" button.</div>
                ) : timeline.slice().reverse().map((t, i) => {
                  const Icon = t.tone === "success" ? CheckCircle2 : t.tone === "error" ? XCircle : Clock;
                  const color = t.tone === "success" ? "text-emerald-600" : t.tone === "error" ? "text-rose-600" : "text-indigo-500";
                  return (
                    <div key={i} className="flex gap-2 text-[12px]">
                      <Icon className={`h-3.5 w-3.5 mt-0.5 shrink-0 ${color}`} />
                      <div className="flex-1">
                        <div className="text-slate-700">{t.msg}</div>
                        <div className="text-[10px] text-slate-400 mt-0.5">{new Date(t.at).toLocaleTimeString()}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
