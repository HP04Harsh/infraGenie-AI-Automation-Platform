import React, { useMemo, useState } from "react";
import Layout from "@/components/Layout";
import HeroSection from "@/components/dashboard/HeroSection";
import OverviewKpis from "@/components/dashboard/OverviewKpis";
import QuickActions from "@/components/dashboard/QuickActions";
import RecentActivity from "@/components/dashboard/RecentActivity";
import { useActivity } from "@/hooks/useTenantData";
import { useTenantSummary } from "@/hooks/useTenantSummary";
import { useAuth } from "@/context/AuthContext";
import { RefreshCw } from "lucide-react";

export default function Dashboard() {
  const { user } = useAuth();
  const { data: summary, refresh } = useTenantSummary();
  const { data: activity } = useActivity(20, true);
  const [refreshing, setRefreshing] = useState(false);

  const cards = useMemo(() => {
    if (!summary) return null;
    return [
      { key: "resources", label: "Total Resources", value: String(summary.resources ?? 0), raw: summary.resources ?? 0, icon: "server", accent: "indigo", sub: `${summary.resource_groups ?? 0} resource groups`, sub_tone: "neutral" },
      { key: "healthy", label: "Healthy Resources", value: String(summary.resources ?? 0), raw: summary.resources ?? 0, icon: "shield-check", accent: "emerald", sub: "Live from tenant", sub_tone: "good" },
      { key: "incidents", label: "Open Incidents", value: "0", raw: 0, icon: "alert-triangle", accent: "amber", sub: "All clear", sub_tone: "good" },
      { key: "cost", label: "Monthly Cost", value: String(summary.monthly_cost ?? 0), raw: summary.monthly_cost ?? 0, currency: summary.currency || "INR", icon: "dollar-sign", accent: "rose", sub: "Month-to-date spend", sub_tone: "neutral" },
      { key: "compliance", label: "Compliance Score", value: `${summary.secure_score ?? 0}%`, raw: summary.secure_score ?? 0, icon: "badge-check", accent: "violet", sub: "Defender secure score", sub_tone: (summary.secure_score ?? 0) >= 60 ? "good" : "warn" },
    ];
  }, [summary]);

  const onRefresh = async () => { setRefreshing(true); await refresh(); setRefreshing(false); };

  return (
    <Layout>
      <div className="pt-8">
        <HeroSection greeting={undefined} userName={user?.name?.split(" ")?.[0]} />

        <div className="mt-8 grid grid-cols-1 xl:grid-cols-3 gap-8">
          <div className="xl:col-span-2 space-y-10">
            <section>
              <div className="flex items-center justify-between">
                <SectionLabel testId="section-overview">Overview</SectionLabel>
                <button data-testid="dash-refresh" onClick={onRefresh} className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-700 inline-flex items-center gap-1">
                  <RefreshCw className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`} /> Refresh
                </button>
              </div>
              <div className="mt-4">
                <OverviewKpis cards={cards} />
              </div>
              {summary?.cached && (
                <div className="mt-2 text-[10.5px] text-slate-400">Cached • Click Refresh for a live tenant scan.</div>
              )}
            </section>

            <section>
              <SectionLabel testId="section-quick-actions">Quick Actions</SectionLabel>
              <div className="mt-4">
                <QuickActions />
              </div>
            </section>
          </div>

          <aside className="xl:col-span-1">
            <RecentActivity items={activity?.items} />
          </aside>
        </div>
      </div>
    </Layout>
  );
}

function SectionLabel({ children, testId }) {
  return (
    <div data-testid={testId} className="text-[11px] font-semibold tracking-[0.18em] uppercase text-slate-400">
      {children}
    </div>
  );
}
