import React, { useEffect, useState } from "react";
import {
  Server,
  ShieldCheck,
  AlertTriangle,
  DollarSign,
  BadgeCheck,
  ArrowUpRight,
} from "lucide-react";
import { formatCurrency } from "@/lib/currency";

const iconMap = {
  server: Server,
  "shield-check": ShieldCheck,
  "alert-triangle": AlertTriangle,
  "dollar-sign": DollarSign,
  "badge-check": BadgeCheck,
};

const accentMap = {
  indigo: { bg: "bg-indigo-50", fg: "text-indigo-600", ring: "ring-indigo-100" },
  emerald: { bg: "bg-emerald-50", fg: "text-emerald-600", ring: "ring-emerald-100" },
  amber: { bg: "bg-amber-50", fg: "text-amber-600", ring: "ring-amber-100" },
  rose: { bg: "bg-rose-50", fg: "text-rose-600", ring: "ring-rose-100" },
  violet: { bg: "bg-violet-50", fg: "text-violet-600", ring: "ring-violet-100" },
};

const toneClass = {
  good: "text-emerald-600",
  warn: "text-amber-600",
  danger: "text-rose-600",
  neutral: "text-slate-500",
};

function useCountUp(target, duration = 900) {
  const [val, setVal] = useState(target ?? 0);
  useEffect(() => {
    if (target == null) return;
    let raf;
    const startVal = 0;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setVal(startVal + (target - startVal) * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
      else setVal(target);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return val;
}

function formatDisplay(rawAnimated, card) {
  if (!card) return "";
  // Currency-aware for cost - always show 2 decimal places
  if (card.key === "cost") {
    return formatCurrency(rawAnimated, card.currency || "INR", { maxFractionDigits: 2, minFractionDigits: 2 });
  }
  // Percent for compliance
  if (String(card.value).endsWith("%")) {
    return `${Math.round(rawAnimated)}%`;
  }
  return Math.round(rawAnimated).toLocaleString();
}

function KpiCard({ card, index, loading }) {
  const Icon = iconMap[card?.icon] ?? Server;
  const accent = accentMap[card?.accent] ?? accentMap.indigo;
  const animated = useCountUp(card?.raw ?? 0);

  return (
    <div
      data-testid={`kpi-${card?.key ?? `skeleton-${index}`}`}
      className="group relative bg-white rounded-2xl border border-slate-200/80 px-3.5 py-3 hover:-translate-y-0.5 hover:shadow-[0_20px_50px_-30px_rgba(15,23,42,0.18)] transition-all duration-300"
      style={card ? { animation: `kpi-fade 600ms ${index * 70}ms both` } : undefined}
    >
      <div className="flex items-center gap-3">
        <div className={`h-10 w-10 rounded-xl grid place-items-center shrink-0 ${accent.bg} ${accent.fg} ring-4 ${accent.ring}`}>
          <Icon className="h-[16px] w-[16px]" strokeWidth={2.2} />
        </div>

        <div className="flex-1 min-w-0">
          {loading ? (
            <>
              <div className="h-3 w-20 bg-slate-100 rounded animate-pulse" />
              <div className="h-6 w-24 bg-slate-100 rounded mt-1.5 animate-pulse" />
              <div className="h-2.5 w-28 bg-slate-100 rounded mt-1.5 animate-pulse" />
            </>
          ) : (
            <>
              <div className="text-[11px] font-semibold uppercase tracking-[0.10em] text-slate-400 truncate">
                {card.label}
              </div>
              <div
                data-testid={`kpi-${card.key}-value`}
                className="mt-0.5 text-[22px] font-semibold tracking-tight text-slate-900 leading-tight truncate"
              >
                {formatDisplay(animated, card)}
              </div>
              <div
                data-testid={`kpi-${card.key}-sub`}
                className={`text-[11px] mt-0.5 font-semibold truncate ${toneClass[card.sub_tone] ?? "text-slate-500"}`}
              >
                {card.sub}
              </div>
            </>
          )}
        </div>

        {!loading && (
          <button
            data-testid={`kpi-${card.key}-open`}
            className="hidden xl:grid h-6 w-6 rounded-lg place-items-center text-slate-300 hover:text-slate-700 hover:bg-slate-50 transition shrink-0 opacity-0 group-hover:opacity-100"
            aria-label="Open"
          >
            <ArrowUpRight className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}

export default function OverviewKpis({ cards }) {
  const placeholders = Array.from({ length: 5 });
  const list = cards && cards.length ? cards : placeholders;

  return (
    <>
      <style>{`
        @keyframes kpi-fade {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      <div
        data-testid="kpi-row"
        className="grid grid-cols-2 md:grid-cols-3 gap-3.5"
      >
        {list.map((c, i) => (
          <KpiCard key={c?.key ?? i} card={c ?? null} index={i} loading={!c} />
        ))}
      </div>
    </>
  );
}
