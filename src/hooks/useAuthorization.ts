import useAuthStore from "@/store/auth";
import { AccessAction, canAccess, canPerform, isSuperuser } from "@/lib/access";

export default function useAuthorization() {
  const user = useAuthStore((state) => state.user);
  return {
    isSuperuser: () => isSuperuser(user),
    canAccess: (roles?: string[]) => canAccess(user, roles),
    canPerform: (action: AccessAction, roles: string[], available = true) => canPerform(user, action, roles, available),
  };
}
