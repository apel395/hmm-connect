import { Navigate } from "react-router-dom";
import useAuthStore from "@/store/auth";
import { isSuperuser } from "@/lib/access";

export default function PermissionGuard({ allow, children }: any) {
  const user = useAuthStore((state) => state.user);

  if (!isSuperuser(user) && !allow) {
    return <Navigate to="/403" replace />;
  }

  return children;
}