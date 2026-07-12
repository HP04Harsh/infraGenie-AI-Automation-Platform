import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Loader2 } from "lucide-react";

export default function ProtectedRoute({ children, requireOnboarded = false }) {
  const { user } = useAuth();
  const location = useLocation();

  if (user === null) {
    return (
      <div className="min-h-screen grid place-items-center bg-[#F4F4FB]">
        <div className="flex items-center gap-2 text-slate-500">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-[13px]">Loading…</span>
        </div>
      </div>
    );
  }
  if (user === false) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (requireOnboarded && !user.onboarding_complete) {
    return <Navigate to="/onboarding" replace />;
  }
  return children;
}
