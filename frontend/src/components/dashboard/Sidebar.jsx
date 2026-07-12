import React, { useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  Search,
  Boxes,
  ClipboardCheck,
  Activity,
  TrendingDown,
  Wrench,
  Ticket,
  ShieldCheck,
  FileBarChart2,
  Settings,
  LifeBuoy,
  Sparkles,
  ChevronRight,
  LogOut,
} from "lucide-react";

const agents = [
  { key: "provisioning", label: "Provisioning Agent", icon: Boxes },
  { key: "assessment", label: "Assessment Agent", icon: ClipboardCheck },
  { key: "observability", label: "Observability Agent", icon: Activity },
  { key: "optimization", label: "Optimization Agent", icon: TrendingDown },
  { key: "troubleshoot", label: "Troubleshoot Agent", icon: Wrench },
  { key: "itsm", label: "ITSM Agent", icon: Ticket },
  { key: "policy", label: "Policy & Compliance Agent", icon: ShieldCheck },
  { key: "reports", label: "Reports Agent", icon: FileBarChart2 },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const [agentFilter, setAgentFilter] = useState("");
  const filtered = agents.filter((a) =>
    a.label.toLowerCase().includes(agentFilter.trim().toLowerCase())
  );

  const userName = user?.name || user?.email?.split("@")[0] || "User";
  const userInitials = userName
    .split(" ")
    .map((s) => s[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <aside
      data-testid="dashboard-sidebar"
      className="hidden lg:flex fixed left-0 top-0 bottom-0 w-[264px] flex-col z-30 border-r border-white/[0.04] text-slate-200"
      style={{ background: "#0B0F19" }}
    >
      {/* Brand */}
      <Link
        to="/dashboard"
        data-testid="sidebar-brand"
        className="px-5 pt-6 pb-5 flex items-center gap-2.5 hover:opacity-90 transition"
      >
        <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 grid place-items-center shadow-[0_10px_28px_-8px_rgba(99,102,241,0.7)]">
          <Sparkles className="h-[18px] w-[18px] text-white" strokeWidth={2.4} />
        </div>
        <div className="text-white font-semibold tracking-tight text-[18px]">
          Infra<span className="text-indigo-400">Genie</span>
        </div>
      </Link>

      {/* Sidebar search — filters the agents list below */}
      <div className="px-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
          <input
            data-testid="sidebar-search"
            type="text"
            value={agentFilter}
            onChange={(e) => setAgentFilter(e.target.value)}
            placeholder="Search agents…"
            className="w-full h-9 rounded-full bg-white/[0.04] border border-white/[0.06] pl-9 pr-3 text-[12.5px] text-slate-200 placeholder:text-slate-500 outline-none focus:border-indigo-400/60 transition"
          />
        </div>
      </div>

      {/* Nav */}
      <nav className="px-3 mt-6 flex-1 overflow-y-auto">
        <div className="px-3 text-[10.5px] uppercase tracking-[0.16em] text-slate-500 mb-2 font-semibold">
          Infrastructure Agents
        </div>
        {filtered.length === 0 ? (
          <div className="px-3 py-2 text-[12px] text-slate-500">No agents match.</div>
        ) : (
          <ul className="space-y-0.5">
            {filtered.map((a) => {
              const Icon = a.icon;
              return (
                <li key={a.key}>
                  <NavLink
                    to={`/agents/${a.key}`}
                    data-testid={`agent-${a.key}`}
                    className={({ isActive }) =>
                      `group w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all ${
                        isActive
                          ? "bg-indigo-500/15 text-white border border-indigo-400/30"
                          : "text-slate-300 hover:bg-white/[0.05] hover:text-white border border-transparent"
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon className={`h-[16px] w-[16px] ${isActive ? "text-indigo-300" : "text-slate-400"}`} strokeWidth={2} />
                        <span className="truncate">{a.label}</span>
                        {isActive && <ChevronRight className="h-3.5 w-3.5 ml-auto text-indigo-300" />}
                      </>
                    )}
                  </NavLink>
                </li>
              );
            })}
          </ul>
        )}

        <div className="px-3 mt-7 text-[10.5px] uppercase tracking-[0.16em] text-slate-500 mb-2 font-semibold">
          Settings &amp; Support
        </div>
        <ul className="space-y-0.5">
          <li>
            <NavLink
              to="/settings"
              data-testid="nav-settings"
              className={({ isActive }) =>
                `w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[13px] font-medium transition ${
                  isActive ? "bg-indigo-500/15 text-white border border-indigo-400/30" : "text-slate-300 hover:bg-white/[0.05] hover:text-white border border-transparent"
                }`
              }
            >
              <Settings className="h-[16px] w-[16px] text-slate-400" />
              <span>Settings</span>
            </NavLink>
          </li>
          <li>
            <NavLink
              to="/support"
              data-testid="nav-support"
              className={({ isActive }) =>
                `w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[13px] font-medium transition ${
                  isActive ? "bg-indigo-500/15 text-white border border-indigo-400/30" : "text-slate-300 hover:bg-white/[0.05] hover:text-white border border-transparent"
                }`
              }
            >
              <LifeBuoy className="h-[16px] w-[16px] text-slate-400" />
              <span>Support</span>
            </NavLink>
          </li>
        </ul>
      </nav>

      {/* User card */}
      <div className="p-3 border-t border-white/[0.05]">
        <div data-testid="sidebar-user" className="flex items-center gap-2.5 px-2 py-2 rounded-xl">
          <div className="h-8 w-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-500 grid place-items-center text-white text-[11.5px] font-semibold shrink-0">
            {userInitials}
          </div>
          <div className="flex-1 min-w-0 leading-tight">
            <div data-testid="sidebar-user-name" className="text-[12.5px] font-semibold text-white truncate">
              {userName}
            </div>
            <div className="text-[10.5px] text-slate-400 truncate">{user?.email}</div>
          </div>
          <button
            data-testid="sidebar-logout"
            onClick={logout}
            className="h-7 w-7 rounded-md grid place-items-center text-slate-400 hover:text-white hover:bg-white/[0.06]"
            aria-label="Log out"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
