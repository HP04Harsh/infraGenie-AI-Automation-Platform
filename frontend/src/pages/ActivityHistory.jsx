import React from "react";
import Layout from "@/components/Layout";
import { useActivity } from "@/hooks/useTenantData";
import { Server, TrendingDown, AlertTriangle, Ticket, ShieldCheck, GitMerge, Loader2 } from "lucide-react";

const iconMap = {
  server: Server, "trending-down": TrendingDown, "alert-triangle": AlertTriangle,
  ticket: Ticket, "shield-check": ShieldCheck, "git-merge": GitMerge,
};
const accentBg = {
  indigo: "bg-indigo-50 text-indigo-600", emerald: "bg-emerald-50 text-emerald-600",
  amber: "bg-amber-50 text-amber-600", violet: "bg-violet-50 text-violet-600",
  rose: "bg-rose-50 text-rose-600",
};
const statusStyle = {
  success: "bg-emerald-50 text-emerald-600 border-emerald-100",
  warning: "bg-amber-50 text-amber-600 border-amber-100",
  info: "bg-sky-50 text-sky-600 border-sky-100",
  danger: "bg-rose-50 text-rose-600 border-rose-100",
  neutral: "bg-slate-50 text-slate-600 border-slate-200",
};

export default function ActivityHistory() {
  const { data } = useActivity(50);

  return (
    <Layout>
      <div data-testid="activity-page" className="pt-8 max-w-4xl">
        <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Activity history</h1>
        <p className="mt-1 text-[13px] text-slate-500">Everything happening across your tenant.</p>

        <div className="mt-6 bg-white rounded-2xl border border-slate-200/80 p-5">
          {!data ? (
            <div className="flex items-center gap-2 text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.items.map((a) => {
                const Icon = iconMap[a.icon] ?? Server;
                return (
                  <li key={a.id} className="flex items-start gap-3 py-4">
                    <div className={`h-10 w-10 rounded-xl grid place-items-center shrink-0 ${accentBg[a.accent] ?? accentBg.indigo}`}>
                      <Icon className="h-[18px] w-[18px]" strokeWidth={2.2} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-3">
                        <div className="text-[13.5px] font-semibold text-slate-900">{a.title}</div>
                        <span className={`shrink-0 text-[10.5px] font-semibold px-2 py-0.5 rounded-full border ${statusStyle[a.status_tone] ?? statusStyle.neutral}`}>
                          {a.status}
                        </span>
                      </div>
                      <div className="text-[12px] text-slate-500 mt-0.5">{a.detail}</div>
                      <div className="text-[11px] text-slate-400 mt-1.5">{a.time_ago} • by {a.actor}</div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </Layout>
  );
}
