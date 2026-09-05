export type AccessAction = "view" | "create" | "edit" | "delete" | "submit" | "approve" | "convert" | "receive" | "post" | "cancel" | "reopen" | "unpost";

type PermissionLike = string | { code?: string };
type RoleLike = string | {
  name?: string;
  code?: string;
  role_name?: string;
  role_code?: string;
  permissions?: PermissionLike[];
};
interface UserLike {
  roles?: RoleLike[];
  username?: string;
  full_name?: string;
  is_admin?: boolean;
  is_superuser?: boolean;
}

export const SUPERUSER_ROLES = new Set(["SYSTEM_ADMINISTRATOR"]);

export function normalizeRoleName(name: string): string {
  return name.trim().toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function normalizePermission(code: string): string {
  return code.trim().toLowerCase();
}

function roleNames(role: RoleLike): string[] {
  if (typeof role === "string") return [normalizeRoleName(role)];
  return [role.name, role.code, role.role_name, role.role_code]
    .filter((value): value is string => Boolean(value))
    .map(normalizeRoleName);
}

export function userRoleNames(user?: UserLike | null): string[] {
  return Array.from(new Set((user?.roles ?? []).flatMap(roleNames)));
}

export function isSuperuser(user?: UserLike | null): boolean {
  if (user?.is_admin || user?.is_superuser) return true;
  return userRoleNames(user).some((role) => SUPERUSER_ROLES.has(role));
}

export function canBackdate(user?: UserLike | null): boolean {
  if (isSuperuser(user)) return true;
  const roles = userRoleNames(user);
  return ["GENERAL_MANAGER", "FINANCE_MANAGER", "PURCHASING_MANAGER", "PROCUREMENT_MANAGER"].some((role) => roles.includes(role));
}

export function userPermissionCodes(user?: UserLike | null): string[] {
  return Array.from(new Set((user?.roles ?? []).flatMap((role) => {
    if (typeof role === "string") return [];
    return (role.permissions ?? [])
      .map((permission) => typeof permission === "string" ? permission : permission.code)
      .filter((code): code is string => Boolean(code))
      .map(normalizePermission);
  })));
}

function permissionGrants(granted: string, required: string): boolean {
  if (granted === "*" || granted === required) return true;
  if (granted.endsWith(".*")) return required.startsWith(granted.slice(0, -1));
  if (granted.endsWith(".manage")) {
    const module = granted.slice(0, -".manage".length);
    return required === `${module}.view` || required.startsWith(`${module}.`);
  }
  return false;
}

export function hasPermission(user: UserLike | null | undefined, permissionCode: string): boolean {
  if (isSuperuser(user)) return true;
  const required = normalizePermission(permissionCode);
  return userPermissionCodes(user).some((granted) => permissionGrants(granted, required));
}

export function canAccess(
  user: UserLike | null | undefined,
  allowedRoles?: string[],
  permissionCode?: string,
): boolean {
  if (isSuperuser(user)) return true;
  if (permissionCode && hasPermission(user, permissionCode)) return true;
  // Persisted mappings become authoritative after a role is migrated.
  if (permissionCode && userPermissionCodes(user).length > 0) return false;
  if (!allowedRoles?.length) return !permissionCode;
  const roles = userRoleNames(user);
  return allowedRoles.some((role) => roles.includes(normalizeRoleName(role)));
}

export function canPerform(
  user: UserLike | null | undefined,
  _action: AccessAction,
  allowedRoles: string[],
  actionAvailable = true,
  permissionCode?: string,
): boolean {
  if (!actionAvailable) return false;
  return canAccess(user, allowedRoles, permissionCode);
}
