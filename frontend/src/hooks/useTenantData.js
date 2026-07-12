import axios from "axios";
import useSWR, { mutate as globalMutate } from "swr";
import { useEffect, useRef } from "react";
import { API } from "@/context/AuthContext";

const fetcher = (url) => axios.get(url).then((r) => r.data);

export function useMetrics() {
  return useSWR(`${API}/metrics`, fetcher, {
    refreshInterval: 30000,
    revalidateOnFocus: false,
  });
}

export function useActivity(limit = 6, important = false) {
  const qs = `limit=${limit}${important ? "&important=true" : ""}`;
  return useSWR(`${API}/activity?${qs}`, fetcher, {
    refreshInterval: 15000,
    revalidateOnFocus: false,
  });
}

export function useNotifications() {
  return useSWR(`${API}/notifications`, fetcher, {
    refreshInterval: 20000,
    revalidateOnFocus: false,
  });
}

/**
 * useNotificationsWS — real-time WebSocket subscription for notifications.
 * Falls back silently if WS fails; REST polling in useNotifications keeps working.
 * On any incoming push, triggers SWR revalidation of the notifications endpoint.
 */
export function useNotificationsWS(onMessage) {
  const wsRef = useRef(null);
  useEffect(() => {
    if (!API) return;
    // Derive ws:// or wss:// from the API base URL
    let wsUrl;
    try {
      const u = new URL(API);
      const proto = u.protocol === "https:" ? "wss:" : "ws:";
      wsUrl = `${proto}//${u.host}/api/ws/notifications`;
    } catch {
      return;
    }
    let closed = false;
    let reconnectTimer = null;

    function connect() {
      if (closed) return;
      let ws;
      try {
        ws = new WebSocket(wsUrl);
      } catch {
        reconnectTimer = setTimeout(connect, 5000);
        return;
      }
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          // Revalidate SWR cache so the bell + activity update immediately
          globalMutate(`${API}/notifications`);
          globalMutate((key) => typeof key === "string" && key.startsWith(`${API}/activity`), undefined, { revalidate: true });
          if (data?.type === "notification" && onMessage) onMessage(data);
        } catch {
          /* ignore */
        }
      };
      ws.onclose = () => {
        if (!closed) reconnectTimer = setTimeout(connect, 5000);
      };
      ws.onerror = () => {
        try { ws.close(); } catch { /* noop */ }
      };
    }
    connect();
    return () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (wsRef.current) {
        try { wsRef.current.close(); } catch { /* noop */ }
      }
    };
  }, []);
}

export function useSettings() {
  return useSWR(`${API}/settings`, fetcher, { revalidateOnFocus: false });
}

export async function sendAssistMessage(message, threadId) {
  const { data } = await axios.post(`${API}/assist/chat`, {
    message,
    thread_id: threadId ?? null,
  });
  return data;
}

export async function patchSettings(payload) {
  const { data } = await axios.patch(`${API}/settings`, payload);
  return data;
}

export async function connectIntegration(key, fields) {
  const { data } = await axios.post(`${API}/settings/integrations/connect`, { key, fields });
  return data;
}

export async function disconnectIntegration(key) {
  const { data } = await axios.post(`${API}/settings/integrations/disconnect`, { key, fields: {} });
  return data;
}
