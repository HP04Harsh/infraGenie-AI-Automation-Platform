import React, { useState, useEffect } from "react";
import Layout from "@/components/Layout";
import axios from "axios";
import { useSettings, patchSettings, connectIntegration, disconnectIntegration } from "@/hooks/useTenantData";
import { saveAiConfig } from "@/hooks/useProvisioning";
import { API, useAuth } from "@/context/AuthContext";
import { Loader2, Plug, CheckCircle2, XCircle, Save, RotateCcw, Users, Trash2, UserPlus, Brain } from "lucide-react";
import { toast } from "sonner";

export default function Settings() {
  const { data, mutate } = useSettings();
  const { user } = useAuth();
  const [portalName, setPortalName] = useState("");
  const [primaryColor, setPrimaryColor] = useState("");
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [modal, setModal] = useState(null);

  React.useEffect(() => {
    if (data) {
      setPortalName(data.portal_name);
      setPrimaryColor(data.primary_color);
    }
  }, [data]);

  const save = async () => {
    setSaving(true);
    try {
      await patchSettings({ portal_name: portalName, primary_color: primaryColor });
      await mutate();
      toast.success("Settings saved — theme applied");
    } catch (e) {
      toast.error("Failed to save", { description: e.message });
    } finally { setSaving(false); }
  };

  const resetTheme = async () => {
    setResetting(true);
    try {
      await axios.post(`${API}/settings/reset-theme`, {}, { withCredentials: true });
      await mutate();
      toast.success("Theme reset to InfraGenie default");
    } catch (e) { toast.error(e.message); }
    finally { setResetting(false); }
  };

  return (
    <Layout>
      <div className="pt-8 max-w-4xl">
        <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Settings</h1>
        <p className="mt-1 text-[13px] text-slate-500">Configure your InfraGenie SaaS portal.</p>

        {!data ? (
          <div className="mt-10 flex items-center gap-2 text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading…
          </div>
        ) : (
          <>
            {/* Portal */}
            <section className="mt-7 bg-white rounded-2xl border border-slate-200/80 p-6">
              <h2 className="text-[15.5px] font-semibold text-slate-900">Portal branding</h2>
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-[12px] font-medium text-slate-600">Portal name</label>
                  <input
                    data-testid="settings-portal-name"
                    value={portalName}
                    onChange={(e) => setPortalName(e.target.value)}
                    className="mt-1.5 w-full h-11 rounded-xl border border-slate-200 px-3 text-[13.5px] outline-none focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100"
                  />
                </div>
                <div>
                  <label className="text-[12px] font-medium text-slate-600">Primary color</label>
                  <div className="mt-1.5 flex items-center gap-3">
                    <input
                      data-testid="settings-primary-color"
                      type="color"
                      value={primaryColor}
                      onChange={(e) => setPrimaryColor(e.target.value)}
                      className="h-11 w-14 rounded-lg border border-slate-200 cursor-pointer"
                    />
                    <span className="text-[12.5px] text-slate-600 font-mono">{primaryColor}</span>
                  </div>
                </div>
              </div>
              <div className="mt-5 flex gap-2">
                <button
                  data-testid="settings-save"
                  onClick={save}
                  disabled={saving}
                  className="h-10 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-[13px] font-semibold inline-flex items-center gap-2 disabled:opacity-60 transition"
                >
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Save changes
                </button>
                <button
                  data-testid="settings-reset-theme"
                  onClick={resetTheme}
                  disabled={resetting}
                  className="h-10 px-4 rounded-xl bg-white border border-slate-200 hover:bg-slate-50 text-[13px] font-semibold text-slate-700 inline-flex items-center gap-2 disabled:opacity-60"
                >
                  {resetting ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                  Reset to default
                </button>
              </div>
            </section>

            {/* AI Provider */}
            <section className="mt-6 bg-white rounded-2xl border border-slate-200/80 p-6">
              <h2 className="text-[15.5px] font-semibold text-slate-900 inline-flex items-center gap-2">
                <Brain className="h-4 w-4 text-indigo-500" /> AI Provider
              </h2>
              <p className="mt-1 text-[12.5px] text-slate-500">
                {data.ai_configured
                  ? `Using ${data.ai_config?.provider || "azure_openai"} — ${data.ai_config?.endpoint}`
                  : "Not configured — AI-driven features will be unavailable."}
              </p>
              <AiConfigForm initial={data.ai_config || {}} onSaved={() => mutate()} />
            </section>

            {/* User management (admin only) */}
            {user?.role === "admin" && <UserManagement />}

            {/* Integrations */}
            <section className="mt-6 bg-white rounded-2xl border border-slate-200/80 p-6">
              <h2 className="text-[15.5px] font-semibold text-slate-900">Integrations</h2>
              <p className="mt-1 text-[12.5px] text-slate-500">
                A green dot means the service is connected and synced.
              </p>
              <ul className="mt-4 divide-y divide-slate-100">
                {data.integrations.map((i) => (
                  <li
                    key={i.key}
                    data-testid={`integration-${i.key}`}
                    className="flex items-center justify-between py-4"
                  >
                    <div className="flex items-center gap-3">
                      <span
                        data-testid={`integration-${i.key}-dot`}
                        className={`h-2.5 w-2.5 rounded-full ${i.connected ? "bg-emerald-500" : "bg-rose-500"} ring-4 ${i.connected ? "ring-emerald-100" : "ring-rose-100"}`}
                      />
                      <div>
                        <div className="text-[13.5px] font-semibold text-slate-900">{i.name}</div>
                        <div className="text-[11.5px] text-slate-500">{i.config_hint}</div>
                      </div>
                    </div>
                    {i.connected ? (
                      <button
                        data-testid={`integration-${i.key}-disconnect`}
                        onClick={async () => {
                          await disconnectIntegration(i.key);
                          mutate();
                          toast.success(`${i.name} disconnected`);
                        }}
                        className="h-9 px-3.5 rounded-lg border border-slate-200 text-[12.5px] font-semibold text-slate-700 hover:border-slate-300"
                      >
                        Disconnect
                      </button>
                    ) : (
                      <button
                        data-testid={`integration-${i.key}-connect`}
                        onClick={() => setModal(i)}
                        className="h-9 px-3.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[12.5px] font-semibold inline-flex items-center gap-1.5"
                      >
                        <Plug className="h-3.5 w-3.5" /> Connect
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </div>

      {modal && (
        <ConnectModal
          integration={modal}
          onClose={() => setModal(null)}
          onConnected={() => {
            mutate();
            setModal(null);
            toast.success(`${modal.name} connected`);
          }}
        />
      )}
    </Layout>
  );
}

function ConnectModal({ integration, onClose, onConnected }) {
  const [fields, setFields] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const set = (k, v) => setFields((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await connectIntegration(integration.key, fields);
      onConnected();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm grid place-items-center px-6" onClick={onClose}>
      <div
        data-testid={`connect-modal-${integration.key}`}
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-2xl w-full max-w-md p-6 shadow-[0_24px_60px_-30px_rgba(15,23,42,0.4)]"
      >
        <h3 className="text-[18px] font-semibold text-slate-900">Connect {integration.name}</h3>
        <p className="text-[12.5px] text-slate-500 mt-1">{integration.config_hint}</p>

        <div className="mt-4 space-y-3">
          {integration.fields.map((f) => (
            <div key={f.key}>
              <label className="text-[12px] font-medium text-slate-600">{f.label}</label>
              <input
                data-testid={`connect-${integration.key}-${f.key}`}
                type={f.type === "password" ? "password" : "text"}
                placeholder={f.placeholder}
                value={fields[f.key] || ""}
                onChange={(e) => set(f.key, e.target.value)}
                className="mt-1.5 w-full h-10 rounded-xl border border-slate-200 px-3 text-[13px] outline-none focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100"
              />
            </div>
          ))}
          {error && <div className="text-[12px] text-rose-600">{String(error)}</div>}
        </div>

        <div className="mt-6 flex items-center justify-end gap-2">
          <button onClick={onClose} className="h-9 px-3.5 rounded-lg text-[12.5px] font-semibold text-slate-600 hover:text-slate-900">Cancel</button>
          <button
            data-testid={`connect-${integration.key}-submit`}
            onClick={submit}
            disabled={busy}
            className="h-9 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[12.5px] font-semibold inline-flex items-center gap-1.5 disabled:opacity-60"
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
            Connect
          </button>
        </div>
      </div>
    </div>
  );
}


function AiConfigForm({ initial, onSaved }) {
  const [endpoint, setEndpoint] = useState(initial.endpoint || "");
  const [deployment, setDeployment] = useState(initial.deployment || "");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);

  React.useEffect(() => {
    setEndpoint(initial.endpoint || "");
    setDeployment(initial.deployment || "");
  }, [initial.endpoint, initial.deployment]);

  const submit = async () => {
    if (!endpoint || !deployment) { toast.error("Endpoint and deployment are required"); return; }
    setBusy(true);
    try {
      const payload = { provider: "azure_openai", endpoint, deployment };
      if (apiKey) payload.api_key = apiKey;
      await saveAiConfig(payload);
      setApiKey("");
      toast.success("AI provider updated");
      onSaved();
    } catch (e) { toast.error(e.response?.data?.detail || e.message); }
    finally { setBusy(false); }
  };

  return (
    <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
      <div>
        <label className="text-[12px] font-medium text-slate-600">Azure OpenAI endpoint</label>
        <input
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
          placeholder="https://your-resource.openai.azure.com"
          className="mt-1.5 w-full h-10 rounded-xl border border-slate-200 px-3 text-[13px] outline-none focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100"
        />
      </div>
      <div>
        <label className="text-[12px] font-medium text-slate-600">Deployment name</label>
        <input
          value={deployment}
          onChange={(e) => setDeployment(e.target.value)}
          placeholder="gpt-4o"
          className="mt-1.5 w-full h-10 rounded-xl border border-slate-200 px-3 text-[13px] outline-none focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100"
        />
      </div>
      <div>
        <label className="text-[12px] font-medium text-slate-600">API key {initial.endpoint ? "(leave blank to keep current)" : ""}</label>
        <div className="mt-1.5 flex gap-2">
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={initial.endpoint ? "unchanged" : "sk-..."}
            className="flex-1 h-10 rounded-xl border border-slate-200 px-3 text-[13px] outline-none focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100"
          />
          <button
            onClick={submit}
            disabled={busy}
            className="h-10 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-[13px] font-semibold inline-flex items-center gap-2 disabled:opacity-60 transition shrink-0"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

function UserManagement() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ email: "", name: "", password: "", role: "user" });
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/users`, { withCredentials: true });
      setUsers(r.data.users || []);
    } catch (e) { toast.error("Failed to load users", { description: e.response?.data?.detail || e.message }); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/users`, form, { withCredentials: true });
      toast.success(`User ${form.email} created`);
      setForm({ email: "", name: "", password: "", role: "user" });
      setShowForm(false);
      await load();
    } catch (e) { toast.error(e.response?.data?.detail || e.message); }
    finally { setBusy(false); }
  };

  const del = async (uid, email) => {
    if (!window.confirm(`Delete user ${email}?`)) return;
    try {
      await axios.delete(`${API}/users/${uid}`, { withCredentials: true });
      toast.success("User deleted");
      await load();
    } catch (e) { toast.error(e.response?.data?.detail || e.message); }
  };

  return (
    <section className="mt-6 bg-white rounded-2xl border border-slate-200/80 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-[15.5px] font-semibold text-slate-900 inline-flex items-center gap-2"><Users className="h-4 w-4 text-indigo-500" /> User management</h2>
        <button data-testid="user-add-btn" onClick={() => setShowForm((s) => !s)} className="h-9 px-3.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[12.5px] font-semibold inline-flex items-center gap-1.5">
          <UserPlus className="h-3.5 w-3.5" /> New user
        </button>
      </div>

      {showForm && (
        <div className="mt-4 p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <input data-testid="user-email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="Email" className="h-10 rounded-lg border border-slate-200 px-3 text-[13px]" />
            <input data-testid="user-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Full name" className="h-10 rounded-lg border border-slate-200 px-3 text-[13px]" />
            <input data-testid="user-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="Password (min 6)" type="password" className="h-10 rounded-lg border border-slate-200 px-3 text-[13px]" />
            <select data-testid="user-role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className="h-10 rounded-lg border border-slate-200 px-3 text-[13px]">
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <button data-testid="user-create-submit" onClick={create} disabled={busy || !form.email || !form.password} className="h-9 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-[12.5px] font-semibold inline-flex items-center gap-1.5 disabled:opacity-60">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />} Create
          </button>
        </div>
      )}

      {loading ? <div className="mt-4 text-slate-400 text-[12px] inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
      : (
        <ul className="mt-4 divide-y divide-slate-100">
          {users.map((u) => (
            <li key={u.id} data-testid={`user-${u.id}`} className="flex items-center justify-between py-3">
              <div>
                <div className="text-[13px] font-semibold text-slate-900">{u.name} <span className="text-[11px] font-normal text-slate-500 ml-1">({u.email})</span></div>
                <div className="text-[11px] text-slate-500 mt-0.5">Role: <span className={`px-1.5 py-0.5 rounded text-[10.5px] font-mono ${u.role === "admin" ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-700"}`}>{u.role}</span></div>
              </div>
              <button data-testid={`user-delete-${u.id}`} onClick={() => del(u.id, u.email)} className="h-8 w-8 rounded-lg hover:bg-rose-50 text-rose-500 grid place-items-center">
                <Trash2 className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
