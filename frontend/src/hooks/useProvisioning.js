import axios from "axios";
import useSWR from "swr";
import { API } from "@/context/AuthContext";

const fetcher = (url) => axios.get(url).then((r) => r.data);

export function useCatalog() {
  return useSWR(`${API}/provisioning/catalog`, fetcher, { revalidateOnFocus: false });
}

export function useJobs(limit = 30) {
  return useSWR(`${API}/provisioning/jobs?limit=${limit}`, fetcher, {
    refreshInterval: 8000,
    revalidateOnFocus: false,
  });
}

export function useSession(sessionId) {
  return useSWR(
    sessionId ? `${API}/provisioning/sessions/${sessionId}` : null,
    fetcher,
    { refreshInterval: 0, revalidateOnFocus: false }
  );
}

export function useTickets(filters = {}) {
  const qs = new URLSearchParams(filters).toString();
  return useSWR(`${API}/tickets?${qs}`, fetcher, { refreshInterval: 12000, revalidateOnFocus: false });
}

export function useTicket(ticketId) {
  return useSWR(
    ticketId ? `${API}/tickets/${ticketId}` : null,
    fetcher,
    { refreshInterval: 5000, revalidateOnFocus: false }
  );
}

export function useTfStorage() {
  return useSWR(`${API}/settings/terraform-storage`, fetcher, { revalidateOnFocus: false });
}

export async function startSession({ prompt, module_key } = {}) {
  const { data } = await axios.post(`${API}/provisioning/sessions`, { prompt, module_key });
  return data;
}

export async function chatSession(sessionId, message) {
  const { data } = await axios.post(`${API}/provisioning/sessions/${sessionId}/chat`, { message });
  return data;
}

export async function generateSessionPlan(sessionId) {
  const { data } = await axios.post(`${API}/provisioning/sessions/${sessionId}/plan`);
  return data;
}

export async function decideSession(sessionId, decision, note = "") {
  const { data } = await axios.post(`${API}/provisioning/sessions/${sessionId}/approve`, {
    decision,
    note,
  });
  return data;
}

export async function postTicketComment(ticketId, text) {
  const { data } = await axios.post(`${API}/tickets/${ticketId}/comment`, { text });
  return data;
}

export async function saveTfStorage(payload) {
  const { data } = await axios.post(`${API}/settings/terraform-storage`, payload);
  return data;
}

export function useAiConfig() {
  return useSWR(`${API}/settings/ai-config`, fetcher, { revalidateOnFocus: false });
}

export async function saveAiConfig(payload) {
  const { data } = await axios.post(`${API}/settings/ai-config`, payload);
  return data;
}

export function useAzureCreds() {
  return useSWR(`${API}/settings/azure-credentials`, fetcher, { revalidateOnFocus: false });
}

export async function saveAzureCreds(payload) {
  const { data } = await axios.post(`${API}/settings/azure-credentials`, payload);
  return data;
}

export async function startDestroy(ticketId) {
  const { data } = await axios.post(`${API}/provisioning/destroy`, { ticket_id: ticketId });
  return data;
}
