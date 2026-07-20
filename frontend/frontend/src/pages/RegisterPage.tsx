import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";

import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";

import {
  register,
  type RegisterRequest,
} from "../features/auth/registerApi";

export default function RegisterPage() {
  const navigate = useNavigate();

  const [form, setForm] = useState<RegisterRequest>({
    username: "",
    email: "",
    full_name: "",
    password: "",
  });

  const registerMutation = useMutation({
    mutationFn: register,

    onSuccess: () => {
      navigate("/login", {
        state: {
          message: "Account created successfully. Please login.",
        },
      });
    },
  });

  const isAuthenticated = Boolean(
    localStorage.getItem("access_token"),
  );

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  function updateField(
    field: keyof RegisterRequest,
    value: string,
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    registerMutation.mutate(form);
  }

  const error = registerMutation.error as
    | {
        response?: {
          data?: {
            detail?: string;
          };
        };
      }
    | null;

  return (
    <main className="flex min-h-screen bg-slate-950">
      <section className="hidden flex-1 flex-col justify-between p-12 text-white lg:flex">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white font-bold text-slate-950">
              E
            </div>

            <span className="text-xl font-semibold">
              HMM Connect
            </span>
          </div>
        </div>

        <div className="max-w-lg">
          <h1 className="text-5xl font-semibold leading-tight">
            Start managing your business better.
          </h1>

          <p className="mt-6 text-lg text-slate-400">
            Create your HMM account and get started.
          </p>
        </div>

        <p className="text-sm text-slate-500">
          HMM Connect v1.0.0
        </p>
      </section>

      <section className="flex w-full items-center justify-center bg-slate-50 p-6 lg:w-[480px]">
        <div className="w-full max-w-sm">
          <div className="mb-8">
            <h2 className="text-2xl font-semibold text-slate-900">
              Create account
            </h2>

            <p className="mt-2 text-sm text-slate-500">
              Register a new HMM account
            </p>
          </div>

          <form
            onSubmit={handleSubmit}
            className="space-y-4"
          >
            <Input
              label="Full name"
              placeholder="John Doe"
              value={form.full_name}
              onChange={(event) =>
                updateField(
                  "full_name",
                  event.target.value,
                )
              }
              required
            />

            <Input
              label="Username"
              placeholder="johndoe"
              value={form.username}
              onChange={(event) =>
                updateField(
                  "username",
                  event.target.value,
                )
              }
              required
            />

            <Input
              label="Email"
              type="email"
              placeholder="john@example.com"
              value={form.email}
              onChange={(event) =>
                updateField(
                  "email",
                  event.target.value,
                )
              }
              required
            />

            <Input
              label="Password"
              type="password"
              placeholder="Create a password"
              value={form.password}
              onChange={(event) =>
                updateField(
                  "password",
                  event.target.value,
                )
              }
              required
              minLength={8}
            />

            {error?.response?.data?.detail && (
              <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
                {error.response.data.detail}
              </div>
            )}

            <Button
              type="submit"
              loading={registerMutation.isPending}
              className="w-full"
            >
              Create account
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            Already have an account?{" "}
            <Link
              to="/login"
              className="font-medium text-slate-900 hover:underline"
            >
              Sign in
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}