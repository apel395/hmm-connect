import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { useLogin } from "../features/auth/useAuth";

export default function LoginPage() {
  const navigate = useNavigate();
  const login = useLogin();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (localStorage.getItem("access_token")) {
      navigate("/", { replace: true });
    }
  }, [navigate]);

  if (localStorage.getItem("access_token")) {
    return <Navigate to="/" replace />;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    login.mutate(
      { username, password },
      {
        onSuccess: () => navigate("/", { replace: true }),
      },
    );
  }

  const error = login.error as { response?: { data?: { detail?: string } } } | null;

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-xl">
        <div className="mb-8">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-900 text-sm font-bold text-white">
            HMM
          </div>
          <h1 className="text-2xl font-semibold text-slate-900">Welcome back</h1>
          <p className="mt-1 text-sm text-slate-500">Sign in to continue to HMM Connect.</p>
        </div>

        <form onSubmit={submit} className="space-y-5">
          <Input
            label="Username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="Enter username"
            autoComplete="username"
            required
          />

          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Enter password"
            autoComplete="current-password"
            required
          />

          {error?.response?.data?.detail && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error.response.data.detail}
            </p>
          )}

          <Button type="submit" loading={login.isPending} className="w-full">
            Sign in
          </Button>
        </form>
      </div>
    </main>
  );
}
