import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff, LogIn } from "lucide-react";

import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Card from "@/components/ui/Card";
import Label from "@/components/ui/Label";

import useAuthStore from "@/store/auth";

export default function LoginPage() {
  const navigate = useNavigate();

  const login = useAuthStore((s) => s.login);
  const loading = useAuthStore((s) => s.loading);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (
    e: React.FormEvent<HTMLFormElement>
  ) => {
    e.preventDefault();

    setError("");

    try {
      await login({
        username,
        password,
      });

      navigate("/", {
        replace: true,
      });
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ??
          "Invalid username or password."
      );
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-6">
      <Card className="w-full max-w-md p-8">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold">
            ERP HMM
          </h1>

          <p className="mt-2 text-sm text-slate-500">
            Sign in to continue
          </p>
        </div>

        <form
          className="space-y-5"
          onSubmit={handleSubmit}
        >
          <div>
            <Label required>
              Username
            </Label>

            <Input
              autoFocus
              value={username}
              autoComplete="username"
              onChange={(e) =>
                setUsername(e.target.value)
              }
            />
          </div>

          <div>
            <Label required>
              Password
            </Label>

            <div className="relative">
              <Input
                value={password}
                autoComplete="current-password"
                type={
                  showPassword
                    ? "text"
                    : "password"
                }
                onChange={(e) =>
                  setPassword(e.target.value)
                }
              />

              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500"
                onClick={() =>
                  setShowPassword(
                    !showPassword
                  )
                }
              >
                {showPassword ? (
                  <EyeOff size={18} />
                ) : (
                  <Eye size={18} />
                )}
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-600">
              {error}
            </div>
          )}

          <Button
            type="submit"
            className="w-full"
            disabled={loading}
          >
            <LogIn
              size={18}
              className="mr-2"
            />

            {loading
              ? "Signing in..."
              : "Sign In"}
          </Button>
        </form>
      </Card>
    </div>
  );
}