import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { mutate as globalMutate } from "swr";
import {
  Server, TrendingDown, AlertTriangle, Ticket, ShieldCheck, GitMerge,
  ChevronRight, Activity, LogIn, UserPlus, LogOut, BadgeCheck, Plug,
  MessageCircle, Boxes, FileText, CheckCircle2, Loader2, GitPullRequest,
  Sparkles, Settings as SettingsIcon,
} from "lucide-react";
import { API } from "@/context/AuthContext";

const iconMap = {
  server: Server,
  "trending-down": TrendingDown,
  "alert-triangle": AlertTriangle,
  ticket: Ticket,
  "shield-check": ShieldCheck,
  "git-merge": GitMerge,
  activity: Activity,
  "log-in": LogIn,
  "user-plus": UserPlus,
  "log-out": LogOut,
  "badge-check": BadgeCheck,
  plug: Plug,
  "plug-zap": Plug,
  settings: SettingsIcon,
  "message-circle": MessageCircle,
  boxes: Boxes,
  "file-text": FileText,
  "check-circle-2": CheckCircle2,
  "loader-2": Loader2,
  "git-pull-request": GitPullRequest,
};

const accentBg = {
  indigo: "bg-indigo-50 text-indigo-600",
  emerald: "bg-emerald-50 text-emerald-600",
  amber: "bg-amber-50 text-amber-600",
  violet: "bg-violet-50 text-violet-600",
  rose: "bg-rose-50 text-rose-600",
  sky: "bg-sky-50 text-sky-600",
  slate: "bg-slate-50 text-slate-600",
};

const statusStyle = {
  success: "bg-emerald-50 text-emerald-600 border-emerald-100",
  warning: "bg-amber-50 text-amber-600 border-amber-100",
  info: "bg-sky-50 text-sky-600 border-sky-100",
  danger: "bg-rose-50 text-rose-600 border-rose-100",
  neutral: "bg-slate-50 text-slate-600 border-slate-200",
};

function Skel() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-start gap-3 py-2">
          <div className="h-9 w-9 rounded-xl bg-slate-100 animate-pulse" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-3/4 bg-slate-100 rounded animate-pulse" />
            <div className="h-2.5 w-1/3 bg-slate-100 rounded animate-pulse" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div data-testid="recent-activity-empty" className="text-center px-4 py-10">
      <div className="mx-auto h-12 w-12 rounded-2xl bg-slate-50 grid place-items-center">
        <Sparkles className="h-5 w-5 text-slate-300" />
      </div>
      <div className="mt-3 text-[13px] font-semibold text-slate-700">No recent activity yet</div>
      <div className="mt-1 text-[12px] text-slate-400 max-w-xs mx-auto">
        As you sign in, onboard, deploy or chat with agents, events will appear here in real time.
      </div>
    </div>
  );
}

export default function RecentActivity({ items }) {
  const nav = useNavigate();

  // Keep this section fresh: revalidate every 15s in addition to WS pushes
  useEffect(() => {
    const t = setInterval(() => globalMutate(`${API}/activity?limit=6`), 15000);
    return () => clearInterval(t);
  }, []);

  return (
    <div
      data-testid="recent-activity-card"
      className="bg-white rounded-2xl border border-slate-200/80 p-5 sticky top-24 flex flex-col max-h-[calc(100vh-160px)]"
    >
      <div className="flex items-center justify-between shrink-0">
        <h3 className="text-[11px] font-semibold tracking-[0.18em] uppercase text-slate-400">
          Recent Activity
        </h3>
        <button
          data-testid="recent-activity-view-all"
          onClick={() => nav("/activity")}
          className="text-[12px] font-semibold text-indigo-600 hover:text-indigo-700 inline-flex items-center gap-0.5"
        >
          View all <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>

      <div
        data-testid="recent-activity-list"
        className="mt-4 flex-1 overflow-y-auto pr-1 -mr-2 [scrollbar-width:thin]"
      >
        {!items ? (
          <Skel />
        ) : items.length === 0 ? (
          <EmptyState />
        ) : (
          <ul className="divide-y divide-slate-100">
            {items.map((a) => {
              const Icon = iconMap[a.icon] ?? Activity;
              return (
                <li
                  key={a.id}
                  data-testid={`recent-activity-${a.id}`}
                  className="flex items-start gap-3 py-3 first:pt-0"
                >
                  <div className={`h-9 w-9 rounded-xl grid place-items-center shrink-0 ${accentBg[a.accent] ?? accentBg.indigo}`}>
                    <Icon className="h-[16px] w-[16px]" strokeWidth={2.2} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="text-[13px] font-semibold text-slate-900 leading-snug truncate">
                        {a.title}
                      </div>
                      <span
                        className={`shrink-0 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                          statusStyle[a.status_tone] ?? statusStyle.neutral
                        }`}
                      >
                        {a.status}
                      </span>
                    </div>
                    {a.detail && (
                      <div className="text-[11.5px] text-slate-500 mt-0.5 line-clamp-2">
                        {a.detail}
                      </div>
                    )}
                    <div className="text-[10.5px] text-slate-400 mt-1">{a.time_ago}</div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
