import React from "react";
import { Search, Bell, ChevronDown, Calendar } from "lucide-react";

export default function Header() {
  const hour = new Date().getHours();
  const greeting =
    hour < 5 ? "Working late" : hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  return (
    <header
      data-testid="dashboard-header"
      className="sticky top-0 z-20 bg-[#F7F8FB]/85 backdrop-blur-md border-b border-slate-200/70"
    >
      <div className="px-6 lg:px-10 max-w-[1500px] mx-auto py-5 flex items-center gap-6 flex-wrap">
        {/* Greeting */}
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[12px] text-slate-500 font-medium">
            <Calendar className="h-3.5 w-3.5" />
            <span>{today}</span>
          </div>
          <h1
            data-testid="greeting-title"
            className="mt-1 text-[26px] lg:text-[30px] font-semibold tracking-tight text-slate-900 leading-tight"
          >
            {greeting},{" "}
            <span className="text-[#6366F1]">Alex</span>
            <span className="text-slate-400 font-normal text-[22px] ml-1">— here's your cloud snapshot</span>
          </h1>
        </div>

        <div className="flex-1" />

        {/* Search */}
        <div className="relative flex-1 max-w-md min-w-[220px]">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            data-testid="header-search"
            type="text"
            placeholder="Search resources, accounts, alerts…"
            className="w-full h-11 rounded-xl bg-white border border-slate-200 pl-10 pr-3 text-[13.5px] placeholder:text-slate-400 outline-none focus:border-[#6366F1] focus:ring-4 focus:ring-indigo-100 transition"
          />
          <kbd className="hidden md:inline-flex absolute right-3 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded border border-slate-200 bg-slate-50 text-[10px] text-slate-500">
            ⌘K
          </kbd>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            data-testid="period-selector"
            className="h-11 px-3.5 rounded-xl bg-white border border-slate-200 hover:border-slate-300 text-[13px] font-medium text-slate-700 flex items-center gap-2 transition"
          >
            Last 30 days
            <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
          </button>

          <button
            data-testid="header-notifications"
            className="relative h-11 w-11 rounded-xl bg-white border border-slate-200 hover:border-slate-300 grid place-items-center transition"
          >
            <Bell className="h-[18px] w-[18px] text-slate-600" />
            <span className="absolute top-2.5 right-2.5 h-2 w-2 rounded-full bg-rose-500 ring-2 ring-white" />
          </button>

          <div
            data-testid="header-user"
            className="h-11 pl-1 pr-3 rounded-xl bg-white border border-slate-200 hover:border-slate-300 flex items-center gap-2 cursor-pointer transition"
          >
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-[#6366F1] to-fuchsia-500 grid place-items-center text-white font-semibold text-[12.5px]">
              AC
            </div>
            <div className="hidden md:block leading-tight">
              <div className="text-[12.5px] font-semibold text-slate-900">Alex Chen</div>
              <div className="text-[10.5px] text-slate-500">Admin</div>
            </div>
            <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
          </div>
        </div>
      </div>
    </header>
  );
}
