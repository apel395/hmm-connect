export type AccessAction = "view" | "create" | "edit" | "delete" | "submit" | "approve" | "convert" | "receive" | "post" | "cancel";

type RoleLike = string | { name?: string; code?: string };
interface UserLike { roles?: RoleLike[]; username?: string; full_name?: string }

export const SUPERUSER_ROLES = new Set([
  "ADMIN",
  "ADMINISTRATOR",
  "SYSTEM_ADMIN",
  "SYSTEM_ADMINISTRATOR",
  "SUPER_ADMIN",
  "SUPERUSER",
  "ERP_ADMIN",
  "ERP_ADMINISTRATOR",
]);

export function normalizeRoleName(name: string): string {
  return name.trim().toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function roleNames(role: RoleLike): string[] {
  if (typeof role === "string") return [normalizeRoleName(role)];
  return [role.name, role.code].filter((value): value is string => Boolean(value)).map(normalizeRoleName);
}

export function userRoleNames(user?: UserLike | null): string[] {
  return Array.from(new Set((user?.roles ?? []).flatMap(roleNames)));
}

function isAdministratorRole(role: string): boolean {
  if (SUPERUSER_ROLES.has(role)) return true;
  const parts = role.split("_");
  return parts.includes("ADMIN") || parts.includes("ADMINISTRATOR") || role.endsWith("ADMIN") || role.endsWith("ADMINISTRATOR");
}

export function isSuperuser(user?: UserLike | null): boolean {
  return userRoleNames(user).some(isAdministratorRole);
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
  if (isSuperuser(user)) return true;
  return actionAvailable && canAccess(user, allowedRoles);
}
