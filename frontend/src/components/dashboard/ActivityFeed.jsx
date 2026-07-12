import React from "react";
import {
  GitMerge,
  AlertOctagon,
  ShieldCheck,
  DollarSign,
  Server,
  UserPlus,
  ChevronRight,
} from "lucide-react";

const activities = [
  {
    id: 1,
    icon: AlertOctagon,
    title: "Anomalous spend detected on RDS Postgres",
    detail: "+$1,240 vs forecast in us-west-2",
    time: "12m ago",
    tone: "danger",
    actor: "Cost Sentinel",
  },
  {
    id: 2,
    icon: ShieldCheck,
    title: "S3 bucket policy hardened",
    detail: "Public access disabled on 3 buckets",
    time: "1h ago",
    tone: "success",
    actor: "Auto-remediation",
  },
  {
    id: 3,
    icon: GitMerge,
    title: "Terraform plan merged to main",
    detail: "infra/eks-prod • 14 resources changed",
    time: "2h ago",
    tone: "info",
    actor: "alex.chen",
  },
  {
    id: 4,
    icon: DollarSign,
    title: "Reserved instance recommendation accepted",
    detail: "Projected savings $4,180 / mo",
    time: "4h ago",
    tone: "indigo",
    actor: "Optimizer",
  },
  {
    id: 5,
    icon: Server,
    title: "Idle EC2 instances flagged",
    detail: "8 t3.medium running <2% CPU for 7d",
    time: "6h ago",
    tone: "warning",
    actor: "Resource Watch",
  },
  {
    id: 6,
    icon: UserPlus,
    title: "New member invited to Production",
    detail: "priya.sharma@acme.com • Viewer",
    time: "Yesterday",
    tone: "neutral",
    actor: "alex.chen",
  },
];

const toneMap = {
  danger: "bg-rose-50 text-rose-600",
  success: "bg-emerald-50 text-emerald-600",
  info: "bg-sky-50 text-sky-600",
  indigo: "bg-indigo-50 text-[#6366F1]",
  warning: "bg-amber-50 text-amber-600",
  neutral: "bg-slate-100 text-slate-600",
};

export default function ActivityFeed() {
  return (
    <div
      data-testid="activity-feed-card"
      className="bg-white rounded-2xl border border-slate-200/80 p-6 h-full"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-[15.5px] font-semibold tracking-tight text-slate-900">
            Activity feed
          </h3>
          <p className="text-[12px] text-slate-500 mt-1">
            Real-time events across your cloud workspace
          </p>
        </div>
        <button
          data-testid="activity-feed-all"
          className="text-[12px] text-[#6366F1] font-semibold hover:text-indigo-700 flex items-center gap-0.5"
        >
          See all <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>

      <ul className="mt-5 relative">
        <span className="absolute left-[19px] top-2 bottom-2 w-px bg-slate-100" aria-hidden />
        {activities.map((a, i) => {
          const Icon = a.icon;
          return (
            <li
              key={a.id}
              data-testid={`activity-item-${a.id}`}
              className="relative flex gap-4 py-3"
            >
              <div className={`relative z-10 h-10 w-10 rounded-xl grid place-items-center shrink-0 ${toneMap[a.tone]}`}>
                <Icon className="h-[18px] w-[18px]" strokeWidth={2.2} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-3">
                  <div className="text-[13.5px] font-semibold text-slate-900 leading-snug">
                    {a.title}
                  </div>
                  <div className="text-[11px] text-slate-400 shrink-0 mt-0.5">{a.time}</div>
                </div>
                <div className="text-[12.5px] text-slate-500 mt-0.5">{a.detail}</div>
                <div className="text-[11px] text-slate-400 mt-1">by {a.actor}</div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
