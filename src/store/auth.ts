import { create } from "zustand";
import axios from "axios";
import api from "@/api/interceptor";
import { hasPermission as userHasPermission } from "@/lib/access";
import useWorkspaceTabs from "@/store/workspaceTabs";
import queryClient from "@/lib/query";

export interface LoginRequest {
  username: string;
  password: string;
  replaceSession?: boolean;
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
  business_unit_id?: number | null;
  department_id?: number | null;
  location_id?: number | null;
  default_business_unit_id?: number | null;
  default_department_id?: number | null;
  default_location_id?: number | null;
  roles?: Role[];
}

export interface LoginResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  user: User;
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

const WORKSPACE_OWNER_KEY = "hmm-last-user-identity";
const LAST_ACTIVITY_KEY = "hmm-last-activity-at";

const userIdentity = (user: User | null | undefined) => {
  if (!user) return null;
  if (user.id != null) return `id:${user.id}`;
  if (user.username) return `username:${user.username.trim().toLowerCase()}`;
  return null;
};

const adoptWorkspaceOwner = (user: User) => {
  const nextIdentity = userIdentity(user);
  if (!nextIdentity) return;
  const previousIdentity = localStorage.getItem(WORKSPACE_OWNER_KEY);
  if (previousIdentity && previousIdentity !== nextIdentity) {
    useWorkspaceTabs.getState().resetTabs();
    queryClient.clear();
  }
  localStorage.setItem(WORKSPACE_OWNER_KEY, nextIdentity);
};

const clearLocalSession = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("user");
  localStorage.removeItem(LAST_ACTIVITY_KEY);
};

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  loading: true,
  authenticated: false,

  hasPermission: (permission: string) => userHasPermission(get().user, permission),

  initialize: async () => {
    const accessToken = localStorage.getItem("access_token");
    const refreshToken = localStorage.getItem("refresh_token");

    if (!accessToken) {
      set({ accessToken: null, refreshToken: null, user: null, authenticated: false, loading: false });
      return;
    }

    set({ loading: true });
    try {
      const { data: user } = await api.get<User>("/auth/me");
      adoptWorkspaceOwner(user);
      localStorage.setItem("user", JSON.stringify(user));
      if (!localStorage.getItem(LAST_ACTIVITY_KEY)) localStorage.setItem(LAST_ACTIVITY_KEY, String(Date.now()));
      set({ accessToken, refreshToken, user, authenticated: true, loading: false });
    } catch (error) {
      // A network interruption does not mean the server session expired.
      if (axios.isAxiosError(error) && error.response?.status === 401) clearLocalSession();
      set({ accessToken: null, refreshToken: null, user: null, authenticated: false, loading: false });
    }
  },

  setUser: (user) => {
    if (user) localStorage.setItem("user", JSON.stringify(user));
    else localStorage.removeItem("user");
    set({ user });
  },

  login: async (payload) => {
    if (get().loading) throw new Error("Sign in is already in progress.");
    set({ loading: true });
    try {
      const { data } = await api.post<LoginResponse>(
        "/auth/login",
        new URLSearchParams({ username: payload.username, password: payload.password,
          replace_session: String(payload.replaceSession ?? false) }),
        { headers: { "Content-Type": "application/x-www-form-urlencoded" } },
      );

      localStorage.setItem("access_token", data.access_token);
      if (data.refresh_token) localStorage.setItem("refresh_token", data.refresh_token);
      else localStorage.removeItem("refresh_token");
      localStorage.setItem(LAST_ACTIVITY_KEY, String(Date.now()));

      adoptWorkspaceOwner(data.user);
      localStorage.setItem("user", JSON.stringify(data.user));

      set({
        accessToken: data.access_token,
        refreshToken: data.refresh_token ?? null,
        user: data.user,
        authenticated: true,
        loading: false,
      });
    } catch (error) {
      clearLocalSession();
      set({ accessToken: null, refreshToken: null, user: null, authenticated: false, loading: false });
      throw error;
    }
  },

  logout: () => {
    const finish = () => {
      queryClient.clear();
      useWorkspaceTabs.getState().resetTabs();
      clearLocalSession();
      set({ accessToken: null, refreshToken: null, user: null, authenticated: false, loading: false });
      window.location.replace("/login");
    };
    void api.post("/auth/logout").catch(() => undefined).finally(finish);
  },
}));

export default useAuthStore;
