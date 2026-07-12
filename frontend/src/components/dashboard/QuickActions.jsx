import React from "react";
import { useNavigate } from "react-router-dom";
import { Server, ShieldCheck, TrendingDown, Ticket, BarChart3, ArrowRight } from "lucide-react";

const actions = [
  { key: "provision", title: "Provision Resource", desc: "Deploy VMs, storage, databases, and networking components.", icon: Server, color: "indigo", agent: "provisioning" },
  { key: "compliance", title: "Check Compliance", desc: "Run policy scans and review compliance posture.", icon: ShieldCheck, color: "emerald", agent: "policy" },
  { key: "optimize", title: "Optimize Costs", desc: "Identify savings and rightsizing recommendations.", icon: TrendingDown, color: "amber", agent: "optimization" },
  { key: "itsm", title: "Open ITSM Ticket", desc: "Create and track incident or change requests.", icon: Ticket, color: "violet", agent: "itsm" },
  { key: "dashboards", title: "View Dashboards", desc: "Explore observability and resource health dashboards.", icon: BarChart3, color: "rose", agent: "observability" },
];

const palette = {
  indigo: { bg: "bg-indigo-50", fg: "text-indigo-600", cta: "text-indigo-600 hover:text-indigo-700", glow: "from-indigo-200/40" },
  emerald: { bg: "bg-emerald-50", fg: "text-emerald-600", cta: "text-emerald-600 hover:text-emerald-700", glow: "from-emerald-200/40" },
  amber: { bg: "bg-amber-50", fg: "text-amber-600", cta: "text-amber-600 hover:text-amber-700", glow: "from-amber-200/40" },
  violet: { bg: "bg-violet-50", fg: "text-violet-600", cta: "text-violet-600 hover:text-violet-700", glow: "from-violet-200/40" },
  rose: { bg: "bg-rose-50", fg: "text-rose-600", cta: "text-rose-600 hover:text-rose-700", glow: "from-rose-200/40" },
};

export default function QuickActions() {
  const nav = useNavigate();
  return (
    <div data-testid="quick-actions-grid" className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {actions.map((a, i) => {
        const Icon = a.icon;
        const c = palette[a.color];
        return (
          <button
            key={a.key}
            data-testid={`action-${a.key}`}
            onClick={() => nav(`/agents/${a.agent}`)}
            className="group relative text-left bg-white rounded-2xl border border-slate-200/80 p-5 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-[0_24px_60px_-30px_rgba(15,23,42,0.22)] transition-all overflow-hidden"
            style={{ animation: `qa-fade 600ms ${i * 60}ms both` }}
          >
            <div className={`absolute -top-12 -right-12 h-32 w-32 rounded-full bg-gradient-to-br ${c.glow} to-transparent blur-2xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none`} />
            <div className="relative">
              <div className={`h-11 w-11 rounded-xl grid place-items-center ${c.bg} ${c.fg}`}>
                <Icon className="h-5 w-5" strokeWidth={2.2} />
              </div>
              <h3 className="mt-4 text-[15px] font-semibold tracking-tight text-slate-900">{a.title}</h3>
              <p className="mt-1.5 text-[12.5px] text-slate-500 leading-relaxed">{a.desc}</p>
              <div className={`mt-5 inline-flex items-center gap-1 text-[12.5px] font-semibold ${c.cta} transition`}>
                Get started
                <ArrowRight className="h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform" />
              </div>
            </div>
          </button>
        );
      })}
      <style>{`
        @keyframes qa-fade {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
