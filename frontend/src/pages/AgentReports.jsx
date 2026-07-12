import React, { useState, useEffect } from "react";
import Layout from "@/components/Layout";
import { API } from "@/context/AuthContext";
import axios from "axios";
import { FileBarChart2, Sparkles, Loader2, Download, ExternalLink, FileText, Presentation } from "lucide-react";
import { toast } from "sonner";

export default function AgentReports() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [deckGen, setDeckGen] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/reports`, { withCredentials: true });
      // Dedupe by title + minute
      const seen = new Set();
      const unique = (r.data.reports || []).filter((x) => {
        const key = `${x.title}|${(x.created_at || "").slice(0, 16)}`;
        if (seen.has(key)) return false;
        seen.add(key); return true;
      });
      setReports(unique);
    } catch (e) { toast.error(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const generate = async () => {
    if (!title.trim() || !prompt.trim() || generating) return;
    setGenerating(true);
    try {
      const r = await axios.post(`${API}/reports/generate`, { title, prompt, format: "pdf" }, { withCredentials: true, timeout: 180000 });
      toast.success("Report generated");
      setTitle(""); setPrompt("");
      await load();
      if (r.data.download_link) window.open(r.data.download_link, "_blank");
    } catch (e) { toast.error("Failed", { description: e.response?.data?.detail || e.message }); }
    finally { setGenerating(false); }
  };

  const generateDeck = async () => {
    if (deckGen) return;
    setDeckGen(true);
    try {
      const r = await axios.post(`${API}/reports/executive-deck`, {}, { withCredentials: true, timeout: 240000 });
      toast.success("Executive board deck ready!");
      await load();
      if (r.data.download_link) window.open(r.data.download_link, "_blank");
    } catch (e) { toast.error("Deck failed", { description: e.response?.data?.detail || e.message }); }
    finally { setDeckGen(false); }
  };

  const download = async (id) => {
    try {
      const r = await axios.get(`${API}/reports/${id}/download`, { withCredentials: true });
      if (r.data.url) window.open(r.data.url, "_blank");
      else if (r.data.content_b64) {
        const bytes = Uint8Array.from(atob(r.data.content_b64), (c) => c.charCodeAt(0));
        const blob = new Blob([bytes], { type: "application/pdf" });
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank");
      }
    } catch (e) { toast.error(e.message); }
  };

  return (
    <Layout>
      <div className="pt-8">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 grid place-items-center text-white shadow-lg">
              <FileBarChart2 className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Reports Agent</h1>
              <p className="mt-0.5 text-[13px] text-slate-500">Generate beautiful executive PDF reports from your Azure tenant. Reports auto-save to your Azure Blob storage under <span className="font-mono">infragenie-reports/</span>.</p>
            </div>
          </div>
          <button
            data-testid="rep-exec-deck"
            onClick={generateDeck}
            disabled={deckGen}
            className="h-11 px-5 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white text-[13px] font-semibold inline-flex items-center gap-2 shadow-[0_10px_28px_-8px_rgba(99,102,241,0.7)] disabled:opacity-60"
          >
            {deckGen ? <Loader2 className="h-4 w-4 animate-spin" /> : <Presentation className="h-4 w-4" />}
            {deckGen ? "Generating deck…" : "One-click Executive Board Deck"}
          </button>
        </div>

        <div className="mt-6 grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-1 bg-white rounded-2xl border border-slate-200/80 p-5">
            <h3 className="text-[13.5px] font-semibold text-slate-900 inline-flex items-center gap-2"><Sparkles className="h-4 w-4 text-indigo-500" /> New report</h3>
            <div className="mt-4 space-y-3">
              <div>
                <label className="text-[11.5px] text-slate-600 font-medium">Title</label>
                <input data-testid="rep-title" value={title} onChange={(e) => setTitle(e.target.value)}
                  placeholder="Monthly Azure Cost Report — Nov"
                  className="mt-1 w-full h-10 rounded-lg border border-slate-200 px-3 text-[13px] outline-none focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100" />
              </div>
              <div>
                <label className="text-[11.5px] text-slate-600 font-medium">What should the report cover?</label>
                <textarea data-testid="rep-prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={5}
                  placeholder="e.g. Executive summary of MTD cost, top spenders, security score, active alerts, and recommendations."
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-[13px] outline-none focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100" />
              </div>
              <button data-testid="rep-generate" onClick={generate} disabled={generating || !title.trim() || !prompt.trim()}
                className="w-full h-10 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[13px] font-semibold inline-flex items-center justify-center gap-2 disabled:opacity-60">
                {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                {generating ? "Generating…" : "Generate PDF"}
              </button>
            </div>
          </div>

          <div className="xl:col-span-2 bg-white rounded-2xl border border-slate-200/80 p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-[13.5px] font-semibold text-slate-900">History</h3>
              <button onClick={load} className="text-[11.5px] font-semibold text-indigo-600 hover:text-indigo-700">Refresh</button>
            </div>
            <div className="mt-3 divide-y divide-slate-100">
              {loading ? <div className="text-slate-400 text-[12px] py-6 inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
              : reports.length === 0 ? <div className="text-[12px] text-slate-400 py-6 italic">No reports yet. Click "One-click Executive Board Deck" above or use the form to make one.</div>
              : reports.map((r) => (
                <div key={r.id} data-testid={`rep-${r.id}`} className="py-3 flex items-center gap-3">
                  <div className="h-8 w-8 rounded-lg bg-indigo-50 grid place-items-center shrink-0"><FileText className="h-4 w-4 text-indigo-600" /></div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-semibold text-slate-900 truncate">{r.title}</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">
                      {new Date(r.created_at).toLocaleString()} • {Math.round((r.size_bytes || 0) / 1024)} KB
                      {r.kind === "executive_deck" && <span className="ml-2 px-1.5 py-0.5 rounded bg-violet-100 text-violet-700 text-[10px] font-mono">EXEC DECK</span>}
                    </div>
                  </div>
                  <div className="flex gap-1.5 shrink-0">
                    <button data-testid={`rep-download-${r.id}`} onClick={() => download(r.id)} className="h-8 px-3 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-[11.5px] font-semibold inline-flex items-center gap-1.5">
                      <Download className="h-3.5 w-3.5" /> Download
                    </button>
                    {r.download_link && (
                      <a href={r.download_link} target="_blank" rel="noreferrer" className="h-8 px-3 rounded-lg bg-white border border-slate-200 text-[11.5px] font-semibold inline-flex items-center gap-1.5">
                        <ExternalLink className="h-3.5 w-3.5" /> Open
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
