import { create } from "zustand";
import api from "@/api/interceptor";
import { isSuperuser } from "@/lib/access";
import useWorkspaceTabs from "@/store/workspaceTabs";

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
}

export interface Permission {
  id?: number;
  code: string;
  description?: string | null;
}

export interface Role {
  id?: number;
  name: string;
  description?: string | null;
  permissions?: Permission[];
}

export interface User {
  id?: number;
  username?: string;
  full_name?: string;
  email?: string;
  roles?: Role[];
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  loading: boolean;
  authenticated: boolean;
  login: (payload: LoginRequest) => Promise<void>;
  logout: () => void;
  initialize: () => Promise<void>;
  setUser: (user: User | null) => void;
  hasPermission: (permission: string) => boolean;
}

const userIdentity = (user: User | null | undefined) => {
  if (!user) return null;
  if (user.id != null) return `id:${user.id}`;
  if (user.username) return `username:${user.username.trim().toLowerCase()}`;
  return null;
};

const storedUser = (): User | null => {
  try {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) as User : null;
  } catch {
    return null;
  }
};

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  loading: true,
  authenticated: false,

  hasPermission: (permission: string) => {
    const user = get().user;
    if (!user?.roles) return false;
    if (isSuperuser(user)) return true;
    return user.roles.some((role) => role.permissions?.some((item) => item.code === permission));
  },

  initialize: async () => {
    const accessToken = localStorage.getItem("access_token");
    const refreshToken = localStorage.getItem("refresh_token");

    if (!accessToken) {
      set({ accessToken: null, refreshToken: null, user: null, authenticated: false, loading: false });
      return;
    }

    set({ loading: true });
    try {
      const previous = storedUser();
      const { data: user } = await api.get<User>("/auth/me");
      if (userIdentity(previous) && userIdentity(previous) !== userIdentity(user)) {
        useWorkspaceTabs.getState().resetTabs();
      }
      localStorage.setItem("user", JSON.stringify(user));
      set({ accessToken, refreshToken, user, authenticated: true, loading: false });
    } catch {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("user");
      set({ accessToken: null, refreshToken: null, user: null, authenticated: false, loading: false });
    }
  },

  setUser: (user) => {
    if (user) localStorage.setItem("user", JSON.stringify(user));
    else localStorage.removeItem("user");
    set({ user });
  },

  login: async (payload) => {
    set({ loading: true });
    try {
      const previous = storedUser();
      const { data } = await api.post<LoginResponse>(
        "/auth/login",
        new URLSearchParams({ username: payload.username, password: payload.password }),
        { headers: { "Content-Type": "application/x-www-form-urlencoded" } },
      );

      localStorage.setItem("access_token", data.access_token);
      if (data.refresh_token) localStorage.setItem("refresh_token", data.refresh_token);
      else localStorage.removeItem("refresh_token");

      const me = await api.get<User>("/auth/me");
      if (userIdentity(previous) && userIdentity(previous) !== userIdentity(me.data)) {
        useWorkspaceTabs.getState().resetTabs();
      }
      localStorage.setItem("user", JSON.stringify(me.data));

      set({
        accessToken: data.access_token,
        refreshToken: data.refresh_token ?? null,
        user: me.data,
        authenticated: true,
        loading: false,
      });
    } catch (error) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("user");
      set({ accessToken: null, refreshToken: null, user: null, authenticated: false, loading: false });
      throw error;
    }
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    // Keep the last user identity until the next successful login so we can
    // distinguish same-account re-login from a different account.
    set({ accessToken: null, refreshToken: null, user: null, authenticated: false, loading: false });
    window.location.replace("/login");
  },
}));

export default useAuthStore;
