import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { canAccess } from "@/lib/access";
import useAuthStore from "@/store/auth";

interface Props {
  permission: string;
  legacyRoles?: string[];
  children: ReactNode;
}

export default function PermissionGuard({ permission, legacyRoles = [], children }: Props) {
  const user = useAuthStore((state) => state.user);
  return canAccess(user, legacyRoles, permission)
    ? <>{children}</>
    : <Navigate to="/403" replace />;
}
