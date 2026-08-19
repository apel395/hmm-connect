import axios, {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from "axios";

const api: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  (
    config: InternalAxiosRequestConfig
  ) => {
    const token =
      localStorage.getItem(
        "access_token"
      );

    if (
      token &&
      token.trim() !== ""
    ) {
      config.headers.Authorization =
        `Bearer ${token}`;
    }

    return config;
  },
  (error: AxiosError) =>
    Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,

  (error: AxiosError) => {
    const status = error.response?.status;
    const requestUrl = String(error.config?.url || "");

    if (status === 401) {
      console.warn("Unauthorized request.");
      const isLoginRequest = requestUrl.includes("/auth/login");
      if (!isLoginRequest && localStorage.getItem("access_token")) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("user");
        localStorage.removeItem("hmm-last-activity-at");
        if (!window.location.pathname.startsWith("/login")) {
          window.location.replace("/login?reason=session");
        }
      }
    }

    if (status === 403) {
      console.warn("Forbidden request.");
    }

    return Promise.reject(error);
  }
);

export default api;

export async function get<T>(
  url: string,
  config?: AxiosRequestConfig
): Promise<T> {
  const response =
    await api.get<T>(
      url,
      config
    );

  return response.data;
}

export async function post<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> {
  const response =
    await api.post<T>(
      url,
      data,
      config
    );

  return response.data;
}

export async function put<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> {
  const response =
    await api.put<T>(
      url,
      data,
      config
    );

  return response.data;
}

export async function patch<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> {
  const response =
    await api.patch<T>(
      url,
      data,
      config
    );

  return response.data;
}

export async function del<T>(
  url: string,
  config?: AxiosRequestConfig
): Promise<T> {
  const response =
    await api.delete<T>(
      url,
      config
    );

  return response.data;
}
