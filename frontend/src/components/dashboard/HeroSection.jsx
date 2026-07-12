import React, { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { Send, Mic, MicOff, Sparkles, Server, TrendingDown, ShieldCheck, GitMerge, Loader2, Bot, X } from "lucide-react";
import { API } from "@/context/AuthContext";
import { stripMarkdown } from "@/lib/markdown";

const suggestions = [
  { label: "Provision a VM in Azure", icon: Server, testId: "suggest-provision-vm" },
  { label: "Show cost optimization opportunities", icon: TrendingDown, testId: "suggest-cost-opt" },
  { label: "Check resource health", icon: ShieldCheck, testId: "suggest-health" },
  { label: "Create a change request", icon: GitMerge, testId: "suggest-change-req" },
];

// Web Speech API — Chrome / Edge (Safari has partial support). Feature-detect gracefully.
const SpeechRecognition =
  typeof window !== "undefined"
    ? (window.SpeechRecognition || window.webkitSpeechRecognition)
    : null;

export default function HeroSection({ greeting = "Good morning", userName = "there" }) {
  const [value, setValue] = useState("");
  const [listening, setListening] = useState(false);
  const [micError, setMicError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState(null);
  const [replyTools, setReplyTools] = useState([]);
  const inputRef = useRef(null);
  const recogRef = useRef(null);
  const baseValueRef = useRef("");

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const submit = async (text) => {
    const msg = (text ?? value).trim();
    if (!msg || busy) return;
    setBusy(true); setReply(null);
    try {
      // If user asks to create a change request/ticket, forward to ITSM create endpoint
      if (/change\s*request|create\s*ticket|open\s*ticket/i.test(msg)) {
        const r = await axios.post(`${API}/itsm/tickets`, {
          title: msg.slice(0, 120),
          description: `Created via Smart Assist: ${msg}`,
          priority: "P3", category: "request",
        }, { withCredentials: true });
        setReply(`✓ Ticket ${r.data.ticket_number} created for: "${msg}". View it in the ITSM Agent.`);
      } else {
        const r = await axios.post(`${API}/tenant/chat`, { messages: [{ role: "user", content: msg }] }, { withCredentials: true, timeout: 90000 });
        setReply(r.data.reply || "…");
        setReplyTools(r.data.tool_traces || []);
      }
    } catch (e) {
      setReply(`Error: ${e.response?.data?.detail || e.message}`);
    } finally { setBusy(false); }
  };

  const populateAndStay = (text) => {
    setValue(text);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const stopListening = useCallback(() => {
    try { recogRef.current?.stop(); } catch { /* noop */ }
    setListening(false);
  }, []);

  const startListening = useCallback(() => {
    setMicError("");
    if (!SpeechRecognition) {
      setMicError("Voice input isn't supported in this browser. Try Chrome or Edge.");
      return;
    }
    // Toggle off if already listening
    if (listening) {
      stopListening();
      return;
    }
    const recog = new SpeechRecognition();
    recog.lang = navigator.language || "en-US";
    recog.continuous = false;
    recog.interimResults = true;
    recog.maxAlternatives = 1;
    baseValueRef.current = value ? `${value} ` : "";

    recog.onresult = (event) => {
      let interim = "";
      let final = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        if (r.isFinal) final += r[0].transcript;
        else interim += r[0].transcript;
      }
      setValue(`${baseValueRef.current}${final}${interim}`.trimStart());
    };
    recog.onerror = (e) => {
      const code = e?.error || "unknown";
      const msg = code === "not-allowed" || code === "service-not-allowed"
        ? "Microphone permission denied. Allow it in the browser to use voice input."
        : code === "no-speech"
          ? "I didn't hear anything. Tap the mic and try again."
          : `Voice input error: ${code}`;
      setMicError(msg);
      setListening(false);
    };
    recog.onend = () => {
      setListening(false);
    };

    try {
      recog.start();
      recogRef.current = recog;
      setListening(true);
      setTimeout(() => inputRef.current?.focus(), 0);
    } catch (err) {
      setMicError(`Couldn't start voice input: ${err?.message || err}`);
    }
  }, [listening, stopListening, value]);

  useEffect(() => {
    return () => { try { recogRef.current?.stop(); } catch { /* noop */ } };
  }, []);

  return (
    <section data-testid="hero-section" className="text-center max-w-3xl mx-auto">
      <h1
        data-testid="hero-greeting"
        className="text-[36px] sm:text-[42px] lg:text-[48px] font-semibold tracking-tight text-slate-900 leading-[1.08]"
      >
        {greeting}, <span className="text-slate-900">{userName}</span>{" "}
        <span className="inline-block animate-wave origin-[70%_70%]">👋</span>
      </h1>
      <p className="mt-3 text-[14.5px] text-slate-500">
        How can I help you build, manage and optimize your infrastructure today?
      </p>

      <div className="mt-5 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-indigo-200/70 shadow-[0_2px_10px_-4px_rgba(99,102,241,0.25)]">
        <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
        <span className="text-[11.5px] font-semibold text-indigo-600 tracking-wide">Smart Assist</span>
      </div>

      <form
        data-testid="hero-chat-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (listening) stopListening();
          submit();
        }}
        className="mt-5 mx-auto max-w-2xl"
      >
        <div className={`group relative flex items-center gap-2 bg-white rounded-2xl border px-4 py-2.5 shadow-[0_4px_30px_-12px_rgba(15,23,42,0.12)] transition ${
          listening
            ? "border-rose-300 ring-4 ring-rose-100/60"
            : "border-slate-200/90 focus-within:border-indigo-300 focus-within:ring-4 focus-within:ring-indigo-100/60"
        }`}>
          <button
            type="button"
            data-testid="hero-mic"
            onClick={startListening}
            className={`relative h-9 w-9 grid place-items-center rounded-full transition ${
              listening
                ? "text-rose-600 bg-rose-50"
                : "text-slate-400 hover:text-indigo-500 hover:bg-indigo-50"
            }`}
            aria-label={listening ? "Stop voice input" : "Start voice input"}
            title={listening ? "Listening… click to stop" : "Voice input"}
          >
            {listening ? <MicOff className="h-[17px] w-[17px]" /> : <Mic className="h-[17px] w-[17px]" />}
            {listening && (
              <span className="absolute inset-0 rounded-full bg-rose-500/25 animate-ping" />
            )}
          </button>
          <input
            ref={inputRef}
            data-testid="hero-chat-input"
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={listening ? "Listening…" : "Ask anything about your infrastructure..."}
            className="flex-1 bg-transparent outline-none text-[14px] text-slate-800 placeholder:text-slate-400 py-2"
          />
          <button
            type="submit"
            data-testid="hero-chat-send"
            disabled={!value.trim() || busy}
            className="h-10 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-[13px] font-semibold flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed transition shadow-[0_10px_24px_-12px_rgba(99,102,241,0.7)]"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} {busy ? "…" : "Send"}
          </button>
        </div>
        {micError && (
          <div data-testid="hero-mic-error" className="mt-2 text-[11.5px] text-rose-600 font-medium">
            {micError}
          </div>
        )}
      </form>

      {(busy || reply) && (
        <div data-testid="hero-reply-panel" className="mt-4 mx-auto max-w-2xl bg-white rounded-2xl border border-slate-200/80 p-4 text-left">
          {busy ? (
            <div className="flex items-center gap-2 text-[13px] text-slate-500"><Loader2 className="h-4 w-4 animate-spin" /> Smart Assist is querying your tenant…</div>
          ) : (
            <div>
              <div className="flex items-start gap-2">
                <div className="h-7 w-7 rounded-full bg-slate-900 grid place-items-center text-white shrink-0"><Bot className="h-3.5 w-3.5" /></div>
                <div className="text-[13px] text-slate-800 whitespace-pre-wrap flex-1">{stripMarkdown(reply)}</div>
                <button onClick={() => setReply(null)} className="text-slate-400 hover:text-slate-700"><X className="h-4 w-4" /></button>
              </div>
              {replyTools && replyTools.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1 pl-9">
                  {replyTools.map((t, i) => (
                    <span key={i} className="text-[10.5px] px-1.5 py-0.5 rounded bg-slate-100 font-mono text-slate-600">→ {t.tool}</span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div data-testid="hero-suggestions" className="mt-5 flex flex-wrap items-center justify-center gap-2">
        {suggestions.map((s) => {
          const Icon = s.icon;
          return (
            <button
              key={s.label}
              data-testid={s.testId}
              onClick={() => populateAndStay(s.label)}
              className="group inline-flex items-center gap-2 h-9 px-3.5 rounded-full bg-white border border-slate-200/80 text-[12.5px] font-medium text-slate-700 hover:border-indigo-300 hover:text-indigo-600 hover:shadow-[0_8px_20px_-12px_rgba(99,102,241,0.5)] transition"
            >
              <Icon className="h-3.5 w-3.5 text-indigo-500" />
              {s.label}
            </button>
          );
        })}
      </div>

      <style>{`
        @keyframes wave {
          0%,100% { transform: rotate(0); }
          15% { transform: rotate(14deg); }
          30% { transform: rotate(-8deg); }
          45% { transform: rotate(14deg); }
          60% { transform: rotate(-4deg); }
          75% { transform: rotate(10deg); }
        }
        .animate-wave { animation: wave 2.4s ease-in-out infinite; transform-origin: 70% 70%; }
      `}</style>
    </section>
  );
}
