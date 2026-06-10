import { Navigate, Outlet } from "react-router";
import { useAuth } from "@/contexts/AuthContext";

/** Gate for /admin/* — non-admins are bounced to the console overview. */
export default function AdminRoute() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user?.role !== "admin") return <Navigate to="/overview" replace />;
  return <Outlet />;
}
