import React, { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, DollarSign, Server, ShieldCheck, AlertTriangle } from "lucide-react";

const kpis = [
  {
    key: "spend",
    testId: "kpi-spend",
    label: "Monthly spend",
    value: 184327,
    prefix: "$",
    delta: -8.4,
    deltaLabel: "vs last month",
    icon: DollarSign,
    accent: "indigo",
    spark: [42, 48, 41, 55, 49, 60, 56, 62, 58, 70, 64, 73],
  },
  {
    key: "resources",
    testId: "kpi-resources",
    label: "Active resources",
    value: 2741,
    delta: 12.3,
    deltaLabel: "this week",
    icon: Server,
    accent: "sky",
    spark: [10, 14, 13, 18, 17, 22, 24, 21, 28, 30, 33, 38],
  },
  {
    key: "security",
    testId: "kpi-security",
    label: "Security score",
    value: 92,
    suffix: "/100",
    delta: 3.1,
    deltaLabel: "improving",
    icon: ShieldCheck,
    accent: "emerald",
    spark: [70, 72, 74, 73, 78, 80, 82, 81, 85, 87, 90, 92],
  },
  {
    key: "alerts",
    testId: "kpi-alerts",
    label: "Open alerts",
    value: 17,
    delta: -22.5,
    deltaLabel: "last 7d",
    icon: AlertTriangle,
    accent: "amber",
    spark: [30, 28, 31, 27, 25, 26, 22, 24, 20, 19, 18, 17],
  },
];

const accentMap = {
  indigo: {
    icon: "bg-indigo-50 text-[#6366F1]",
    spark: "#6366F1",
    sparkBg: "rgba(99,102,241,0.12)",
  },
  sky: {
    icon: "bg-sky-50 text-sky-600",
    spark: "#0EA5E9",
    sparkBg: "rgba(14,165,233,0.12)",
  },
  emerald: {
    icon: "bg-emerald-50 text-emerald-600",
    spark: "#10B981",
    sparkBg: "rgba(16,185,129,0.12)",
  },
  amber: {
    icon: "bg-amber-50 text-amber-600",
    spark: "#F59E0B",
    sparkBg: "rgba(245,158,11,0.12)",
  },
};

function useCountUp(target, duration = 1100) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    let raf;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setVal(target * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
      else setVal(target);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return val;
}

function Sparkline({ data, color, fill }) {
  const w = 110;
  const h = 36;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const step = w / (data.length - 1);
  const points = data
    .map((v, i) => `${i * step},${h - ((v - min) / range) * (h - 4) - 2}`)
    .join(" ");
  const areaPath = `M0,${h} L${points.replaceAll(" ", " L")} L${w},${h} Z`;
  return (
    <svg width={w} height={h} className="overflow-visible" aria-hidden>
      <path d={areaPath} fill={fill} />
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
}

function formatValue(n, prefix, suffix) {
  let s;
  if (n >= 10000) s = Math.round(n).toLocaleString();
  else if (Number.isInteger(n)) s = String(Math.round(n));
  else s = n.toFixed(1);
  return `${prefix ?? ""}${s}${suffix ?? ""}`;
}

function KpiCard({ kpi, index }) {
  const Icon = kpi.icon;
  const styles = accentMap[kpi.accent];
  const animated = useCountUp(kpi.value);
  const positive = kpi.delta >= 0;
  // For 'alerts' and 'spend', negative delta is good
  const isGood =
    kpi.key === "alerts" || kpi.key === "spend" ? kpi.delta < 0 : kpi.delta > 0;

  return (
    <div
      data-testid={kpi.testId}
      className="group relative bg-white rounded-2xl border border-slate-200/80 p-5 hover:shadow-[0_24px_60px_-30px_rgba(15,23,42,0.18)] hover:-translate-y-0.5 transition-all duration-300"
      style={{ animation: `kpi-rise 600ms ${index * 80}ms both` }}
    >
      <div className="flex items-start justify-between">
        <div className={`h-10 w-10 rounded-xl grid place-items-center ${styles.icon}`}>
          <Icon className="h-[18px] w-[18px]" strokeWidth={2.2} />
        </div>
        <div
          className={`flex items-center gap-1 text-[11.5px] font-semibold px-2 py-1 rounded-full ${
            isGood ? "bg-emerald-50 text-emerald-600" : "bg-rose-50 text-rose-600"
          }`}
        >
          {positive ? (
            <TrendingUp className="h-3 w-3" />
          ) : (
            <TrendingDown className="h-3 w-3" />
          )}
          {Math.abs(kpi.delta).toFixed(1)}%
        </div>
      </div>

      <div className="mt-4">
        <div className="text-[12.5px] text-slate-500 font-medium">{kpi.label}</div>
        <div
          data-testid={`${kpi.testId}-value`}
          className="text-[28px] font-semibold tracking-tight text-slate-900 leading-tight mt-1"
        >
          {formatValue(animated, kpi.prefix, kpi.suffix)}
        </div>
        <div className="text-[11.5px] text-slate-400 mt-0.5">{kpi.deltaLabel}</div>
      </div>

      <div className="absolute right-4 bottom-4 opacity-90">
        <Sparkline data={kpi.spark} color={styles.spark} fill={styles.sparkBg} />
      </div>
    </div>
  );
}

export default function KpiRow() {
  return (
    <>
      <style>{`
        @keyframes kpi-rise {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      <div
        data-testid="kpi-row"
        className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5"
      >
        {kpis.map((k, i) => (
          <KpiCard key={k.key} kpi={k} index={i} />
        ))}
      </div>
    </>
  );
}
