import useAuthStore from "@/store/auth";
import { AccessAction, canAccess, canPerform, hasPermission, isSuperuser } from "@/lib/access";

export default function useAuthorization() {
  const user = useAuthStore((state) => state.user);
  return {
    isSuperuser: () => isSuperuser(user),
    hasPermission: (permission: string) => hasPermission(user, permission),
    canAccess: (roles?: string[], permission?: string) => canAccess(user, roles, permission),
    canPerform: (
      action: AccessAction,
      roles: string[],
      available = true,
      permission?: string,
    ) => canPerform(user, action, roles, available, permission),
  };
}
