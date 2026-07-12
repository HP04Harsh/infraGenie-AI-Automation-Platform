import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth, formatApiError } from "@/context/AuthContext";
import { Sparkles, Mail, Lock, Loader2, Eye, EyeOff, User as UserIcon } from "lucide-react";

export default function Login() {
  const nav = useNavigate();
  const location = useLocation();
  const { login, register, user } = useAuth();

  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [email, setEmail] = useState("guest@infragenie.io");
  const [password, setPassword] = useState("Guest@321");
  const [name, setName] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  React.useEffect(() => {
    if (user && user !== false) {
      nav(user.onboarding_complete ? "/dashboard" : "/onboarding", { replace: true });
    }
  }, [user, nav]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const u = mode === "login" ? await login(email, password) : await register(email, password, name);
      const redirect = location.state?.from?.pathname;
      if (!u.onboarding_complete) nav("/onboarding", { replace: true });
      else nav(redirect || "/dashboard", { replace: true });
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const isSignup = mode === "signup";

  return (
    <div
      data-testid="login-page"
      className="min-h-screen flex"
      style={{ fontFamily: '"Plus Jakarta Sans", "Manrope", system-ui, sans-serif' }}
    >
      {/* Left: dark purple gradient brand panel */}
      <div className="hidden lg:flex w-1/2 relative overflow-hidden text-white" style={{ background: "#0B0F19" }}>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_25%_20%,rgba(99,102,241,0.55),transparent_45%),radial-gradient(circle_at_75%_75%,rgba(168,85,247,0.4),transparent_50%),radial-gradient(circle_at_50%_50%,rgba(217,70,239,0.18),transparent_60%)]" />
        <div className="absolute inset-0 opacity-[0.08]" style={{ backgroundImage: "linear-gradient(rgba(255,255,255,0.5) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.5) 1px,transparent 1px)", backgroundSize: "60px 60px" }} />
        <div className="relative p-12 flex flex-col justify-between w-full z-10">
          <div className="flex items-center gap-2.5">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 grid place-items-center shadow-[0_10px_28px_-8px_rgba(99,102,241,0.7)]">
              <Sparkles className="h-5 w-5 text-white" strokeWidth={2.4} />
            </div>
            <div className="text-[22px] font-semibold tracking-tight">
              Infra<span className="text-indigo-400">Genie</span>
            </div>
          </div>

          <div>
            <div className="inline-block text-[11px] font-semibold uppercase tracking-[0.18em] text-indigo-300/90 bg-indigo-500/10 border border-indigo-400/20 px-2.5 py-1 rounded-full">
              AI Cloud Operations for Azure
            </div>
            <h2 className="mt-5 text-[40px] font-semibold tracking-tight leading-[1.06]">
              Your AI ops team
              <br />
              for every Azure tenant.
            </h2>
            <p className="mt-5 text-[14.5px] text-slate-300 max-w-md leading-relaxed">
              Provisioning, observability, FinOps, ITSM, and compliance — all run by autonomous agents
              that read your tenant in real-time.
            </p>
            <ul className="mt-8 space-y-2.5 text-[13px] text-slate-300">
              {["Connect your Azure tenant in 60 seconds", "Live cost, security and resource metrics", "Agents that act, not just dashboards"].map((t) => (
                <li key={t} className="flex items-center gap-2.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
                  {t}
                </li>
              ))}
            </ul>
          </div>

          <div className="text-[11px] text-slate-500">© InfraGenie {new Date().getFullYear()}</div>
        </div>
      </div>

      {/* Right: form on white */}
      <div className="flex-1 grid place-items-center px-6 py-12 bg-white">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 grid place-items-center">
              <Sparkles className="h-4 w-4 text-white" />
            </div>
            <div className="text-[18px] font-semibold tracking-tight">
              Infra<span className="text-indigo-500">Genie</span>
            </div>
          </div>

          <h1 className="text-[28px] font-semibold tracking-tight text-slate-900">
            {isSignup ? "Create your account" : "Welcome back"}
          </h1>
          <p className="mt-1.5 text-[13.5px] text-slate-500">
            {isSignup
              ? "Spin up an InfraGenie workspace in under a minute."
              : "Sign in to continue to your InfraGenie workspace."}
          </p>

          <form data-testid="login-form" onSubmit={onSubmit} className="mt-8 space-y-4">
            {isSignup && (
              <Field label="Full name" icon={UserIcon}>
                <input
                  data-testid="register-name-input"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Doe"
                  required
                  className="login-input"
                />
              </Field>
            )}

            <Field label="Email" icon={Mail}>
              <input
                data-testid="login-email-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                className="login-input"
              />
            </Field>

            <Field label="Password" icon={Lock}>
              <input
                data-testid="login-password-input"
                type={showPw ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={6}
                className="login-input pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPw((s) => !s)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 z-20"
                aria-label="Toggle password visibility"
              >
                {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </Field>

            {error && (
              <div
                data-testid="login-error"
                className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[12.5px] text-rose-700"
              >
                {error}
              </div>
            )}

            <button
              data-testid="login-submit-button"
              type="submit"
              disabled={loading}
              className="w-full h-11 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-[13.5px] font-semibold flex items-center justify-center gap-2 disabled:opacity-60 transition shadow-[0_12px_28px_-12px_rgba(99,102,241,0.7)]"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {isSignup ? "Creating account…" : "Signing in…"}
                </>
              ) : isSignup ? (
                "Create account"
              ) : (
                "Sign in"
              )}
            </button>

            <div className="text-center text-[12.5px] text-slate-500 pt-2">
              {isSignup ? "Already have an account?" : "Don't have an account?"}{" "}
              <button
                data-testid="toggle-auth-mode"
                type="button"
                onClick={() => {
                  setMode(isSignup ? "login" : "signup");
                  setError(null);
                }}
                className="font-semibold text-indigo-600 hover:text-indigo-700"
              >
                {isSignup ? "Sign in" : "Sign up"}
              </button>
            </div>

            {!isSignup && (
              <div className="text-center text-[11px] text-slate-400 pt-2">
                Demo: <span className="font-mono text-slate-600">guest@infragenie.io / Guest@321</span>
              </div>
            )}
          </form>
        </div>
      </div>

      <style>{`
        .login-input {
          width: 100%;
          height: 44px;
          border-radius: 12px;
          border: 1px solid rgb(226 232 240);
          padding-left: 38px;
          padding-right: 12px;
          font-size: 13.5px;
          outline: none;
          background: #fff;
          transition: all .15s;
        }
        .login-input:focus {
          border-color: rgb(165 180 252);
          box-shadow: 0 0 0 4px rgb(224 231 255 / .6);
        }
      `}</style>
    </div>
  );
}

function Field({ label, icon: Icon, children }) {
  return (
    <div>
      <label className="text-[12px] font-medium text-slate-600">{label}</label>
      <div className="relative mt-1.5">
        {Icon && <Icon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 z-10" />}
        {children}
      </div>
    </div>
  );
}
