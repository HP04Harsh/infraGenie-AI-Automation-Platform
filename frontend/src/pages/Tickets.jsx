import React, { useState, useRef, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Layout from "@/components/Layout";
import axios from "axios";
import { toast } from "sonner";
import { Search, Filter, Inbox, CheckCircle2, XCircle, Clock, Loader2, FileText, Send, MessageSquare, Server, Trash2, Plus, Bot, X, Ticket } from "lucide-react";
import { useTickets, useTicket, postTicketComment, startDestroy } from "@/hooks/useProvisioning";
import { mutate } from "swr";
import { API } from "@/context/AuthContext";

const statusStyle = {
  awaiting_approval: { bg: "bg-amber-50 text-amber-700 border-amber-200", icon: Clock, label: "Awaiting approval" },
  approved:          { bg: "bg-indigo-50 text-indigo-700 border-indigo-200", icon: CheckCircle2, label: "Approved" },
  deploying:         { bg: "bg-sky-50 text-sky-700 border-sky-200", icon: Loader2, label: "Deploying" },
  completed:         { bg: "bg-emerald-50 text-emerald-700 border-emerald-200", icon: CheckCircle2, label: "Completed" },
  failed:            { bg: "bg-rose-50 text-rose-700 border-rose-200", icon: XCircle, label: "Failed" },
  rejected:          { bg: "bg-slate-100 text-slate-600 border-slate-200", icon: XCircle, label: "Rejected" },
};

const timelineTone = {
  info:    "bg-sky-50 text-sky-700 border-sky-200",
  success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  danger:  "bg-rose-50 text-rose-700 border-rose-200",
  neutral: "bg-slate-50 text-slate-600 border-slate-200",
};

function formatMoney(value, currency = "USD") {
  if (value == null) return "—";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: (currency || "USD").toUpperCase(),
      maximumFractionDigits: 1,
    }).format(value);
  } catch (_e) {
    return `${currency} ${value}`;
  }
}

function ITSMChatPanel({ onClose }) {
  const [msgs, setMsgs] = useState([
    { role: "assistant", content: "Hi! I'm the ITSM assistant. I can help you create ServiceNow tickets, check status, or list your tickets. What would you like to do?" }
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const send = async () => {
    if (!input.trim() || busy) return;
    const text = input.trim();
    setInput("");
    setMsgs((prev) => [...prev, { role: "user", content: text }]);
    setBusy(true);
    try {
      const r = await axios.post(`${API}/itsm/chat`, { message: text }, { withCredentials: true });
      const reply = r.data.reply;
      const ticket = r.data.ticket;
      let content = reply;
      if (ticket) {
        content += `\n\nTicket: ${ticket.ticket_number} — ${ticket.title} (${ticket.status})`;
        if (ticket.servicenow_synced) content += ` — synced to ServiceNow`;
        mutate((key) => typeof key === "string" && key.startsWith(`${API}/tickets`));
      }
      setMsgs((prev) => [...prev, { role: "assistant", content }]);
    } catch (e) {
      setMsgs((prev) => [...prev, { role: "assistant", content: `Error: ${e.response?.data?.detail || e.message}` }]);
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-[400px] bg-white border-l border-slate-200 shadow-2xl flex flex-col">
      <div className="flex items-center justify-between px-4 h-14 border-b border-slate-200 bg-indigo-600 text-white">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          <span className="font-semibold text-[14px]">ITSM Assistant</span>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-indigo-500 rounded-lg transition"><X className="h-5 w-5" /></button>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed ${
              m.role === "user" ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-800"
            }`}>
              {m.content.split('\n').map((line, j) => <p key={j}>{line}</p>)}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="bg-slate-100 rounded-2xl px-3.5 py-2.5 text-[13px] text-slate-500 flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Thinking...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="border-t border-slate-200 p-3">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask me to create a ticket…"
            disabled={busy}
            className="flex-1 h-10 px-3.5 rounded-lg bg-slate-50 border border-slate-200 text-[13px] outline-none focus:border-indigo-300 focus:bg-white focus:ring-4 focus:ring-indigo-100/60 transition disabled:opacity-50"
          />
          <button onClick={send} disabled={!input.trim() || busy} className="h-10 w-10 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white grid place-items-center disabled:opacity-50 transition">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}

function TicketsList() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const { data } = useTickets({ q, status: statusFilter });

  const items = data?.items || [];

  return (
    <Layout>
      <div className="pt-6 space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="h-12 w-12 rounded-xl bg-violet-50 ring-4 ring-violet-100 grid place-items-center text-violet-600">
              <Inbox className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-[24px] font-semibold tracking-tight text-slate-900">Change Tickets</h1>
              <p className="text-[13px] text-slate-500 mt-0.5">ITSM-style audit trail for every provisioning, modification and deletion request.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setChatOpen(true)}
              className="h-10 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-[13px] font-semibold inline-flex items-center gap-1.5"
            >
              <Bot className="h-4 w-4" /> ITSM Chat
            </button>
            <button
              data-testid="tickets-create-btn"
              onClick={() => setCreateOpen(true)}
              className="h-10 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[13px] font-semibold inline-flex items-center gap-1.5"
            >
              <Plus className="h-4 w-4" /> Create ticket
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-4 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[260px]">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by ticket #, name, or module…"
              data-testid="tickets-search"
              className="w-full h-10 rounded-lg bg-slate-50 border border-slate-200 pl-10 pr-3 text-[13px] outline-none focus:border-indigo-300 focus:bg-white focus:ring-4 focus:ring-indigo-100/60 transition"
            />
          </div>
          <div className="inline-flex items-center gap-1.5 text-[12px]">
            <Filter className="h-3.5 w-3.5 text-slate-400" />
            <span className="text-slate-500 font-medium">Status</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-9 px-2.5 rounded-lg bg-slate-50 border border-slate-200 text-[12.5px] font-medium text-slate-700 outline-none focus:border-indigo-300"
            >
              <option value="">All</option>
              <option value="awaiting_approval">Awaiting approval</option>
              <option value="approved">Approved</option>
              <option value="deploying">Deploying</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
        </div>

        {/* Ticket cards */}
        {items.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200/80 p-12 text-center">
            <Inbox className="h-10 w-10 mx-auto text-slate-300" />
            <p className="mt-3 text-[13px] font-medium text-slate-600">No tickets match your filter</p>
            <p className="text-[11.5px] text-slate-400 mt-0.5">Tickets are created automatically whenever the provisioning agent generates a plan.</p>
          </div>
        ) : (
          <div className="bg-white rounded-2xl border border-slate-200/80 overflow-hidden">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="bg-slate-50/70 text-[10.5px] font-semibold tracking-[0.14em] uppercase text-slate-500">
                  <th className="text-left px-5 py-3">Ticket</th>
                  <th className="text-left px-3 py-3">Resource</th>
                  <th className="text-left px-3 py-3">Module</th>
                  <th className="text-left px-3 py-3">Region</th>
                  <th className="text-left px-3 py-3">Requested By</th>
                  <th className="text-left px-3 py-3">Est. Cost</th>
                  <th className="text-left px-5 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((t) => {
                  const st = statusStyle[t.status] || statusStyle.awaiting_approval;
                  const StIcon = st.icon;
                  return (
                    <tr key={t.id} data-testid={`ticket-row-${t.id}`} onClick={() => nav(`/tickets/${t.id}`)} className="hover:bg-slate-50/50 cursor-pointer">
                      <td className="px-5 py-3 font-mono text-[12px] text-slate-700">{t.ticket_number}</td>
                      <td className="px-3 py-3 font-semibold text-slate-900">{t.deployment_name || t.title || t.resource_ref || "—"}</td>
                      <td className="px-3 py-3 text-slate-600">{t.terraform_module || t.module_key || t.category || "manual"}</td>
                      <td className="px-3 py-3 text-slate-600">{t.region || t.location || "—"}</td>
                      <td className="px-3 py-3 text-slate-600">{t.requested_by || t.assignee_email || "—"}</td>
                      <td className="px-3 py-3 font-semibold text-slate-800">{t.estimated_cost != null ? formatMoney(t.estimated_cost, t.currency) : "—"}</td>
                      <td className="px-5 py-3">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full border text-[11px] font-semibold ${st.bg}`}>
                          <StIcon className="h-3 w-3" />
                          {st.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {createOpen && <CreateTicketModal onClose={() => setCreateOpen(false)} onCreated={(t) => { setCreateOpen(false); toast.success(`Ticket ${t.ticket_number} created`); mutate((key) => typeof key === "string" && key.startsWith(`${API}/tickets`)); }} />}
      {chatOpen && <ITSMChatPanel onClose={() => setChatOpen(false)} />}
    </Layout>
  );
}

function CreateTicketModal({ onClose, onCreated }) {
  const [f, setF] = useState({ title: "", description: "", priority: "P3", category: "general", resource_ref: "", assignee_email: "" });
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const submit = async () => {
    if (!f.title.trim()) return;
    setBusy(true);
    try {
      const r = await axios.post(`${API}/itsm/tickets`, f, { withCredentials: true });
      onCreated(r.data);
    } catch (e) {
      toast.error("Failed to create ticket", { description: e.response?.data?.detail || e.message });
    } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm grid place-items-center px-6" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} data-testid="create-ticket-modal" className="bg-white rounded-2xl w-full max-w-lg p-6">
        <h3 className="text-[18px] font-semibold text-slate-900">Create ticket</h3>
        <p className="text-[12px] text-slate-500 mt-1">Manual ITSM ticket. If ServiceNow is connected in Settings, it will be forwarded automatically.</p>
        <div className="mt-4 space-y-3">
          <Field label="Title *"><input data-testid="ct-title" value={f.title} onChange={(e) => set("title", e.target.value)} placeholder="e.g. Storage account needs backup enabled" className="w-full h-10 rounded-lg border border-slate-200 px-3 text-[13px] outline-none focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100" /></Field>
          <Field label="Description"><textarea data-testid="ct-desc" value={f.description} onChange={(e) => set("description", e.target.value)} rows={4} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-[13px] outline-none focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100" /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Priority"><select data-testid="ct-priority" value={f.priority} onChange={(e) => set("priority", e.target.value)} className="w-full h-10 rounded-lg border border-slate-200 px-3 text-[13px]"><option>P1</option><option>P2</option><option>P3</option><option>P4</option></select></Field>
            <Field label="Category"><select data-testid="ct-category" value={f.category} onChange={(e) => set("category", e.target.value)} className="w-full h-10 rounded-lg border border-slate-200 px-3 text-[13px]"><option value="general">General</option><option value="provisioning">Provisioning</option><option value="incident">Incident</option><option value="request">Request</option><option value="compliance">Compliance</option></select></Field>
          </div>
          <Field label="Resource reference (optional)"><input data-testid="ct-resource" value={f.resource_ref} onChange={(e) => set("resource_ref", e.target.value)} placeholder="/subscriptions/.../resourceGroups/…" className="w-full h-10 rounded-lg border border-slate-200 px-3 text-[13px] font-mono" /></Field>
          <Field label="Assignee email (optional)"><input data-testid="ct-assignee" value={f.assignee_email} onChange={(e) => set("assignee_email", e.target.value)} placeholder="user@example.com" className="w-full h-10 rounded-lg border border-slate-200 px-3 text-[13px]" /></Field>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="h-9 px-3.5 rounded-lg text-[12.5px] font-semibold text-slate-600">Cancel</button>
          <button data-testid="ct-submit" onClick={submit} disabled={busy || !f.title.trim()} className="h-9 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[12.5px] font-semibold inline-flex items-center gap-1.5 disabled:opacity-60">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />} Create
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (<div><label className="text-[11.5px] font-medium text-slate-600">{label}</label><div className="mt-1">{children}</div></div>);
}

function TicketDetail() {
  const { ticketId } = useParams();
  const nav = useNavigate();
  const { data: ticket } = useTicket(ticketId);
  const [commentText, setCommentText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [destroying, setDestroying] = useState(false);

  const refresh = () => mutate(`${API}/tickets/${ticketId}`);

  const handleComment = async (e) => {
    e.preventDefault();
    if (!commentText.trim() || submitting) return;
    setSubmitting(true);
    try {
      await postTicketComment(ticketId, commentText.trim());
      setCommentText("");
      await refresh();
    } finally {
      setSubmitting(false);
    }
  };

  const handleDestroy = async () => {
    if (!window.confirm(`Destroy "${ticket?.deployment_name}"? This will delete real Azure resources. You will be asked to approve the destroy plan before it runs.`)) return;
    setDestroying(true);
    try {
      const res = await startDestroy(ticketId);
      nav(`/provisioning/session/${res.session_id}`);
    } catch (ex) {
      alert(`Destroy failed: ${ex.response?.data?.detail || ex.message}`);
      setDestroying(false);
    }
  };

  if (!ticket) {
    return (
      <Layout>
        <div className="pt-10 text-center text-[13px] text-slate-400">Loading ticket…</div>
      </Layout>
    );
  }

  const st = statusStyle[ticket.status] || statusStyle.awaiting_approval;
  const StIcon = st.icon;

  return (
    <Layout>
      <div className="pt-6 space-y-6">
        <button onClick={() => nav("/tickets")} className="text-[12px] font-semibold text-slate-600 hover:text-slate-900">← Back to tickets</button>

        {/* Header */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-[11px] font-mono uppercase tracking-[0.14em] text-slate-400">{ticket.ticket_number}</div>
              <h1 className="text-[22px] font-semibold tracking-tight text-slate-900 mt-1">{ticket.deployment_name}</h1>
              <p className="text-[12.5px] text-slate-500 mt-0.5">
                Action: <span className="font-semibold text-slate-700 capitalize">{ticket.action}</span> •
                Module: <span className="font-mono">{ticket.terraform_module}</span> •
                Region: <span className="font-semibold">{ticket.region || "—"}</span>
              </p>
            </div>
            <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-[12px] font-semibold ${st.bg}`}>
              <StIcon className={`h-3.5 w-3.5 ${ticket.status === "deploying" ? "animate-spin" : ""}`} />
              {st.label}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5">
            <Stat label="Requested by" value={ticket.requested_by} />
            <Stat label="Approver" value={ticket.approver || "—"} />
            <Stat label="Estimated cost" value={formatMoney(ticket.estimated_cost, ticket.currency)} />
            <Stat label="Created" value={new Date(ticket.created_at).toLocaleString()} />
          </div>

          {/* Actions bar — destroy is only visible for completed create tickets */}
          {ticket.status === "completed" && ticket.action === "create" && (
            <div className="mt-5 pt-4 border-t border-slate-100 flex items-center justify-between">
              <div className="text-[12.5px] text-slate-600">
                Deployment is live in Azure. You can destroy it below — the agent will run <span className="font-mono">terraform plan -destroy</span> and ask for your approval before deleting anything.
              </div>
              <button
                onClick={handleDestroy}
                disabled={destroying}
                data-testid="ticket-destroy-btn"
                className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-[12.5px] font-semibold transition disabled:opacity-60"
              >
                {destroying ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                Destroy Resource
              </button>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Timeline + comments */}
          <div className="xl:col-span-2 space-y-6">
            <div className="bg-white rounded-2xl border border-slate-200/80 p-5">
              <h3 className="text-[13px] font-semibold text-slate-900">Timeline</h3>
              <ol className="mt-4 relative border-l border-slate-200 pl-5 space-y-4">
                {(ticket.timeline || []).map((ev, i) => (
                  <li key={i} className="relative">
                    <span className="absolute -left-[26px] top-1 h-3 w-3 rounded-full bg-indigo-500 ring-4 ring-indigo-100" />
                    <div className="flex items-center gap-2">
                      <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${timelineTone[ev.status] || timelineTone.neutral}`}>
                        {ev.label}
                      </span>
                      <span className="text-[11px] text-slate-400">{new Date(ev.at).toLocaleString()}</span>
                    </div>
                    {ev.detail && <p className="text-[12px] text-slate-600 mt-1">{ev.detail}</p>}
                  </li>
                ))}
                {(ticket.timeline || []).length === 0 && (
                  <li className="text-[12px] text-slate-400">No timeline events yet.</li>
                )}
              </ol>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200/80 p-5">
              <h3 className="text-[13px] font-semibold text-slate-900 flex items-center gap-1.5">
                <MessageSquare className="h-3.5 w-3.5 text-slate-400" /> Comments
              </h3>
              <div className="mt-3 space-y-2">
                {(ticket.comments || []).length === 0 ? (
                  <p className="text-[12px] text-slate-400 italic">No comments yet. Add the first one below.</p>
                ) : (
                  (ticket.comments || []).map((c) => (
                    <div key={c.id} className="bg-slate-50 border border-slate-100 rounded-lg p-3">
                      <div className="flex items-center justify-between">
                        <div className="text-[12.5px] font-semibold text-slate-800">{c.author}</div>
                        <div className="text-[10.5px] text-slate-400">{new Date(c.at).toLocaleString()}</div>
                      </div>
                      <p className="text-[12.5px] text-slate-600 mt-1 whitespace-pre-wrap">{c.text}</p>
                    </div>
                  ))
                )}
              </div>
              <form onSubmit={handleComment} className="mt-3 flex gap-2">
                <input
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  placeholder="Write a comment…"
                  data-testid="ticket-comment-input"
                  className="flex-1 h-10 px-3.5 rounded-lg bg-slate-50 border border-slate-200 outline-none text-[13px] focus:border-indigo-300 focus:bg-white focus:ring-4 focus:ring-indigo-100/60 transition"
                />
                <button type="submit" disabled={!commentText.trim() || submitting} className="h-10 px-4 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-[12.5px] font-semibold inline-flex items-center gap-1.5 disabled:opacity-50 transition">
                  {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Post
                </button>
              </form>
            </div>
          </div>

          {/* Right — tfvars + outputs */}
          <aside className="xl:col-span-1 space-y-6">
            <div className="bg-white rounded-2xl border border-slate-200/80 p-5">
              <h3 className="text-[13px] font-semibold text-slate-900 flex items-center gap-1.5">
                <Server className="h-3.5 w-3.5 text-indigo-500" /> Terraform Variables
              </h3>
              <div className="mt-3 space-y-1.5">
                {Object.entries(ticket.tfvars || {}).map(([k, v]) => (
                  <div key={k} className="flex items-start justify-between gap-3 text-[12px]">
                    <span className="font-mono text-slate-500">{k}</span>
                    <span className="font-semibold text-slate-800 text-right break-all">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200/80 p-5">
              <h3 className="text-[13px] font-semibold text-slate-900 flex items-center gap-1.5">
                <FileText className="h-3.5 w-3.5 text-indigo-500" /> Outputs
              </h3>
              {Object.keys(ticket.outputs || {}).length === 0 ? (
                <p className="text-[12px] text-slate-400 italic mt-2">No outputs yet — outputs appear after a successful apply.</p>
              ) : (
                <div className="mt-3 space-y-1.5">
                  {Object.entries(ticket.outputs).map(([k, v]) => (
                    <div key={k} className="flex items-start justify-between gap-3 text-[12px]">
                      <span className="font-mono text-slate-500">{k}</span>
                      <span className="font-semibold text-slate-800 text-right break-all">{String(v)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {(ticket.logs || []).length > 0 && (
              <div className="bg-slate-950 rounded-2xl border border-slate-200/80 p-4 font-mono text-[11px] text-slate-100 max-h-64 overflow-y-auto">
                <div className="text-[10px] uppercase tracking-[0.14em] text-slate-400 mb-2">terraform apply logs</div>
                {ticket.logs.map((l, i) => (
                  <div key={i} className="whitespace-pre-wrap">{l}</div>
                ))}
              </div>
            )}
          </aside>
        </div>
      </div>
    </Layout>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <div className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</div>
      <div className="text-[13px] font-semibold text-slate-800 mt-0.5">{value}</div>
    </div>
  );
}

export default function Tickets() {
  const { ticketId } = useParams();
  return ticketId ? <TicketDetail /> : <TicketsList />;
}
