import React, { useEffect, useState, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import Layout from "@/components/Layout";
import { sendAssistMessage } from "@/hooks/useTenantData";
import { Send, Loader2, Sparkles, ArrowLeft } from "lucide-react";
import { stripMarkdown } from "@/lib/markdown";

export default function ChatScreen() {
  const [searchParams] = useSearchParams();
  const nav = useNavigate();
  const initial = searchParams.get("prompt") || "";
  const [value, setValue] = useState("");
  const [thread, setThread] = useState(null);
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const endRef = useRef(null);
  const sentInitialRef = useRef(false);

  useEffect(() => {
    if (initial && !sentInitialRef.current) {
      sentInitialRef.current = true;
      send(initial);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text) => {
    const msg = (text ?? value).trim();
    if (!msg || sending) return;
    setMessages((m) => [...m, { role: "user", content: msg }]);
    setValue("");
    setSending(true);
    try {
      const { reply, thread_id } = await sendAssistMessage(msg, thread);
      setThread(thread_id);
      setMessages((m) => [...m, { role: "assistant", content: reply }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: "Assistant unavailable. Please retry." }]);
    } finally {
      setSending(false);
    }
  };

  return (
    <Layout>
      <div data-testid="chat-page" className="pt-6 max-w-4xl mx-auto">
        <button
          onClick={() => nav("/dashboard")}
          className="text-[12.5px] font-semibold text-slate-500 hover:text-slate-900 inline-flex items-center gap-1.5"
        >
          <ArrowLeft className="h-4 w-4" /> Back to dashboard
        </button>

        <div className="mt-4 bg-white rounded-2xl border border-slate-200/80 p-6 min-h-[560px] flex flex-col">
          <div className="flex items-center gap-2 pb-4 border-b border-slate-100">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-500 grid place-items-center">
              <Sparkles className="h-4 w-4 text-white" />
            </div>
            <div>
              <div className="text-[13.5px] font-semibold text-slate-900">Smart Assist</div>
              <div className="text-[11px] text-slate-500">Mocked Azure AI Foundry agent</div>
            </div>
          </div>

          <div data-testid="chat-messages" className="flex-1 mt-4 space-y-3 overflow-y-auto">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  data-testid={`chat-msg-${m.role}-${i}`}
                  className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-[13.5px] leading-relaxed whitespace-pre-wrap ${
                    m.role === "user"
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-100 text-slate-800 border border-slate-200"
                  }`}
                >
                  {stripMarkdown(m.content)}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="rounded-2xl px-4 py-2.5 bg-slate-100 text-slate-500 text-[13px] inline-flex items-center gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Thinking…
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <form
            data-testid="chat-form"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
            className="mt-4 flex items-center gap-2"
          >
            <input
              data-testid="chat-input"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Ask anything about your infrastructure…"
              className="flex-1 h-12 rounded-xl border border-slate-200 px-4 text-[13.5px] outline-none focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100"
            />
            <button
              data-testid="chat-send"
              disabled={sending || !value.trim()}
              className="h-12 px-5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-[13px] font-semibold inline-flex items-center gap-2 disabled:opacity-60"
            >
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Send
            </button>
          </form>
        </div>
      </div>
    </Layout>
  );
}
