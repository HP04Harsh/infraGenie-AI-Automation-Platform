import React, { useEffect, useState } from "react";
import { ShieldCheck, ChevronRight } from "lucide-react";

const items = [
  { label: "Critical", count: 2, color: "bg-rose-500", textId: "sec-critical" },
  { label: "High", count: 6, color: "bg-amber-500", textId: "sec-high" },
  { label: "Medium", count: 11, color: "bg-yellow-400", textId: "sec-medium" },
  { label: "Resolved", count: 84, color: "bg-emerald-500", textId: "sec-resolved" },
];

export default function SecurityGauge() {
  const target = 92;
  const [val, setVal] = useState(0);

  useEffect(() => {
    let raf;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / 1200);
      const eased = 1 - Math.pow(1 - t, 3);
      setVal(target * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  // Half-circle gauge: arc from 180° to 360° (semi-circle on top)
  const radius = 78;
  const cx = 100;
  const cy = 100;
  const startAngle = 180;
  const endAngle = 360;
  const totalSweep = endAngle - startAngle;
  const progressAngle = startAngle + (val / 100) * totalSweep;

  const polar = (angle) => {
    const a = (angle * Math.PI) / 180;
    return { x: cx + radius * Math.cos(a), y: cy + radius * Math.sin(a) };
  };
  const s = polar(startAngle);
  const e = polar(endAngle);
  const p = polar(progressAngle);
  const largeArc = totalSweep > 180 ? 1 : 0;
  const bgPath = `M ${s.x} ${s.y} A ${radius} ${radius} 0 ${largeArc} 1 ${e.x} ${e.y}`;
  const progressLarge = progressAngle - startAngle > 180 ? 1 : 0;
  const progressPath = `M ${s.x} ${s.y} A ${radius} ${radius} 0 ${progressLarge} 1 ${p.x} ${p.y}`;

  return (
    <div
      data-testid="security-gauge-card"
      className="bg-white rounded-2xl border border-slate-200/80 p-6 h-full"
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-emerald-50 grid place-items-center">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
            </div>
            <h3 className="text-[15.5px] font-semibold tracking-tight text-slate-900">
              Security score
            </h3>
          </div>
          <p className="text-[12px] text-slate-500 mt-1.5">Posture across 17 services</p>
        </div>
        <button
          data-testid="security-details"
          className="text-[12px] text-[#6366F1] font-semibold hover:text-indigo-700 flex items-center gap-0.5"
        >
          Details <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="mt-2 flex flex-col items-center" data-testid="security-gauge-svg">
        <svg viewBox="0 0 200 120" width="100%" className="max-w-[260px]">
          <defs>
            <linearGradient id="gaugeGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#10B981" />
              <stop offset="60%" stopColor="#6366F1" />
              <stop offset="100%" stopColor="#A855F7" />
            </linearGradient>
          </defs>
          <path d={bgPath} fill="none" stroke="#EEF0F5" strokeWidth="14" strokeLinecap="round" />
          <path
            d={progressPath}
            fill="none"
            stroke="url(#gaugeGrad)"
            strokeWidth="14"
            strokeLinecap="round"
          />
          {/* Needle dot */}
          <circle cx={p.x} cy={p.y} r="6" fill="#fff" stroke="#6366F1" strokeWidth="3" />
        </svg>

        <div className="-mt-10 text-center">
          <div
            data-testid="security-gauge-value"
            className="text-[44px] font-semibold tracking-tight text-slate-900 leading-none"
          >
            {Math.round(val)}
          </div>
          <div className="text-[11.5px] text-slate-400 mt-1">out of 100 • Good</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2.5 mt-5">
        {items.map((i) => (
          <div
            key={i.label}
            data-testid={i.textId}
            className="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2.5 border border-slate-100"
          >
            <div className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${i.color}`} />
              <span className="text-[12px] text-slate-600 font-medium">{i.label}</span>
            </div>
            <span className="text-[13px] font-semibold text-slate-900">{i.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
