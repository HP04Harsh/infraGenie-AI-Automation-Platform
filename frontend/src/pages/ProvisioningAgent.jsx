import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "@/components/Layout";
import { Send, Sparkles, Server, Database, HardDrive, GitMerge, KeyRound, Boxes, Folder, ShieldCheck, History, Plus, ChevronRight, Loader2 } from "lucide-react";
import { useCatalog, useJobs, startSession } from "@/hooks/useProvisioning";

const iconMap = {
  server: Server, database: Database, "hard-drive": HardDrive, "git-merge": GitMerge,
  "key-round": KeyRound, boxes: Boxes, folder: Folder, "shield-check": ShieldCheck,
};

const accentBg = {
  indigo: "bg-indigo-50 text-indigo-600 ring-indigo-100",
  emerald: "bg-emerald-50 text-emerald-600 ring-emerald-100",
  amber: "bg-amber-50 text-amber-600 ring-amber-100",
  violet: "bg-violet-50 text-violet-600 ring-violet-100",
  rose: "bg-rose-50 text-rose-600 ring-rose-100",
  sky: "bg-sky-50 text-sky-600 ring-sky-100",
  slate: "bg-slate-50 text-slate-600 ring-slate-100",
};

const statusBadge = {
  awaiting_approval: "bg-amber-50 text-amber-700 border-amber-200",
  approved: "bg-indigo-50 text-indigo-700 border-indigo-200",
  deploying: "bg-sky-50 text-sky-700 border-sky-200",
  completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  failed: "bg-rose-50 text-rose-700 border-rose-200",
  rejected: "bg-slate-100 text-slate-600 border-slate-200",
  planning: "bg-sky-50 text-sky-700 border-sky-200",
};

const statusLabel = {
  awaiting_approval: "Awaiting approval",
  approved: "Approved",
  deploying: "Deploying",
  completed: "Completed",
  failed: "Failed",
  rejected: "Rejected",
  planning: "Planning",
};

function PromptHero({ onStart, starting }) {
  const [text, setText] = useState("");

  const examples = [
    { label: "Provision a Linux VM in East US", icon: Server },
    { label: "Create a SQL database", icon: Database },
    { label: "Add a storage account", icon: HardDrive },
    { label: "Set up a virtual network", icon: GitMerge },
  ];

  const submit = (e) => {
    e.preventDefault();
    if (!text.trim() || starting) return;
    onStart({ prompt: text.trim() });
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-[0_4px_30px_-18px_rgba(15,23,42,0.18)]">
      <form onSubmit={submit} className="flex items-stretch gap-3">
        <div className="flex-1 flex items-center gap-3 px-4 py-2.5 rounded-xl bg-slate-50/60 border border-slate-200/80 focus-within:bg-white focus-within:border-indigo-300 focus-within:ring-4 focus-within:ring-indigo-100/60 transition">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-[11px] font-semibold border border-emerald-200 shrink-0">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Provisioning Active
          </span>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Describe the resource you want to provision in plain English."
            className="flex-1 bg-transparent outline-none text-[14px] text-slate-800 placeholder:text-slate-400"
            data-testid="prov-prompt-input"
          />
        </div>
        <button
          type="submit"
          disabled={!text.trim() || starting}
          data-testid="prov-prompt-send"
          className="px-5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-[13.5px] font-semibold flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed transition shadow-[0_10px_24px_-12px_rgba(99,102,241,0.7)]"
        >
          {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Send
        </button>
      </form>
      <div className="mt-3 text-[12px] text-slate-400">
        <Sparkles className="h-3 w-3 inline mr-1 text-indigo-400" />
        e.g. Provision a Standard_D4s_v5 Linux VM in East US for the prod-app workload.
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {examples.map((s) => {
          const Icon = s.icon;
          return (
            <button
              key={s.label}
              onClick={() => onStart({ prompt: s.label })}
              disabled={starting}
              className="inline-flex items-center gap-1.5 h-8 px-3 rounded-full bg-slate-50 hover:bg-indigo-50 hover:text-indigo-700 text-[12px] font-medium text-slate-700 border border-slate-200/70 transition disabled:opacity-50"
            >
              <Icon className="h-3.5 w-3.5 text-indigo-500" />
              {s.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function CatalogCard({ item, onDeploy }) {
  const Icon = iconMap[item.icon] || Server;
  return (
    <div
      data-testid={`catalog-${item.key}`}
      className="relative bg-white rounded-2xl border border-slate-200/80 p-5 hover:-translate-y-0.5 hover:shadow-[0_24px_60px_-30px_rgba(15,23,42,0.18)] transition group"
    >
      {item.popular && (
        <span className="absolute top-3 right-3 inline-flex items-center px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 text-[10px] font-semibold border border-violet-200">Popular</span>
      )}
      <div className={`h-11 w-11 rounded-xl grid place-items-center ring-4 ${accentBg[item.accent] || accentBg.indigo}`}>
        <Icon className="h-5 w-5" strokeWidth={2.2} />
      </div>
      <div className="mt-4 text-[14px] font-semibold text-slate-900">{item.label}</div>
      <div className="mt-1 text-[12px] text-slate-500 leading-snug min-h-[34px]">{item.description}</div>
      <button
        onClick={() => onDeploy(item.key)}
        className="mt-3 inline-flex items-center gap-1 text-[12.5px] font-semibold text-indigo-600 hover:text-indigo-700"
      >
        Deploy <ChevronRight className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

function JobsTable({ items, onOpen }) {
  if (!items) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200/80 p-8 text-center text-[13px] text-slate-400">
        Loading jobs…
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200/80 p-10 text-center">
        <History className="h-8 w-8 mx-auto text-slate-300" />
        <p className="mt-3 text-[13px] font-medium text-slate-600">No provisioning jobs yet</p>
        <p className="text-[11.5px] text-slate-400 mt-0.5">Start a request above to see it appear here in real time.</p>
      </div>
    );
  }
  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 overflow-hidden">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="bg-slate-50/70 text-[10.5px] font-semibold tracking-[0.14em] uppercase text-slate-500">
            <th className="text-left px-5 py-3">Resource</th>
            <th className="text-left px-3 py-3">Type</th>
            <th className="text-left px-3 py-3">Region</th>
            <th className="text-left px-3 py-3">Requested By</th>
            <th className="text-left px-3 py-3">Time</th>
            <th className="text-left px-5 py-3">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {items.map((j) => (
            <tr
              key={j.id}
              data-testid={`job-row-${j.id}`}
              onClick={() => onOpen(j)}
              className="hover:bg-slate-50/50 cursor-pointer"
            >
              <td className="px-5 py-3 font-semibold text-slate-900">{j.resource_name || j.deployment_name || "—"}</td>
              <td className="px-3 py-3 text-slate-700">{j.module_label || j.module_key || "—"}</td>
              <td className="px-3 py-3 text-slate-600">{j.region || "—"}</td>
              <td className="px-3 py-3 text-slate-600">{j.requested_by}</td>
              <td className="px-3 py-3 text-slate-500 text-[12px]">{j.created_at ? new Date(j.created_at).toLocaleString() : "—"}</td>
              <td className="px-5 py-3">
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full border text-[11px] font-semibold ${statusBadge[j.status] || "bg-slate-50 text-slate-600 border-slate-200"}`}>
                  <span className="h-1.5 w-1.5 rounded-full mr-1 bg-current" />
                  {statusLabel[j.status] || j.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ProvisioningAgent() {
  const nav = useNavigate();
  const { data: catalog } = useCatalog();
  const { data: jobs } = useJobs();
  const [starting, setStarting] = useState(false);

  const handleStart = async ({ prompt, module_key }) => {
    setStarting(true);
    try {
      const session = await startSession({ prompt, module_key });
      nav(`/provisioning/session/${session.id}`);
    } catch (e) {
      console.error(e);
      setStarting(false);
    }
  };

  const openJob = (job) => nav(`/tickets/${job.id}`);

  return (
    <Layout>
      <div className="pt-6 space-y-8">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="h-12 w-12 rounded-xl bg-indigo-50 ring-4 ring-indigo-100 grid place-items-center text-indigo-600">
              <Boxes className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-[24px] font-semibold tracking-tight text-slate-900">Provisioning Agent</h1>
              <p className="text-[13px] text-slate-500 mt-0.5">Deploy and manage Azure resources using natural language or templates.</p>
            </div>
          </div>
          <div className="flex items-center gap-2.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 text-[12px] font-semibold border border-emerald-200">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Provisioning Active
            </span>
            <button
              onClick={() => nav("/tickets")}
              className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-full bg-white border border-slate-200/80 hover:border-slate-300 text-[12.5px] font-semibold text-slate-700 transition"
            >
              <History className="h-3.5 w-3.5" /> Job History
            </button>
            <button
              onClick={() => handleStart({})}
              className="inline-flex items-center gap-1.5 h-9 px-4 rounded-full bg-indigo-600 hover:bg-indigo-700 text-white text-[12.5px] font-semibold transition shadow-[0_10px_24px_-12px_rgba(99,102,241,0.7)]"
              data-testid="new-provision-request"
            >
              <Plus className="h-3.5 w-3.5" /> New Provision Request
            </button>
          </div>
        </div>

        {/* Prompt */}
        <PromptHero onStart={handleStart} starting={starting} />

        {/* Resource Catalog */}
        <section>
          <div className="flex items-center justify-between">
            <h2 className="text-[15px] font-semibold text-slate-900">Resource Catalog</h2>
            <a className="text-[12px] font-semibold text-indigo-600 hover:text-indigo-700">Browse all →</a>
          </div>
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {(catalog?.catalog || []).slice(0, 8).map((it) => (
              <CatalogCard key={it.key} item={it} onDeploy={(k) => handleStart({ module_key: k })} />
            ))}
          </div>
        </section>

        {/* Recent Provisioning Jobs */}
        <section>
          <div className="flex items-center justify-between">
            <h2 className="text-[15px] font-semibold text-slate-900">Recent Provisioning Jobs</h2>
            <button onClick={() => nav("/tickets")} className="text-[12px] font-semibold text-indigo-600 hover:text-indigo-700">View all jobs →</button>
          </div>
          <div className="mt-4">
            <JobsTable items={jobs?.items} onOpen={openJob} />
          </div>
        </section>
      </div>
    </Layout>
  );
}
