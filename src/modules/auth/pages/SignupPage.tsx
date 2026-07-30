import { useState, type FormEvent } from "react";
import axios from "axios";
import {
  CheckCircle2,
  Eye,
  EyeOff,
  ShieldCheck,
  UserPlus,
} from "lucide-react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Label from "@/components/ui/Label";
import useAuthStore from "@/store/auth";
import {
  registerAccount,
  type RegistrationResponse,
} from "../api/registerApi";

interface ValidationDetail {
  loc?: Array<string | number>;
  msg?: string;
}

function safeRedirect(value: string | null): string | null {
  return value?.startsWith("/") && !value.startsWith("//") ? value : null;
}

function registrationError(error: unknown): string {
  if (!axios.isAxiosError(error)) return "Unable to create your account.";
  const data = error.response?.data as
    | { detail?: string | ValidationDetail[] }
    | undefined;
  if (Array.isArray(data?.detail)) {
    const message = data.detail
      .map((item) => {
        const field = item.loc?.filter((part) => part !== "body").join(".");
        return [field, item.msg].filter(Boolean).join(": ");
      })
      .filter(Boolean)
      .join("; ");
    if (message) return message;
  }
  if (typeof data?.detail === "string") return data.detail;
  if (error.response?.status === 409) {
    return "That username or email is already registered.";
  }
  if (error.response?.status === 422) {
    return "Please check the registration fields and try again.";
  }
  if (error.response?.status && error.response.status >= 500) {
    return "The server could not create your account. Please try again later.";
  }
  return "Unable to create your account.";
}

export default function SignupPage() {
  const authenticated = useAuthStore((state) => state.authenticated);
  const [searchParams] = useSearchParams();
  const redirect = safeRedirect(searchParams.get("redirect"));
  const loginTarget = redirect
    ? `/login?redirect=${encodeURIComponent(redirect)}`
    : "/login";
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<RegistrationResponse | null>(null);

  if (authenticated) return <Navigate to={redirect || "/dashboard"} replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    const normalizedUsername = username.trim();
    const normalizedName = fullName.trim();
    const normalizedEmail = email.trim().toLowerCase();

    if (!normalizedUsername || !normalizedName || !normalizedEmail || !password) {
      setError("Username, full name, email, and password are required.");
      return;
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(normalizedEmail)) {
      setError("Enter a valid email address.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Password and confirmation do not match.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const response = await registerAccount({
        username: normalizedUsername,
        full_name: normalizedName,
        email: normalizedEmail,
        password,
      });
      setSuccess(response.data);
      setUsername("");
      setFullName("");
      setEmail("");
      setPassword("");
      setConfirmPassword("");
    } catch (caught) {
      setError(registrationError(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#F8F6F1] text-[#202723] lg:grid lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden min-h-screen overflow-hidden bg-[#073F37] px-12 py-10 text-white lg:flex lg:flex-col">
        <div className="absolute -right-32 -top-32 h-96 w-96 rounded-full border border-[#C49A4A]/15" />
        <div className="absolute -right-20 -top-20 h-72 w-72 rounded-full border border-[#C49A4A]/20" />
        <div className="relative flex items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-xl border border-[#C49A4A]/60 bg-white/5 font-serif text-lg font-bold tracking-wider text-[#E4C57E]">
            HMM
          </div>
          <div>
            <div className="font-semibold tracking-wide">HMM Connect</div>
            <div className="text-xs text-emerald-100/65">Hotel Administration</div>
          </div>
        </div>
        <div className="relative my-auto max-w-xl">
          <div className="mb-5 flex gap-1 text-sm text-[#C49A4A]">
            <span>★</span><span>★</span><span>★</span><span>★</span>
          </div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.24em] text-[#D8B96F]">
            Hotel Mutiara Merdeka
          </p>
          <h1 className="font-serif text-5xl font-semibold leading-tight tracking-tight">
            Join a connected hotel operations workspace.
          </h1>
          <p className="mt-6 max-w-lg leading-7 text-emerald-50/70">
            Create your basic account. An administrator will assign the access
            appropriate for your responsibilities.
          </p>
          <div className="mt-10 rounded-xl border border-white/10 bg-white/5 p-5">
            <ShieldCheck className="mb-3 h-6 w-6 text-[#D8B96F]" />
            <div className="font-semibold">Access is administrator controlled</div>
            <p className="mt-1 text-sm text-emerald-50/60">
              Public registration never assigns privileged roles or permissions.
            </p>
          </div>
        </div>
        <p className="relative text-xs text-emerald-100/45">
          Hotel Mutiara Merdeka · Pekanbaru, Indonesia
        </p>
      </section>

      <section className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-md">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-[#073F37] font-serif text-sm font-bold tracking-wider text-[#E4C57E]">
              HMM
            </div>
            <div>
              <div className="font-semibold">HMM Connect</div>
              <div className="text-xs text-[#6F756F]">Hotel Mutiara Merdeka</div>
            </div>
          </div>

          <div className="rounded-xl border border-[#E8E2D8] bg-white p-6 shadow-[0_12px_40px_rgba(40,48,43,0.08)] sm:p-9">
            {success ? (
              <div className="py-4 text-center">
                <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-emerald-50 text-[#086B5A]">
                  <CheckCircle2 className="h-7 w-7" />
                </div>
                <h1 className="mt-5 font-serif text-2xl font-semibold">Account created</h1>
                <p className="mt-3 text-sm leading-6 text-[#6F756F]">
                  {success.requires_admin_access
                    ? "Your account has been created and is waiting for administrator access."
                    : success.message}
                </p>
                <Link
                  to={loginTarget}
                  className="mt-6 inline-flex h-10 items-center justify-center rounded-lg bg-[#086B5A] px-5 text-sm font-semibold text-white hover:bg-[#07594C]"
                >
                  Continue to sign in
                </Link>
              </div>
            ) : (
              <>
                <div className="mb-7">
                  <div className="mb-4 grid h-10 w-10 place-items-center rounded-lg bg-[#E7F1EE] text-[#086B5A]">
                    <UserPlus className="h-5 w-5" />
                  </div>
                  <h1 className="font-serif text-3xl font-semibold tracking-tight">Create account</h1>
                  <p className="mt-2 text-sm text-[#6F756F]">
                    Register for basic access to HMM Connect.
                  </p>
                </div>

                <form className="space-y-4" onSubmit={submit}>
                  <label className="block">
                    <Label required>Username</Label>
                    <Input autoFocus autoComplete="username" value={username} disabled={submitting} onChange={(event) => setUsername(event.target.value)} />
                  </label>
                  <label className="block">
                    <Label required>Full Name</Label>
                    <Input autoComplete="name" value={fullName} disabled={submitting} onChange={(event) => setFullName(event.target.value)} />
                  </label>
                  <label className="block">
                    <Label required>Email</Label>
                    <Input type="email" autoComplete="email" value={email} disabled={submitting} onChange={(event) => setEmail(event.target.value)} />
                  </label>
                  <label className="block">
                    <Label required>Password</Label>
                    <div className="relative">
                      <Input type={showPassword ? "text" : "password"} autoComplete="new-password" value={password} disabled={submitting} className="pr-11" onChange={(event) => setPassword(event.target.value)} />
                      <button type="button" aria-label={showPassword ? "Hide password" : "Show password"} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-2 text-[#6F756F] hover:bg-[#F8F6F1]" onClick={() => setShowPassword((value) => !value)}>
                        {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </div>
                  </label>
                  <label className="block">
                    <Label required>Confirm Password</Label>
                    <div className="relative">
                      <Input type={showConfirmation ? "text" : "password"} autoComplete="new-password" value={confirmPassword} disabled={submitting} className="pr-11" onChange={(event) => setConfirmPassword(event.target.value)} />
                      <button type="button" aria-label={showConfirmation ? "Hide confirmation password" : "Show confirmation password"} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-2 text-[#6F756F] hover:bg-[#F8F6F1]" onClick={() => setShowConfirmation((value) => !value)}>
                        {showConfirmation ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </div>
                  </label>

                  {error && (
                    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-[#A44741]">
                      {error}
                    </div>
                  )}
                  <Button type="submit" loading={submitting} className="w-full bg-[#086B5A] hover:bg-[#07594C] focus:ring-[#086B5A]">
                    <UserPlus className="h-4 w-4" />
                    Create Account
                  </Button>
                </form>
              </>
            )}
          </div>

          <p className="mt-6 text-center text-sm text-[#6F756F]">
            Already have an account?{" "}
            <Link className="font-semibold text-[#086B5A] hover:underline" to={loginTarget}>
              Sign in
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
