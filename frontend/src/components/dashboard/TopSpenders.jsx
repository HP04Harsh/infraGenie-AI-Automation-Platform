import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { ChevronRight } from "lucide-react";

const data = [
  { name: "EC2 Compute", value: 48230, share: 26.2, region: "us-east-1" },
  { name: "S3 Storage", value: 31420, share: 17.1, region: "global" },
  { name: "RDS Postgres", value: 24890, share: 13.5, region: "us-west-2" },
  { name: "CloudFront", value: 19340, share: 10.5, region: "global" },
  { name: "Lambda", value: 15780, share: 8.6, region: "us-east-1" },
  { name: "ElastiCache", value: 12450, share: 6.7, region: "eu-west-1" },
  { name: "OpenSearch", value: 9820, share: 5.3, region: "us-east-1" },
];

const colors = ["#6366F1", "#7C7BF6", "#9695F9", "#B5B4FB", "#CFCEFC", "#E4E3FD", "#EFEFFE"];

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="bg-white shadow-xl border border-slate-200 rounded-xl p-3 min-w-[180px]">
      <div className="text-[12.5px] font-semibold text-slate-900">{p.name}</div>
      <div className="text-[10.5px] text-slate-400 mb-1.5">{p.region}</div>
      <div className="flex items-center justify-between text-[12px]">
        <span className="text-slate-500">Spend</span>
        <span className="font-semibold text-slate-900">${p.value.toLocaleString()}</span>
      </div>
      <div className="flex items-center justify-between text-[12px]">
        <span className="text-slate-500">Share</span>
        <span className="font-semibold text-[#6366F1]">{p.share}%</span>
      </div>
    </div>
  );
}

export default function TopSpenders() {
  return (
    <div
      data-testid="top-spenders-card"
      className="bg-white rounded-2xl border border-slate-200/80 p-6 h-full"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-[15.5px] font-semibold tracking-tight text-slate-900">
            Top spenders
          </h3>
          <p className="text-[12px] text-slate-500 mt-1">
            Services consuming the highest cloud spend this month
          </p>
        </div>
        <button
          data-testid="top-spenders-view-all"
          className="text-[12px] text-[#6366F1] font-semibold hover:text-indigo-700 flex items-center gap-0.5"
        >
          View all <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="mt-5 h-[300px]" data-testid="top-spenders-chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid stroke="#EEF0F5" vertical={false} />
            <XAxis
              dataKey="name"
              tick={{ fill: "#94A3B8", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              interval={0}
              angle={-12}
              textAnchor="end"
              height={50}
            />
            <YAxis
              tick={{ fill: "#94A3B8", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(99,102,241,0.06)" }} />
            <Bar dataKey="value" radius={[8, 8, 0, 0]} animationDuration={900}>
              {data.map((_, i) => (
                <Cell key={i} fill={colors[i % colors.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
