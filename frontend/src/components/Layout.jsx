import React from "react";
import Sidebar from "@/components/dashboard/Sidebar";
import TopBar from "@/components/dashboard/TopBar";

export default function Layout({ children }) {
  return (
    <div
      data-testid="app-layout"
      className="min-h-screen bg-[#F4F4FB] text-slate-900"
      style={{ fontFamily: '"Plus Jakarta Sans", "Manrope", system-ui, sans-serif' }}
    >
      <div className="flex">
        <Sidebar />
        <main className="flex-1 min-w-0 lg:ml-[260px]">
          <TopBar />
          <div className="px-6 lg:px-10 pb-16 pt-2 max-w-[1480px] mx-auto">{children}</div>
        </main>
      </div>
    </div>
  );
}
