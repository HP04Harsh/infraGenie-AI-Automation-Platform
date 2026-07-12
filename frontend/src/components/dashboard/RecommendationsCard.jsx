import React from "react";
import { Sparkles, ArrowRight, Zap } from "lucide-react";

const recs = [
  {
    id: 1,
    title: "Right-size 12 EC2 instances",
    save: "$3,840/mo",
    impact: "High",
    type: "Compute",
  },
  {
    id: 2,
    title: "Move cold S3 to Glacier Deep Archive",
    save: "$1,205/mo",
    impact: "Med",
    type: "Storage",
  },
  {
    id: 3,
    title: "Purchase 1-year RIs for RDS",
    save: "$4,180/mo",
    impact: "High",
    type: "Database",
  },
  {
    id: 4,
    title: "Delete 38 unused EBS volumes",
    save: "$612/mo",
    impact: "Low",
    type: "Storage",
  },
];

const impactStyles = {
  High: "bg-rose-50 text-rose-600",
  Med: "bg-amber-50 text-amber-600",
  Low: "bg-slate-100 text-slate-600",
};

export default function RecommendationsCard() {
  return (
    <div
      data-testid="recommendations-card"
      className="rounded-2xl border border-indigo-200/60 p-6 h-full relative overflow-hidden bg-gradient-to-br from-white via-indigo-50/40 to-white"
    >
      <div className="absolute -top-12 -right-12 h-40 w-40 rounded-full bg-indigo-200/40 blur-3xl pointer-events-none" />
      <div className="relative">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-[#6366F1] grid place-items-center shadow-[0_8px_20px_-8px_rgba(99,102,241,0.7)]">
              <Sparkles className="h-4 w-4 text-white" />
            </div>
            <h3 className="text-[15.5px] font-semibold tracking-tight text-slate-900">
              AI Recommendations
            </h3>
          </div>
          <span className="text-[10.5px] uppercase tracking-wide font-semibold text-[#6366F1] bg-white border border-indigo-200 px-2 py-0.5 rounded-full">
            Genie
          </span>
        </div>

        <div className="mt-3 flex items-baseline gap-2">
          <div
            data-testid="recommendations-total-savings"
            className="text-[26px] font-semibold tracking-tight text-slate-900"
          >
            $9,837
          </div>
          <div className="text-[12px] text-slate-500">potential savings / mo</div>
        </div>

        <ul className="mt-4 space-y-2.5">
          {recs.map((r) => (
            <li
              key={r.id}
              data-testid={`recommendation-${r.id}`}
              className="group bg-white rounded-xl border border-slate-200/80 px-3.5 py-3 flex items-center gap-3 hover:border-[#6366F1] hover:shadow-[0_18px_40px_-30px_rgba(99,102,241,0.6)] transition-all cursor-pointer"
            >
              <div className="h-8 w-8 rounded-lg bg-indigo-50 grid place-items-center shrink-0">
                <Zap className="h-4 w-4 text-[#6366F1]" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-semibold text-slate-900 truncate">
                  {r.title}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[11px] text-emerald-600 font-semibold">{r.save}</span>
                  <span className="text-[11px] text-slate-300">•</span>
                  <span className="text-[11px] text-slate-500">{r.type}</span>
                </div>
              </div>
              <span
                className={`text-[10.5px] font-semibold px-1.5 py-0.5 rounded ${impactStyles[r.impact]}`}
              >
                {r.impact}
              </span>
              <ArrowRight className="h-4 w-4 text-slate-300 group-hover:text-[#6366F1] group-hover:translate-x-0.5 transition" />
            </li>
          ))}
        </ul>

        <button
          data-testid="recommendations-apply-all"
          className="mt-5 w-full h-11 rounded-xl bg-[#0F1431] text-white text-[13px] font-semibold hover:bg-[#1a2050] transition flex items-center justify-center gap-2"
        >
          Review & apply
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
