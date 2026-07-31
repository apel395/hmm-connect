import axios, {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from "axios";

const api: AxiosInstance = axios.create({
  baseURL: 'https://feb-purchases-burlington-expanding.trycloudflare.com/api/v1',
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
    const status =
      error.response?.status;

    if (status === 401) {
      console.warn(
        "Unauthorized request."
      );
    }

    if (status === 403) {
      console.warn(
        "Forbidden request."
      );
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