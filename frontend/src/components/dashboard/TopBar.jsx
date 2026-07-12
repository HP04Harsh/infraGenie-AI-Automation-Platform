import React, { useState, useRef, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, ChevronDown, LogOut, User, Settings as SettingsIcon, X, Check, RefreshCw } from "lucide-react";
import axios from "axios";
import { useAuth, API } from "@/context/AuthContext";
import { useNotifications, useNotificationsWS, useMetrics } from "@/hooks/useTenantData";
import { mutate as globalMutate } from "swr";

const toneDot = {
  operational: "bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.18)]",
  degraded: "bg-amber-500 shadow-[0_0_0_3px_rgba(245,158,11,0.18)]",
  down: "bg-rose-500 shadow-[0_0_0_3px_rgba(244,63,94,0.18)]",
};

function RefreshButton() {
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const doRefresh = async () => {
    if (busy) return;
    setBusy(true);
    setToast(null);
    try {
      const res = await axios.post(`${API}/metrics/refresh`);
      // Revalidate all data hooks so KPIs, activity, notifications all refresh
      await Promise.all([
        globalMutate(`${API}/metrics`),
        globalMutate((k) => typeof k === "string" && k.startsWith(`${API}/activity`), undefined, { revalidate: true }),
        globalMutate(`${API}/notifications`),
      ]);
      setToast({ ok: true, msg: `Refreshed — ${res.data?.resources_total ?? 0} resources scanned` });
    } catch (e) {
      setToast({ ok: false, msg: e?.response?.data?.detail || e.message });
    } finally {
      setBusy(false);
      setTimeout(() => setToast(null), 3500);
    }
  };

  return (
    <div className="relative">
      <button
        data-testid="topbar-refresh"
        onClick={doRefresh}
        disabled={busy}
        title="Refresh tenant data"
        className="h-11 w-11 rounded-full bg-white border border-slate-200/80 grid place-items-center text-slate-500 hover:text-slate-800 hover:border-slate-300 transition shadow-[0_1px_2px_rgba(15,23,42,0.04)] disabled:opacity-70"
        aria-label="Refresh"
      >
        <RefreshCw className={`h-[17px] w-[17px] ${busy ? "animate-spin" : ""}`} />
      </button>
      {toast && (
        <div className={`absolute right-0 top-12 min-w-[240px] rounded-xl px-3 py-2 text-[12px] font-semibold shadow-lg border ${
          toast.ok ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-rose-50 text-rose-700 border-rose-200"
        }`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}

function StatusPill({ status = "operational", label = "InfraGenie Portal" }) {
  const dot = toneDot[status] || toneDot.operational;
  const text = status === "operational" ? "All systems normal" : status;
  return (
    <div
      data-testid="topbar-portal-status"
      className="h-11 pl-3.5 pr-4 rounded-full bg-white border border-slate-200/80 flex items-center gap-2.5 shadow-[0_1px_2px_rgba(15,23,42,0.04)]"
      title={text}
    >
      <span className={`h-2.5 w-2.5 rounded-full ${dot} animate-pulse`} />
      <span className="text-[12.5px] font-semibold text-slate-800">
        {label} <span className="text-slate-400 font-medium">: {text}</span>
      </span>
    </div>
  );
}

function LocationPill({ region }) {
  if (!region) return null;
  return (
    <div
      data-testid="topbar-location"
      className="h-11 px-3.5 rounded-full bg-white border border-slate-200/80 flex items-center gap-2 shadow-[0_1px_2px_rgba(15,23,42,0.04)]"
    >
      <span className="text-[16px] leading-none">{region.flag || "🌐"}</span>
      <span className="text-[12.5px] font-semibold text-slate-800">{region.display}</span>
    </div>
  );
}

function NotificationsPanel({ open, onClose }) {
  const { data } = useNotifications();
  const items = data?.items || [];
  const unread = data?.unread || 0;

  const markAllRead = async () => {
    try {
      await axios.post(`${API}/notifications/read`);
      globalMutate(`${API}/notifications`);
    } catch { /* noop */ }
  };

  const markOneRead = async (id) => {
    try {
      await axios.post(`${API}/notifications/${id}/read`);
      globalMutate(`${API}/notifications`);
    } catch { /* noop */ }
  };

  return (
    <>
      {open && (
        <div
          data-testid="notifications-overlay"
          onClick={onClose}
          className="fixed inset-0 bg-slate-900/20 backdrop-blur-[2px] z-40"
        />
      )}
      <aside
        data-testid="notifications-panel"
        className={`fixed top-0 right-0 h-full w-full sm:w-[400px] bg-white z-50 shadow-2xl border-l border-slate-200 transform transition-transform duration-300 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <header className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div>
            <h3 className="text-[15px] font-semibold text-slate-900">Notifications</h3>
            <p className="text-[11.5px] text-slate-500 mt-0.5">
              {unread ? `${unread} unread` : "You're all caught up"}
            </p>
          </div>
          <div className="flex items-center gap-1">
            {unread > 0 && (
              <button
                data-testid="notifications-mark-all"
                onClick={markAllRead}
                className="text-[11.5px] font-semibold text-indigo-600 hover:text-indigo-700 px-2 py-1"
              >
                Mark all read
              </button>
            )}
            <button
              data-testid="notifications-close"
              onClick={onClose}
              className="h-8 w-8 rounded-lg grid place-items-center text-slate-400 hover:text-slate-700 hover:bg-slate-100"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </header>

        <div className="overflow-y-auto h-[calc(100%-73px)] px-3 py-3">
          {items.length === 0 ? (
            <div className="text-center px-6 py-16">
              <div className="mx-auto h-12 w-12 rounded-2xl bg-slate-50 grid place-items-center">
                <Bell className="h-5 w-5 text-slate-300" />
              </div>
              <div className="mt-3 text-[13px] font-semibold text-slate-700">No notifications yet</div>
              <div className="mt-1 text-[12px] text-slate-400">
                Signups, deployments, and Azure events will appear here in real-time.
              </div>
            </div>
          ) : (
            <ul className="space-y-2">
              {items.map((n) => (
                <li
                  key={n.id}
                  data-testid={`notification-item-${n.id}`}
                  className={`group rounded-xl border p-3 flex items-start gap-3 transition ${
                    n.read
                      ? "bg-white border-slate-100"
                      : "bg-indigo-50/40 border-indigo-100"
                  }`}
                >
                  <div className="mt-0.5 h-2 w-2 rounded-full shrink-0 bg-indigo-500" style={{ opacity: n.read ? 0.25 : 1 }} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[12.5px] font-semibold text-slate-900 truncate">{n.title}</span>
                      <span className="text-[10.5px] text-slate-400 shrink-0">{n.time_ago}</span>
                    </div>
                    {n.detail && (
                      <p className="mt-0.5 text-[12px] text-slate-500 line-clamp-2">{n.detail}</p>
                    )}
                    <div className="mt-1 text-[10.5px] font-semibold uppercase tracking-wider text-slate-400">
                      {n.actor || "System"}
                    </div>
                  </div>
                  {!n.read && (
                    <button
                      onClick={() => markOneRead(n.id)}
                      className="opacity-0 group-hover:opacity-100 transition h-7 w-7 rounded-lg grid place-items-center text-slate-400 hover:text-emerald-600 hover:bg-emerald-50"
                      aria-label="Mark read"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </>
  );
}

function UserDropdown({ userName, userEmail, initials }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const { logout } = useAuth();
  const nav = useNavigate();

  useEffect(() => {
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        data-testid="topbar-user"
        onClick={() => setOpen((s) => !s)}
        className="h-11 pl-1 pr-3 rounded-full bg-white border border-slate-200/80 hover:border-slate-300 flex items-center gap-2 cursor-pointer transition shadow-[0_1px_2px_rgba(15,23,42,0.04)]"
      >
        <div className="h-9 w-9 rounded-full bg-gradient-to-br from-indigo-500 to-violet-500 grid place-items-center text-white text-[12.5px] font-semibold">
          {initials}
        </div>
        <div className="hidden md:block leading-tight pr-1">
          <div data-testid="topbar-user-name" className="text-[12.5px] font-semibold text-slate-900">
            {userName}
          </div>
        </div>
        <ChevronDown className={`h-3.5 w-3.5 text-slate-400 transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div
          data-testid="user-dropdown"
          className="absolute right-0 mt-2 w-64 rounded-2xl bg-white border border-slate-200 shadow-[0_20px_50px_-20px_rgba(15,23,42,0.25)] py-1.5 z-50"
        >
          <div className="px-4 py-3 border-b border-slate-100">
            <div className="text-[13px] font-semibold text-slate-900 truncate">{userName}</div>
            <div className="text-[11.5px] text-slate-500 truncate">{userEmail}</div>
          </div>
          <button
            onClick={() => { setOpen(false); nav("/settings"); }}
            className="w-full text-left px-4 py-2.5 text-[12.5px] text-slate-700 hover:bg-slate-50 flex items-center gap-2.5"
          >
            <SettingsIcon className="h-4 w-4 text-slate-400" /> Settings
          </button>
          <button
            onClick={() => { setOpen(false); nav("/support"); }}
            className="w-full text-left px-4 py-2.5 text-[12.5px] text-slate-700 hover:bg-slate-50 flex items-center gap-2.5"
          >
            <User className="h-4 w-4 text-slate-400" /> Support
          </button>
          <div className="my-1 border-t border-slate-100" />
          <button
            data-testid="user-dropdown-signout"
            onClick={() => { setOpen(false); logout(); }}
            className="w-full text-left px-4 py-2.5 text-[12.5px] text-rose-600 hover:bg-rose-50 flex items-center gap-2.5 font-semibold"
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export default function TopBar() {
  const { user } = useAuth();
  const { data: notifs } = useNotifications();
  const { data: metrics } = useMetrics();
  useNotificationsWS();
  const unread = notifs?.unread ?? 0;

  const [notifOpen, setNotifOpen] = useState(false);

  const userName = user?.name || user?.email?.split("@")[0] || "User";
  const initials = useMemo(
    () => userName.split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase(),
    [userName],
  );

  const region = metrics?.tenant
    ? {
        display: metrics.tenant.region_display || "Central India",
        flag: metrics.tenant.region_flag || "🇮🇳",
      }
    : { display: "Central India", flag: "🇮🇳" };
  const portalStatus = metrics?.tenant?.portal_status || "operational";

  return (
    <>
      <header
        data-testid="dashboard-topbar"
        className="sticky top-0 z-20 bg-[#F4F4FB]/85 backdrop-blur-md"
      >
        <div className="px-6 lg:px-10 max-w-[1480px] mx-auto pt-6 pb-2 flex items-center gap-3 flex-wrap">
          <StatusPill status={portalStatus} />
          <LocationPill region={region} />

          <div className="flex-1" />

          <div className="flex items-center gap-2.5">
            <RefreshButton />
            <button
              data-testid="topbar-notifications"
              onClick={() => setNotifOpen(true)}
              className="relative h-11 w-11 rounded-full bg-white border border-slate-200/80 grid place-items-center text-slate-500 hover:text-slate-800 hover:border-slate-300 transition shadow-[0_1px_2px_rgba(15,23,42,0.04)]"
              aria-label="Notifications"
            >
              <Bell className="h-[17px] w-[17px]" />
              {unread > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-rose-500 text-white text-[10px] font-semibold grid place-items-center ring-2 ring-white">
                  {unread}
                </span>
              )}
            </button>

            <UserDropdown userName={userName} userEmail={user?.email} initials={initials} />
          </div>
        </div>
      </header>

      <NotificationsPanel open={notifOpen} onClose={() => setNotifOpen(false)} />
    </>
  );
}
