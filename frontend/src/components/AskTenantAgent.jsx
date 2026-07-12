import React, { useState, useRef, useEffect } from "react";
import axios from "axios";
import { Send, Loader2, Bot, User, Sparkles } from "lucide-react";
import { API } from "@/context/AuthContext";
import { stripMarkdown } from "@/lib/markdown";

/**
 * Reusable "Ask the X Agent" chat panel powered by /api/tenant/chat (function-calling bridge).
 * Every agent page (Optimization, Troubleshoot, Compliance, Assessment, Reports, Support, Dashboard)
 * uses this so we have one consistent experience across the portal.
 */
export default function AskTenantAgent({
  title = "Ask the Agent",
  placeholder = "Ask anything about your tenant…",
  hint = "",
  suggestedPrompts = [],
  testIdPrefix = "ask-agent",
}) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages.length, busy]);

  const send = async (msg) => {
    const m = (msg ?? text).trim();
    if (!m || busy) return;
    setText("");
    const next = [...messages, { role: "user", content: m }];
    setMessages(next);
    setBusy(true);
    try {
      const res = await axios.post(`${API}/tenant/chat`, { messages: next, hint }, { withCredentials: true });
      setMessages([...next, { role: "assistant", content: res.data.reply || "…", tools: res.data.tool_traces }]);
    } catch (e) {
      setMessages([...next, { role: "assistant", content: `Error: ${e.response?.data?.detail || e.message}`, error: true }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid={testIdPrefix} className="bg-white rounded-2xl border border-slate-200/80 flex flex-col h-[520px]">
      <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-2">
        <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-500 grid place-items-center text-white">
          <Sparkles className="h-3.5 w-3.5" />
        </div>
        <div className="text-[13.5px] font-semibold text-slate-900">{title}</div>
        <div className="ml-auto text-[10.5px] text-slate-400">Connected to your Azure tenant</div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50/40">
        {messages.length === 0 && (
          <div>
            <div className="text-[12px] text-slate-400 italic mb-3">Try one of these:</div>
            <div className="flex flex-wrap gap-2">
              {suggestedPrompts.map((p, i) => (
                <button
                  key={i}
                  onClick={() => send(p)}
                  data-testid={`${testIdPrefix}-suggested-${i}`}
                  className="text-[11.5px] px-3 py-1.5 rounded-full bg-white border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 text-slate-700 transition"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-2.5 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
            <div className={`h-7 w-7 rounded-full grid place-items-center shrink-0 ${m.role === "user" ? "bg-gradient-to-br from-indigo-500 to-violet-500" : "bg-slate-900"} text-white`}>
              {m.role === "user" ? <User className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
            </div>
            <div className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-[12.5px] leading-relaxed whitespace-pre-wrap ${
              m.role === "user"
                ? "bg-indigo-600 text-white rounded-tr-sm"
                : m.error
                ? "bg-rose-50 text-rose-700 border border-rose-200 rounded-tl-sm"
                : "bg-white text-slate-800 border border-slate-200/80 rounded-tl-sm"
            }`}>
              {stripMarkdown(m.content)}
              {m.tools && m.tools.length > 0 && (
                <div className="mt-2 pt-2 border-t border-slate-100 text-[10.5px] text-slate-500 flex flex-wrap gap-1">
                  {m.tools.map((t, j) => (
                    <span key={j} className="px-1.5 py-0.5 rounded bg-slate-100 font-mono">→ {t.tool}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex gap-2.5">
            <div className="h-7 w-7 rounded-full bg-slate-900 grid place-items-center text-white">
              <Bot className="h-3.5 w-3.5" />
            </div>
            <div className="bg-white border border-slate-200/80 rounded-2xl rounded-tl-sm px-3.5 py-2 text-[12.5px] text-slate-500 inline-flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Querying your tenant…
            </div>
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); send(); }}
        className="border-t border-slate-100 p-2.5 flex gap-2"
      >
        <input
          data-testid={`${testIdPrefix}-input`}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={placeholder}
          disabled={busy}
          className="flex-1 h-10 px-3.5 rounded-xl bg-slate-50 border border-slate-200 outline-none text-[13px] focus:border-indigo-300 focus:bg-white transition disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={!text.trim() || busy}
          data-testid={`${testIdPrefix}-send`}
          className="h-10 px-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-[12.5px] font-semibold inline-flex items-center gap-1.5 disabled:opacity-40 transition"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
        </button>
      </form>
    </div>
  );
}
