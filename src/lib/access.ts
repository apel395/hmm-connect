export type AccessAction = "view" | "create" | "edit" | "delete" | "submit" | "approve" | "convert" | "receive" | "post" | "cancel";

interface RoleLike { name: string }
interface UserLike { roles?: RoleLike[] }

export const SUPERUSER_ROLES = new Set(["ADMIN", "ADMINISTRATOR", "SUPER_ADMIN"]);

export function normalizeRoleName(name: string): string {
  return name.trim().toUpperCase().replace(/[\s-]+/g, "_");
}

export function userRoleNames(user?: UserLike | null): string[] {
  return (user?.roles ?? []).map((role) => normalizeRoleName(role.name));
}

export function isSuperuser(user?: UserLike | null): boolean {
  return userRoleNames(user).some((role) => SUPERUSER_ROLES.has(role));
}

export function canAccess(user: UserLike | null | undefined, allowedRoles?: string[]): boolean {
  if (isSuperuser(user)) return true;
  if (!allowedRoles?.length) return true;
  const roles = userRoleNames(user);
  return allowedRoles.some((role) => roles.includes(normalizeRoleName(role)));
}

export function canPerform(
  user: UserLike | null | undefined,
  _action: AccessAction,
  allowedRoles: string[],
  actionAvailable = true,
): boolean {
  return actionAvailable && canAccess(user, allowedRoles);
}
