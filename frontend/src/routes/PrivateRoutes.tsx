import { Navigate, Outlet } from "react-router";
import { useAuth } from "@/contexts/AuthContext";

export default function PrivateRoutes() {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <div className="flex h-screen items-center justify-center text-slate-400">Loading…</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Outlet />;
}
