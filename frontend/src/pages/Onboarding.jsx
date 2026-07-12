import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import {
  Sparkles, Building2, Cloud, Brain, Rocket, CheckCircle2, Loader2,
  AlertCircle, ArrowRight, Server, Cpu, Layers, ShieldCheck,
} from "lucide-react";
import { useAuth, API, formatApiError } from "@/context/AuthContext";

const stepMeta = [
  { n: 1, label: "Company", icon: Building2 },
  { n: 2, label: "Azure Tenant", icon: Cloud },
  { n: 3, label: "AI Config", icon: Brain },
  { n: 4, label: "Sync & Extract", icon: Rocket },
  { n: 5, label: "Done", icon: CheckCircle2 },
];

const extractionPhases = [
  { key: "auth", label: "Authentication", desc: "Service principal → Azure AD" },
  { key: "resources", label: "Resource Discovery", desc: "Subscriptions • RGs • resources" },
  { key: "cost", label: "Cost Management", desc: "Month-to-date spend" },
  { key: "security", label: "Security", desc: "Defender for Cloud score" },
  { key: "ai", label: "AI Init", desc: "Smart Assist agent" },
];

export default function Onboarding() {
  const nav = useNavigate();
  const { user, refreshUser } = useAuth();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    company: { company_name: "", industry: "", company_size: "", website: "" },
    azure_tenant: { tenant_id: "", client_id: "", client_secret: "", subscription_id: "" },
    azure_ai: { project_endpoint: "", api_key: "", agent_name: "OpsBot", model_name: "gpt-4o", provider: "azure_openai" },
  });
  const [extractStatus, setExtractStatus] = useState({}); // {phaseKey: "pending"|"running"|"ok"|"error"}
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const logEndRef = useRef(null);

  useEffect(() => {
    if (user === false) nav("/login", { replace: true });
    if (user && user.onboarding_complete) nav("/dashboard", { replace: true });
  }, [user, nav]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const setSec = (section, key, val) =>
    setForm((f) => ({ ...f, [section]: { ...f[section], [key]: val } }));

  const validStep1 = form.company.company_name.trim().length > 1;
  const validStep2 =
    form.azure_tenant.tenant_id.trim().length > 4 &&
    form.azure_tenant.client_id.trim().length > 4 &&
    form.azure_tenant.client_secret.trim().length > 0 &&
    form.azure_tenant.subscription_id.trim().length > 4;
  const validStep3 =
    form.azure_ai.project_endpoint.trim().length > 6 &&
    form.azure_ai.api_key.trim().length > 4 &&
    form.azure_ai.agent_name.trim().length > 0 &&
    form.azure_ai.model_name.trim().length > 0;

  const goNext = () => setStep((s) => Math.min(5, s + 1));
  const goBack = () => setStep((s) => Math.max(1, s - 1));

  const runExtraction = async () => {
    setExtracting(true);
    setSubmitError(null);
    const initial = Object.fromEntries(extractionPhases.map((p) => [p.key, "pending"]));
    setExtractStatus(initial);
    setLogs([{ ts: new Date(), level: "info", text: "▶ Starting Azure tenant extraction…" }]);

    // Visual: mark each phase as "running" with a small stagger so the bars animate
    extractionPhases.forEach((p, idx) => {
      setTimeout(() => {
        setExtractStatus((s) => ({ ...s, [p.key]: "running" }));
        setLogs((l) => [...l, { ts: new Date(), level: "info", text: `→ ${p.label}: ${p.desc}` }]);
      }, idx * 350);
    });

    try {
      const { data } = await axios.post(`${API}/onboarding/submit`, form);
      // Merge backend logs into UI
      const backendLogs = (data.logs || []).map((lg) => ({
        ts: new Date(lg.at),
        level: lg.status === "error" ? "error" : lg.status === "ok" ? "ok" : "info",
        text: `[${lg.phase}] ${lg.message}`,
      }));
      setLogs((prev) => [...prev, ...backendLogs]);

      // Determine per-phase ok/error
      const phases = data.metrics?.phases || {};
      const newStatus = {};
      for (const p of extractionPhases) {
        const ph = phases[p.key];
        if (!ph) newStatus[p.key] = "error";
        else newStatus[p.key] = ph.ok ? "ok" : "error";
      }
      setExtractStatus(newStatus);
      setStats(data.stats);
      setLogs((l) => [
        ...l,
        { ts: new Date(), level: "ok", text: `✔ Extraction finished. Resources=${data.stats.resources}, VMs=${data.stats.vms}, RGs=${data.stats.resource_groups}, SecScore=${data.stats.security_score}.` },
      ]);
    } catch (err) {
      const msg = formatApiError(err.response?.data?.detail) || err.message;
      setSubmitError(msg);
      setLogs((l) => [...l, { ts: new Date(), level: "error", text: `✖ ${msg}` }]);
      const errStatus = Object.fromEntries(extractionPhases.map((p) => [p.key, "error"]));
      setExtractStatus(errStatus);
    } finally {
      setExtracting(false);
      // advance to step 5 regardless — show errors gracefully
      setTimeout(() => setStep(5), 600);
    }
  };

  return (
    <div
      data-testid="onboarding-page"
      className="min-h-screen bg-[#F4F4FB] px-6 py-10"
      style={{ fontFamily: '"Plus Jakarta Sans", "Manrope", system-ui, sans-serif' }}
    >
      <div className="max-w-3xl mx-auto">
        {/* Brand */}
        <div className="flex items-center gap-2 mb-7 justify-center">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 grid place-items-center shadow-[0_10px_28px_-8px_rgba(99,102,241,0.7)]">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <div className="text-[20px] font-semibold tracking-tight">
            Infra<span className="text-indigo-500">Genie</span>
          </div>
        </div>

        {/* Stepper */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-3 mb-6">
          <div className="flex items-center justify-between">
            {stepMeta.map((s, idx) => {
              const Icon = s.icon;
              const active = step === s.n;
              const done = step > s.n;
              return (
                <React.Fragment key={s.n}>
                  <div
                    data-testid={`step-indicator-${s.n}`}
                    className={`flex items-center gap-2 px-2.5 py-2 rounded-lg transition ${
                      active ? "bg-indigo-50" : ""
                    }`}
                  >
                    <div
                      className={`h-8 w-8 rounded-full grid place-items-center text-[12px] font-semibold ${
                        done
                          ? "bg-emerald-500 text-white"
                          : active
                          ? "bg-indigo-600 text-white"
                          : "bg-slate-100 text-slate-400"
                      }`}
                    >
                      {done ? <CheckCircle2 className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                    </div>
                    <div className="hidden md:block">
                      <div
                        className={`text-[11.5px] font-semibold ${
                          active ? "text-indigo-700" : done ? "text-emerald-600" : "text-slate-400"
                        }`}
                      >
                        Step {s.n}
                      </div>
                      <div className={`text-[11px] ${active ? "text-slate-900" : "text-slate-500"}`}>
                        {s.label}
                      </div>
                    </div>
                  </div>
                  {idx < stepMeta.length - 1 && (
                    <div className={`flex-1 h-0.5 mx-1 ${step > s.n ? "bg-emerald-400" : "bg-slate-200"}`} />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Step body */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-7 shadow-[0_24px_60px_-30px_rgba(15,23,42,0.18)]">
          {step === 1 && (
            <StepCompany form={form} setSec={setSec} />
          )}
          {step === 2 && (
            <StepAzure form={form} setSec={setSec} />
          )}
          {step === 3 && (
            <StepAi form={form} setSec={setSec} />
          )}
          {step === 4 && (
            <StepExtract
              extractStatus={extractStatus}
              logs={logs}
              extracting={extracting}
              onStart={runExtraction}
              logEndRef={logEndRef}
              submitError={submitError}
            />
          )}
          {step === 5 && <StepDone stats={stats} userName={user?.name?.split(" ")?.[0] || "there"} nav={nav} refreshUser={refreshUser} />}

          {/* Footer nav */}
          {step <= 4 && (
            <div className="mt-7 flex items-center justify-between">
              <button
                data-testid="onboarding-back-button"
                onClick={goBack}
                disabled={step === 1 || extracting}
                className="h-10 px-4 rounded-xl text-[13px] font-semibold text-slate-600 hover:text-slate-900 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                Back
              </button>

              {step < 4 ? (
                <button
                  data-testid="onboarding-next-button"
                  onClick={goNext}
                  disabled={
                    (step === 1 && !validStep1) ||
                    (step === 2 && !validStep2) ||
                    (step === 3 && !validStep3)
                  }
                  className="h-10 px-5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-[13px] font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition shadow-[0_12px_28px_-12px_rgba(99,102,241,0.7)] flex items-center gap-2"
                >
                  Continue
                  <ArrowRight className="h-4 w-4" />
                </button>
              ) : (
                <button
                  data-testid="onboarding-extract-button"
                  onClick={runExtraction}
                  disabled={extracting}
                  className="h-10 px-5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-[13px] font-semibold disabled:opacity-60 transition shadow-[0_12px_28px_-12px_rgba(99,102,241,0.7)] flex items-center gap-2"
                >
                  {extracting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Extracting…
                    </>
                  ) : (
                    <>
                      Start extraction
                      <Rocket className="h-4 w-4" />
                    </>
                  )}
                </button>
              )}
            </div>
          )}
        </div>

        <style>{`
          .onb-input {
            width: 100%;
            height: 42px;
            border-radius: 12px;
            border: 1px solid rgb(226 232 240);
            padding: 0 12px;
            font-size: 13.5px;
            outline: none;
            background: #fff;
            transition: all .15s;
          }
          .onb-input.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px; }
          .onb-input:focus { border-color: rgb(165 180 252); box-shadow: 0 0 0 4px rgb(224 231 255 / .6); }
        `}</style>
      </div>
    </div>
  );
}

// ---------- Steps ----------
function StepCompany({ form, setSec }) {
  return (
    <div>
      <h2 className="text-[22px] font-semibold tracking-tight text-slate-900">Tell us about your company</h2>
      <p className="mt-1 text-[13px] text-slate-500">This shapes how InfraGenie surfaces cost and resource metrics.</p>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Company name *">
          <input
            data-testid="onboarding-company-name"
            value={form.company.company_name}
            onChange={(e) => setSec("company", "company_name", e.target.value)}
            placeholder="Acme Cloud Inc."
            className="onb-input"
          />
        </Field>
        <Field label="Industry">
          <select
            value={form.company.industry}
            onChange={(e) => setSec("company", "industry", e.target.value)}
            className="onb-input"
          >
            <option value="">Select industry</option>
            {["Technology", "Finance", "Healthcare", "Retail", "Manufacturing", "Other"].map((i) => (
              <option key={i}>{i}</option>
            ))}
          </select>
        </Field>
        <Field label="Company size">
          <select
            value={form.company.company_size}
            onChange={(e) => setSec("company", "company_size", e.target.value)}
            className="onb-input"
          >
            <option value="">Select size</option>
            {["1–10", "11–50", "51–200", "201–500", "501–1000", "1000+"].map((s) => <option key={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Website">
          <input
            value={form.company.website}
            onChange={(e) => setSec("company", "website", e.target.value)}
            placeholder="https://acme.com"
            className="onb-input"
          />
        </Field>
      </div>
    </div>
  );
}

function StepAzure({ form, setSec }) {
  return (
    <div>
      <h2 className="text-[22px] font-semibold tracking-tight text-slate-900">Connect your Azure tenant</h2>
      <p className="mt-1 text-[13px] text-slate-500">
        Provide a service principal so we can read resource, cost and security data.
      </p>

      <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-[12px] text-amber-800 flex gap-2">
        <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
        <div>
          <span className="font-semibold">Service Principal needs Reader + Cost Management Reader</span> at subscription scope.
        </div>
      </div>

      <div className="mt-5 space-y-4">
        <Field label="Tenant ID *">
          <input
            data-testid="onboarding-tenant-id"
            value={form.azure_tenant.tenant_id}
            onChange={(e) => setSec("azure_tenant", "tenant_id", e.target.value)}
            placeholder="00000000-0000-0000-0000-000000000000"
            className="onb-input mono"
          />
        </Field>
        <Field label="Client (Application) ID *">
          <input
            data-testid="onboarding-client-id"
            value={form.azure_tenant.client_id}
            onChange={(e) => setSec("azure_tenant", "client_id", e.target.value)}
            placeholder="00000000-0000-0000-0000-000000000000"
            className="onb-input mono"
          />
        </Field>
        <Field label="Client Secret *">
          <input
            data-testid="onboarding-client-secret"
            type="password"
            value={form.azure_tenant.client_secret}
            onChange={(e) => setSec("azure_tenant", "client_secret", e.target.value)}
            placeholder="••••••••••••••••••••••••••"
            className="onb-input mono"
          />
        </Field>
        <Field label="Subscription ID *">
          <input
            data-testid="onboarding-subscription-id"
            value={form.azure_tenant.subscription_id}
            onChange={(e) => setSec("azure_tenant", "subscription_id", e.target.value)}
            placeholder="00000000-0000-0000-0000-000000000000"
            className="onb-input mono"
          />
        </Field>
      </div>
    </div>
  );
}

function StepAi({ form, setSec }) {
  return (
    <div>
      <h2 className="text-[22px] font-semibold tracking-tight text-slate-900">Configure Azure OpenAI</h2>
      <p className="mt-1 text-[13px] text-slate-500">Powers Smart Assist, the Provisioning Agent, and every conversational agent in the portal. You can switch to Azure Foundry later from Settings.</p>
      <div className="mt-6 space-y-4">
        <Field label="Azure OpenAI endpoint *">
          <input
            data-testid="onboarding-ai-endpoint"
            value={form.azure_ai.project_endpoint}
            onChange={(e) => setSec("azure_ai", "project_endpoint", e.target.value)}
            placeholder="https://<account>.openai.azure.com/openai/v1"
            className="onb-input mono"
          />
        </Field>
        <Field label="API key *">
          <input
            data-testid="onboarding-ai-key"
            type="password"
            value={form.azure_ai.api_key}
            onChange={(e) => setSec("azure_ai", "api_key", e.target.value)}
            placeholder="••••••••••••••••"
            className="onb-input mono"
          />
        </Field>
        <Field label="Deployment name *">
          <input
            data-testid="onboarding-ai-model"
            value={form.azure_ai.model_name}
            onChange={(e) => setSec("azure_ai", "model_name", e.target.value)}
            placeholder="gpt-4o"
            className="onb-input mono"
          />
        </Field>
      </div>
    </div>
  );
}

function StepExtract({ extractStatus, logs, extracting, onStart, logEndRef, submitError }) {
  const phases = extractionPhases;
  return (
    <div>
      <h2 className="text-[22px] font-semibold tracking-tight text-slate-900">Syncing your Azure tenant</h2>
      <p className="mt-1 text-[13px] text-slate-500">
        Five phases run in parallel. Errors are shown gracefully — your account will still be set up.
      </p>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-5 gap-3">
        {phases.map((p) => {
          const st = extractStatus[p.key] || "pending";
          return (
            <div
              key={p.key}
              data-testid={`phase-${p.key}`}
              className={`rounded-xl border p-3.5 ${
                st === "ok"
                  ? "border-emerald-200 bg-emerald-50"
                  : st === "error"
                  ? "border-rose-200 bg-rose-50"
                  : st === "running"
                  ? "border-indigo-200 bg-indigo-50"
                  : "border-slate-200 bg-white"
              }`}
            >
              <div className="flex items-center gap-2">
                {st === "ok" ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                ) : st === "error" ? (
                  <AlertCircle className="h-4 w-4 text-rose-600" />
                ) : st === "running" ? (
                  <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />
                ) : (
                  <div className="h-4 w-4 rounded-full border border-slate-300" />
                )}
                <span className="text-[12px] font-semibold text-slate-900">{p.label}</span>
              </div>
              <div className="mt-2 h-1.5 rounded-full bg-white overflow-hidden border border-slate-200/80">
                <div
                  className={`h-full transition-all duration-700 ${
                    st === "ok"
                      ? "w-full bg-emerald-500"
                      : st === "error"
                      ? "w-full bg-rose-500"
                      : st === "running"
                      ? "w-2/3 bg-indigo-500 animate-pulse"
                      : "w-0"
                  }`}
                />
              </div>
              <div className="mt-1.5 text-[10.5px] text-slate-500">{p.desc}</div>
            </div>
          );
        })}
      </div>

      {/* Terminal log */}
      <div
        data-testid="extract-log"
        className="mt-6 rounded-xl bg-[#0B0F19] text-slate-200 font-mono text-[11.5px] p-4 h-56 overflow-y-auto border border-slate-800"
      >
        {logs.length === 0 ? (
          <div className="text-slate-500">
            <span className="text-emerald-400">$</span> waiting for extraction to start…
          </div>
        ) : (
          logs.map((l, i) => (
            <div key={i} className="leading-relaxed">
              <span className="text-slate-500">
                [{l.ts.toLocaleTimeString("en-US", { hour12: false })}]
              </span>{" "}
              <span
                className={
                  l.level === "error"
                    ? "text-rose-400"
                    : l.level === "ok"
                    ? "text-emerald-400"
                    : "text-slate-200"
                }
              >
                {l.text}
              </span>
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>

      {!extracting && logs.length === 0 && (
        <div className="mt-4 text-[12.5px] text-slate-500">
          Click <span className="font-semibold">Start extraction</span> below to begin.
        </div>
      )}

      {submitError && (
        <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[12.5px] text-rose-700">
          {submitError}
        </div>
      )}
    </div>
  );
}

function StepDone({ stats, userName, nav, refreshUser }) {
  const [going, setGoing] = React.useState(false);
  const statCards = [
    { label: "Resources", value: stats?.resources ?? 0, icon: Layers, accent: "indigo" },
    { label: "Virtual Machines", value: stats?.vms ?? 0, icon: Cpu, accent: "violet" },
    { label: "Resource Groups", value: stats?.resource_groups ?? 0, icon: Server, accent: "sky" },
    { label: "Security Score", value: `${stats?.security_score ?? 0}`, icon: ShieldCheck, accent: "emerald" },
  ];
  const accentBg = {
    indigo: "bg-indigo-50 text-indigo-600",
    violet: "bg-violet-50 text-violet-600",
    sky: "bg-sky-50 text-sky-600",
    emerald: "bg-emerald-50 text-emerald-600",
  };
  const goDashboard = async () => {
    setGoing(true);
    try {
      await refreshUser?.();
    } catch (_e) {}
    nav("/dashboard", { replace: true });
  };
  return (
    <div className="text-center">
      <div className="mx-auto h-14 w-14 rounded-full bg-emerald-100 grid place-items-center">
        <CheckCircle2 className="h-7 w-7 text-emerald-600" />
      </div>
      <h2 className="mt-4 text-[26px] font-semibold tracking-tight text-slate-900">
        You're all set, {userName}!
      </h2>
      <p className="mt-1.5 text-[13.5px] text-slate-500">
        Here's what we just pulled from your Azure tenant.
      </p>

      <div className="mt-7 grid grid-cols-2 md:grid-cols-4 gap-4 text-left">
        {statCards.map((c) => {
          const Icon = c.icon;
          return (
            <div key={c.label} data-testid={`done-stat-${c.label.toLowerCase().replace(/ /g, "-")}`} className="rounded-xl border border-slate-200/80 p-4 bg-white">
              <div className={`h-9 w-9 rounded-lg grid place-items-center ${accentBg[c.accent]}`}>
                <Icon className="h-4 w-4" />
              </div>
              <div className="mt-3 text-[24px] font-semibold tracking-tight text-slate-900 leading-none">
                {c.value}
              </div>
              <div className="text-[11.5px] text-slate-500 mt-1.5">{c.label}</div>
            </div>
          );
        })}
      </div>

      <button
        data-testid="onboarding-go-dashboard"
        onClick={goDashboard}
        disabled={going}
        className="mt-8 h-11 px-6 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-[13.5px] font-semibold inline-flex items-center gap-2 transition shadow-[0_12px_28px_-12px_rgba(99,102,241,0.7)] disabled:opacity-60"
      >
        {going ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        Go to Dashboard
        <ArrowRight className="h-4 w-4" />
      </button>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="text-[12px] font-medium text-slate-600">{label}</label>
      <div className="mt-1.5">{children}</div>
    </div>
  );
}
