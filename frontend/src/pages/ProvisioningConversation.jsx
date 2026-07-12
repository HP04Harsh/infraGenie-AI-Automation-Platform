import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Layout from "@/components/Layout";
import { Send, Loader2, Sparkles, CheckCircle2, XCircle, Shield, Coins, FileText, Server, ArrowRight, Bot, User, Clock, Lightbulb } from "lucide-react";
import { useSession, chatSession, generateSessionPlan, decideSession } from "@/hooks/useProvisioning";
import { mutate } from "swr";
import { API } from "@/context/AuthContext";
import { stripMarkdown } from "@/lib/markdown";

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

function MessageBubble({ msg }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`h-9 w-9 rounded-full grid place-items-center shrink-0 ${
          isUser ? "bg-gradient-to-br from-indigo-500 to-violet-500 text-white" : "bg-slate-900 text-white"
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-[13.5px] leading-relaxed whitespace-pre-wrap ${
          isUser
            ? "bg-indigo-600 text-white rounded-tr-sm"
            : "bg-white border border-slate-200/80 text-slate-800 rounded-tl-sm shadow-sm"
        }`}
      >
        {stripMarkdown(msg.content)}
      </div>
    </div>
  );
}

function CollectedVarsPanel({ moduleKey, vars }) {
  const entries = Object.entries(vars || {});
  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 p-5">
      <div className="flex items-center gap-2">
        <Server className="h-4 w-4 text-indigo-500" />
        <h3 className="text-[13px] font-semibold text-slate-900">Collected configuration</h3>
      </div>
      <p className="text-[11.5px] text-slate-400 mt-0.5">Module: <span className="font-mono text-slate-600">{moduleKey || "—"}</span></p>
      <div className="mt-3 space-y-1.5">
        {entries.length === 0 ? (
          <p className="text-[12px] text-slate-400 italic">No variables collected yet. Answer the assistant’s questions to build the configuration.</p>
        ) : (
          entries.map(([k, v]) => (
            <div key={k} className="flex items-start justify-between gap-3 text-[12px]">
              <span className="font-mono text-slate-500">{k}</span>
              <span className="font-semibold text-slate-800 text-right break-all">{String(v)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function PlanPanel({ plan, onApprove, onReject, deciding }) {
  if (!plan) return null;
  const cost = plan.cost || {};
  const sec = plan.security || {};
  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="bg-white rounded-2xl border border-slate-200/80 p-5">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-indigo-500" />
          <h3 className="text-[13px] font-semibold text-slate-900">Terraform Plan</h3>
        </div>
        <p className="mt-2 text-[12.5px] font-mono text-slate-700">{plan.summary}</p>

        <div className="mt-3 space-y-1.5">
          {(plan.actions || []).slice(0, 8).map((a, i) => {
            const tone = a.action === "create" ? "emerald" : a.action === "update" ? "amber" : "rose";
            return (
              <div key={i} className={`flex items-start gap-2 text-[12px] px-2.5 py-1.5 rounded-lg bg-${tone}-50 border border-${tone}-100`}>
                <span className={`text-${tone}-700 font-mono font-semibold uppercase text-[10px] mt-0.5`}>+ {a.action}</span>
                <div className="min-w-0">
                  <div className="font-mono text-slate-800 truncate">{a.resource_type}.{a.resource_name}</div>
                  {a.details && a.details.length > 0 && (
                    <div className="text-[11px] text-slate-500 mt-0.5">{a.details.slice(0, 3).join(" • ")}</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Cost */}
      <div className="bg-white rounded-2xl border border-slate-200/80 p-5">
        <div className="flex items-center gap-2">
          <Coins className="h-4 w-4 text-amber-500" />
          <h3 className="text-[13px] font-semibold text-slate-900">Cost Estimate</h3>
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <div className="text-[28px] font-semibold text-slate-900 tracking-tight">{formatMoney(cost.monthly_total, cost.currency)}</div>
          <div className="text-[12px] text-slate-500">/ month</div>
        </div>
        {cost.one_time ? (
          <div className="text-[11.5px] text-slate-500 mt-1">+ {formatMoney(cost.one_time, cost.currency)} one-time</div>
        ) : null}
        <div className="mt-3 space-y-1">
          {(cost.breakdown || []).map((b, i) => (
            <div key={i} className="flex justify-between text-[12px]">
              <span className="text-slate-600">{b.label}</span>
              <span className="font-semibold text-slate-800">{formatMoney(b.monthly, cost.currency)}</span>
            </div>
          ))}
        </div>
        {(cost.optimization_suggestions || []).length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-100">
            <div className="flex items-center gap-1.5 text-[11.5px] font-semibold text-indigo-600">
              <Lightbulb className="h-3 w-3" /> Optimization suggestions
            </div>
            <ul className="mt-1.5 space-y-1">
              {cost.optimization_suggestions.map((s, i) => (
                <li key={i} className="text-[11.5px] text-slate-600">• {s}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Security */}
      <div className="bg-white rounded-2xl border border-slate-200/80 p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-rose-500" />
            <h3 className="text-[13px] font-semibold text-slate-900">Security &amp; Compliance</h3>
          </div>
          <div className="text-[11.5px] font-semibold text-slate-700">
            Score: <span className={`${sec.score >= 80 ? "text-emerald-600" : sec.score >= 60 ? "text-amber-600" : "text-rose-600"}`}>{sec.score ?? "—"}/100</span>
          </div>
        </div>
        {(sec.warnings || []).length > 0 && (
          <ul className="mt-2 space-y-1">
            {sec.warnings.map((w, i) => (
              <li key={i} className="text-[11.5px] text-amber-700 bg-amber-50 border border-amber-100 rounded-md px-2.5 py-1.5">⚠ {w}</li>
            ))}
          </ul>
        )}
        {(sec.compliance || []).length > 0 && (
          <ul className="mt-2 space-y-1">
            {sec.compliance.map((c, i) => (
              <li key={i} className="text-[11.5px] text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-md px-2.5 py-1.5">✓ {c}</li>
            ))}
          </ul>
        )}
      </div>

      {/* Approval */}
      <div className="sticky bottom-0 bg-gradient-to-t from-[#F4F4FB] via-[#F4F4FB] to-transparent pt-4">
        <div className="bg-white rounded-2xl border border-slate-200/80 p-4 flex items-center justify-between gap-3">
          <div className="text-[12px] text-slate-600">
            <span className="font-semibold text-slate-900">Human approval required.</span> Review the plan above before deploying.
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onReject}
              disabled={deciding}
              data-testid="reject-btn"
              className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-[12.5px] font-semibold text-slate-700 transition disabled:opacity-50"
            >
              <XCircle className="h-4 w-4" /> Reject
            </button>
            <button
              onClick={onApprove}
              disabled={deciding}
              data-testid="approve-btn"
              className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-[12.5px] font-semibold transition shadow-[0_10px_24px_-12px_rgba(16,185,129,0.7)] disabled:opacity-50"
            >
              {deciding ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />} Approve Deployment
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function DeployingPanel({ session }) {
  const apply = session?.apply;
  const logs = apply?.logs || [];
  const status = session?.status;
  return (
    <div className="bg-slate-950 text-slate-100 rounded-2xl border border-slate-200/80 p-5 font-mono text-[11.5px] leading-relaxed max-h-[420px] overflow-y-auto">
      <div className="flex items-center gap-2 mb-3 text-[11px] uppercase tracking-[0.18em] text-slate-400">
        {status === "completed" ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400" />}
        {status === "completed" ? "Deployment complete" : "Deploying…"}
      </div>
      {logs.length === 0 ? (
        <div className="text-slate-400">Starting terraform apply…</div>
      ) : (
        logs.map((l, i) => (
          <div key={i} className="whitespace-pre-wrap">{l}</div>
        ))
      )}
      {status === "completed" && Object.keys(apply?.outputs || {}).length > 0 && (
        <div className="mt-4 pt-3 border-t border-slate-800">
          <div className="text-emerald-400 font-semibold mb-1">Outputs:</div>
          {Object.entries(apply.outputs).map(([k, v]) => (
            <div key={k}>{k} = &quot;{String(v)}&quot;</div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ProvisioningConversation() {
  const { sessionId } = useParams();
  const nav = useNavigate();
  const { data: session } = useSession(sessionId);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [planning, setPlanning] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const scrollRef = useRef(null);

  const refresh = () => mutate(`${API}/provisioning/sessions/${sessionId}`);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [session?.conversation?.length, session?.status]);

  // Poll while AI is thinking, planning, deploying, or applying
  useEffect(() => {
    const busy = ["thinking", "planning", "applying", "deploying"].includes(session?.status);
    if (busy) {
      const t = setInterval(refresh, 2000);
      return () => clearInterval(t);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.status, sessionId]);

  const sendMessage = async (e) => {
    e?.preventDefault();
    const m = text.trim();
    if (!m || sending) return;
    setText("");
    setSending(true);
    try {
      await chatSession(sessionId, m);
      await refresh();
    } finally {
      setSending(false);
    }
  };

  const handleGeneratePlan = async () => {
    setPlanning(true);
    try {
      await generateSessionPlan(sessionId);
      await refresh();
    } finally {
      setPlanning(false);
    }
  };

  const handleApprove = async () => {
    setDeciding(true);
    try {
      await decideSession(sessionId, "approve");
      await refresh();
    } finally {
      setDeciding(false);
    }
  };

  const handleReject = async () => {
    setDeciding(true);
    try {
      await decideSession(sessionId, "reject", "Cancelled by user");
      await refresh();
    } finally {
      setDeciding(false);
    }
  };

  const status = session?.status;
  const messages = session?.conversation || session?.messages || [];
  const collectedVars = session?.collected_vars || {};
  const plan = session?.plan;
  const canPlan = status === "ready" || status === "ready_for_plan";
  const isThinking = status === "thinking";
  const isPlanning = status === "planning";
  const showPlan = ["awaiting_approval", "applying", "deploying", "completed", "failed", "rejected"].includes(status);
  const showLogs = ["applying", "deploying", "completed"].includes(status);

  return (
    <Layout>
      <div className="pt-6 grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left/main — conversation */}
        <div className="xl:col-span-2 flex flex-col h-[calc(100vh-110px)]">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 grid place-items-center text-white shadow-lg shadow-indigo-200">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-[18px] font-semibold text-slate-900 leading-tight">InfraGenie Provisioning Agent</h1>
                <p className="text-[12px] text-slate-500">AI is collecting Terraform variables to deploy your resource.</p>
              </div>
            </div>
            <button
              onClick={() => nav("/agents/provisioning")}
              className="text-[12px] font-semibold text-slate-600 hover:text-slate-900"
            >
              ← Back to catalog
            </button>
          </div>

          {/* Messages */}
          <div
            ref={scrollRef}
            data-testid="conv-messages"
            className="flex-1 bg-slate-50/40 rounded-2xl border border-slate-200/60 p-4 overflow-y-auto space-y-3"
          >
            {messages.length === 0 ? (
              <div className="text-center py-12 text-[12.5px] text-slate-400">Starting session…</div>
            ) : (
              messages.map((m, i) => <MessageBubble key={i} msg={m} />)
            )}
            {isThinking && (
              <div className="flex gap-3" data-testid="conv-thinking">
                <div className="h-9 w-9 rounded-full grid place-items-center shrink-0 bg-slate-900 text-white">
                  <Bot className="h-4 w-4" />
                </div>
                <div className="bg-white border border-slate-200/80 text-slate-500 rounded-2xl rounded-tl-sm shadow-sm px-4 py-2.5 text-[13px]">
                  <span className="inline-flex items-center gap-1.5">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    InfraGenie is thinking…
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Composer + action bar */}
          <div className="mt-3 space-y-2">
            {isPlanning && (
              <div className="w-full inline-flex items-center justify-center gap-2 h-11 px-4 rounded-xl bg-indigo-50 text-indigo-700 text-[13.5px] font-semibold border border-indigo-200">
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating Terraform plan & cost estimate…
              </div>
            )}
            {canPlan && (
              <button
                onClick={handleGeneratePlan}
                disabled={planning}
                data-testid="generate-plan-btn"
                className="w-full inline-flex items-center justify-center gap-2 h-11 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-[13.5px] font-semibold transition shadow-[0_10px_24px_-12px_rgba(99,102,241,0.7)] disabled:opacity-50"
              >
                {planning ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
                {planning ? "Generating Terraform plan & cost estimate…" : "Review Plan & Cost Estimate"}
              </button>
            )}
            {!showPlan && !isPlanning && (
              <form onSubmit={sendMessage} className="flex gap-2">
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={isThinking ? "Wait for assistant…" : "Type your answer…"}
                  disabled={isThinking}
                  className="flex-1 h-11 px-4 rounded-xl bg-white border border-slate-200 outline-none text-[13.5px] focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100/60 transition disabled:opacity-60"
                  data-testid="conv-input"
                />
                <button
                  type="submit"
                  disabled={!text.trim() || sending || isThinking}
                  data-testid="conv-send"
                  className="h-11 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-[13px] font-semibold inline-flex items-center gap-1.5 disabled:opacity-50 transition"
                >
                  {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Send
                </button>
              </form>
            )}
          </div>
        </div>

        {/* Right — sidecar */}
        <aside className="xl:col-span-1 space-y-4">
          <CollectedVarsPanel moduleKey={session?.module_key} vars={collectedVars} />
          {showPlan && plan && (
            <PlanPanel
              plan={plan}
              onApprove={handleApprove}
              onReject={handleReject}
              deciding={deciding || status === "applying" || status === "deploying"}
            />
          )}
          {showLogs && <DeployingPanel session={session} />}
          {status === "completed" && (
            <button
              onClick={() => nav(`/tickets/${session.ticket_id}`)}
              className="w-full h-10 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-[13px] font-semibold transition"
            >
              View Ticket
            </button>
          )}
          {status === "rejected" && (
            <div className="bg-rose-50 border border-rose-200 rounded-2xl p-4 text-[12.5px] text-rose-700">
              <Clock className="h-4 w-4 inline mr-1" /> Deployment rejected. You can start a new request from the catalog.
            </div>
          )}
        </aside>
      </div>
    </Layout>
  );
}
