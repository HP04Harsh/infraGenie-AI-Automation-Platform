import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { API } from "@/context/AuthContext";

export function useTenantSummary(refreshKey = 0) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const load = useCallback(async (fresh = false) => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/tenant/summary${fresh ? "?fresh=true" : ""}`, { withCredentials: true });
      setData(r.data);
      setError(null);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(false); }, [load, refreshKey]);
  return { data, loading, error, refresh: () => load(true) };
}
