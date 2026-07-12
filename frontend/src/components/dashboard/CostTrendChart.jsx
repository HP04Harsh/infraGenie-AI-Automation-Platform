import React, { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Line,
} from "recharts";
import { ArrowUpRight, MoreHorizontal } from "lucide-react";

const data = [
  { d: "Jan 01", actual: 4200, forecast: 4150 },
  { d: "Jan 05", actual: 4850, forecast: 4400 },
  { d: "Jan 09", actual: 5100, forecast: 4700 },
  { d: "Jan 13", actual: 4700, forecast: 4900 },
  { d: "Jan 17", actual: 5400, forecast: 5200 },
  { d: "Jan 21", actual: 6200, forecast: 5500 },
  { d: "Jan 25", actual: 5900, forecast: 5800 },
  { d: "Jan 29", actual: 6700, forecast: 6100 },
  { d: "Feb 02", actual: 6300, forecast: 6300 },
  { d: "Feb 06", actual: 7100, forecast: 6500 },
  { d: "Feb 10", actual: 7600, forecast: 6800 },
  { d: "Feb 14", actual: 8200, forecast: 7100 },
];

const tabs = [
  { key: "7d", label: "7d", testId: "cost-range-7d" },
  { key: "30d", label: "30d", testId: "cost-range-30d" },
  { key: "90d", label: "90d", testId: "cost-range-90d" },
  { key: "ytd", label: "YTD", testId: "cost-range-ytd" },
];

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white shadow-xl border border-slate-200 rounded-xl p-3 min-w-[160px]">
      <div className="text-[11px] text-slate-500 font-medium mb-1.5">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4 text-[12.5px] py-0.5">
          <div className="flex items-center gap-2">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: p.dataKey === "actual" ? "#6366F1" : "#CBD5E1" }}
            />
            <span className="text-slate-600 capitalize">{p.dataKey}</span>
          </div>
          <span className="font-semibold text-slate-900">${p.value.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

export default function CostTrendChart() {
  const [range, setRange] = useState("30d");

  const total = data.reduce((s, x) => s + x.actual, 0);

  return (
    <div
      data-testid="cost-trend-card"
      className="bg-white rounded-2xl border border-slate-200/80 p-6"
    >
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-[15.5px] font-semibold tracking-tight text-slate-900">
              Cost trend
            </h3>
            <span className="text-[10.5px] uppercase tracking-wide font-semibold text-[#6366F1] bg-indigo-50 px-2 py-0.5 rounded-full">
              Live
            </span>
          </div>
          <div className="mt-1 flex items-baseline gap-3">
            <div
              data-testid="cost-trend-total"
              className="text-[26px] font-semibold tracking-tight text-slate-900"
            >
              ${total.toLocaleString()}
            </div>
            <div className="text-[12px] font-semibold text-emerald-600 flex items-center gap-1">
              <ArrowUpRight className="h-3.5 w-3.5" />
              +14.2%
            </div>
            <div className="text-[12px] text-slate-400">vs previous period</div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="bg-slate-100 rounded-lg p-1 flex items-center text-[12px] font-medium">
            {tabs.map((t) => (
              <button
                key={t.key}
                data-testid={t.testId}
                onClick={() => setRange(t.key)}
                className={`px-3 py-1.5 rounded-md transition ${
                  range === t.key
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <button
            data-testid="cost-trend-more"
            className="h-9 w-9 rounded-lg border border-slate-200 grid place-items-center text-slate-500 hover:text-slate-800 hover:border-slate-300"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-5 mt-3 text-[12px] text-slate-500">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-[#6366F1]" />
          <span>Actual spend</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full border border-slate-300 bg-white" />
          <span>Forecast</span>
        </div>
      </div>

      <div className="mt-4 h-[300px]" data-testid="cost-trend-chart">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 8, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="actualFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6366F1" stopOpacity={0.28} />
                <stop offset="100%" stopColor="#6366F1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#EEF0F5" vertical={false} />
            <XAxis
              dataKey="d"
              tick={{ fill: "#94A3B8", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "#94A3B8", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: "#CBD5E1", strokeDasharray: 3 }} />
            <Area
              type="monotone"
              dataKey="actual"
              stroke="#6366F1"
              strokeWidth={2.5}
              fill="url(#actualFill)"
              animationDuration={900}
              dot={false}
              activeDot={{ r: 5, fill: "#6366F1", stroke: "#fff", strokeWidth: 2 }}
            />
            <Line
              type="monotone"
              dataKey="forecast"
              stroke="#CBD5E1"
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={false}
              animationDuration={900}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
