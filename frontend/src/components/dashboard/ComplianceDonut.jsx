import React from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { CheckCircle2 } from "lucide-react";

const data = [
  { name: "Passing", value: 248, color: "#6366F1" },
  { name: "Warning", value: 42, color: "#F59E0B" },
  { name: "Failing", value: 18, color: "#EF4444" },
  { name: "Skipped", value: 12, color: "#CBD5E1" },
];

const total = data.reduce((s, x) => s + x.value, 0);
const passing = data[0].value;
const passingPct = Math.round((passing / total) * 100);

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="bg-white shadow-xl border border-slate-200 rounded-xl px-3 py-2">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
        <span className="text-[12px] text-slate-600">{p.name}</span>
      </div>
      <div className="text-[14px] font-semibold text-slate-900 mt-0.5">
        {p.value} checks
      </div>
    </div>
  );
}

export default function ComplianceDonut() {
  return (
    <div
      data-testid="compliance-donut-card"
      className="bg-white rounded-2xl border border-slate-200/80 p-6 h-full"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-[15.5px] font-semibold tracking-tight text-slate-900">
            Compliance
          </h3>
          <p className="text-[12px] text-slate-500 mt-1">SOC 2 • HIPAA • ISO 27001</p>
        </div>
        <span className="text-[10.5px] uppercase tracking-wide font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
          On track
        </span>
      </div>

      <div className="relative mt-3" data-testid="compliance-donut-chart">
        <div className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={62}
                outerRadius={88}
                dataKey="value"
                paddingAngle={3}
                stroke="none"
                animationDuration={900}
              >
                {data.map((d, i) => (
                  <Cell key={i} fill={d.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <CheckCircle2 className="h-5 w-5 text-[#6366F1] mb-1" />
          <div
            data-testid="compliance-passing-pct"
            className="text-[28px] font-semibold tracking-tight text-slate-900 leading-none"
          >
            {passingPct}%
          </div>
          <div className="text-[10.5px] text-slate-400 mt-1">passing of {total}</div>
        </div>
      </div>

      <div className="space-y-2 mt-4">
        {data.map((d) => (
          <div
            key={d.name}
            data-testid={`compliance-${d.name.toLowerCase()}`}
            className="flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: d.color }} />
              <span className="text-[12.5px] text-slate-700 font-medium">{d.name}</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-20 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${(d.value / total) * 100}%`,
                    background: d.color,
                  }}
                />
              </div>
              <span className="text-[12px] font-semibold text-slate-900 w-8 text-right">
                {d.value}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
