import { useState, type FormEvent } from "react";
import axios from "axios";
import { useNavigate, useSearchParams } from "react-router-dom";
import { BedDouble, Eye, EyeOff, LogIn, ShieldCheck, Sparkles } from "lucide-react";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Label from "@/components/ui/Label";
import useAuthStore from "@/store/auth";

interface ValidationError { msg?: string }

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirectValue = searchParams.get("redirect");
  const redirect = redirectValue?.startsWith("/") && !redirectValue.startsWith("//") ? redirectValue : null;
  const login = useAuthStore((state) => state.login);
  const loading = useAuthStore((state) => state.loading);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [sessionConflict, setSessionConflict] = useState(false);

  async function signIn(replaceSession = false) {
    if (loading) return;
    setError(""); setSessionConflict(false);
    try { await login({ username: username.trim(), password, replaceSession }); navigate(redirect || "/", { replace: true }); }
    catch (caught) {
      if (axios.isAxiosError(caught)) {
        if (caught.response?.status === 409) setSessionConflict(true);
        if (!caught.response) { setError("Connection interrupted. Please try signing in again."); return; }
        const detail = (caught.response?.data as { detail?: string | ValidationError[] } | undefined)?.detail;
        if (typeof detail === "string") { setError(detail); return; }
        if (Array.isArray(detail)) { setError(detail.map((item) => item.msg).filter(Boolean).join(" ") || "Unable to sign in."); return; }
      }
      setError("Invalid username or password.");
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void signIn();
  }

  return <main className="min-h-screen bg-[#F8F6F1] text-[#202723] lg:grid lg:grid-cols-[1.05fr_1fr]">
    <section className="relative hidden min-h-screen overflow-hidden bg-[#073F37] px-12 py-10 text-white lg:flex lg:flex-col">
      <div className="absolute -right-32 -top-32 h-96 w-96 rounded-full border border-[#D4AA1D]/15" aria-hidden="true"/><div className="absolute -right-20 -top-20 h-72 w-72 rounded-full border border-[#D4AA1D]/20" aria-hidden="true"/><div className="absolute bottom-20 left-10 h-48 w-48 rounded-full border border-white/5" aria-hidden="true"/>
      <div className="relative flex items-center gap-4"><div className="grid h-16 w-24 place-items-center overflow-hidden rounded-xl bg-white p-1.5 shadow-sm"><img src="/mutiara-merdeka-logo.svg" alt="Hotel Mutiara Merdeka" className="h-full w-full object-contain"/></div><div><div className="font-semibold tracking-wide">MMH-Connect</div><div className="text-xs text-emerald-100/65">Hotel Administration</div></div></div>
      <div className="relative my-auto max-w-xl"><div className="mb-5 flex gap-1 text-sm text-[#D4AA1D]"><span>★</span><span>★</span><span>★</span><span>★</span></div><p className="mb-3 text-xs font-semibold uppercase tracking-[0.24em] text-[#E1C65F]">Hotel Mutiara Merdeka</p><h1 className="max-w-lg font-serif text-5xl font-semibold leading-tight tracking-tight">Thoughtful operations for exceptional hospitality.</h1><p className="mt-6 max-w-lg text-base leading-7 text-emerald-50/70">A unified workspace for purchasing, inventory, suppliers, finance, and hotel administration in Pekanbaru.</p><div className="mt-10 grid max-w-lg grid-cols-2 gap-4"><div className="rounded-xl border border-white/10 bg-white/5 p-4"><ShieldCheck className="mb-3 h-5 w-5 text-[#E1C65F]"/><div className="text-sm font-semibold">Secure access</div><div className="mt-1 text-xs text-emerald-50/60">Role-based hotel administration</div></div><div className="rounded-xl border border-white/10 bg-white/5 p-4"><Sparkles className="mb-3 h-5 w-5 text-[#E1C65F]"/><div className="text-sm font-semibold">Connected operations</div><div className="mt-1 text-xs text-emerald-50/60">Clear workflows across departments</div></div></div></div>
      <p className="relative text-xs text-emerald-100/45">Hotel Mutiara Merdeka · Pekanbaru, Indonesia</p>
    </section>
    <section className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-10"><div className="w-full max-w-md"><div className="mb-10 flex items-center gap-3 lg:hidden"><div className="grid h-14 w-20 place-items-center overflow-hidden rounded-lg bg-white p-1 shadow-sm"><img src="/mutiara-merdeka-logo.svg" alt="Hotel Mutiara Merdeka" className="h-full w-full object-contain"/></div><div><div className="font-semibold">MMH-Connect</div><div className="text-xs text-[#6F756F]">Hotel Mutiara Merdeka</div></div></div><div className="rounded-xl border border-[#E8E2D8] bg-white p-6 shadow-[0_12px_40px_rgba(40,48,43,0.08)] sm:p-9"><div className="mb-8"><div className="mb-4 grid h-10 w-10 place-items-center rounded-lg bg-[#E7F1EE] text-[#086B5A]"><BedDouble className="h-5 w-5"/></div><h2 className="font-serif text-3xl font-semibold tracking-tight">Welcome back</h2><p className="mt-2 text-sm text-[#6F756F]">Sign in to your hotel administration account.</p></div><form className="space-y-5" onSubmit={handleSubmit}><div><Label required>Username</Label><Input autoFocus value={username} autoComplete="username" disabled={loading} placeholder="Enter your username" className="border-[#DCD6CB] focus:border-[#086B5A] focus:ring-[#086B5A]" onChange={(event)=>{setUsername(event.target.value);setSessionConflict(false);}}/></div><div><Label required>Password</Label><div className="relative"><Input value={password} autoComplete="current-password" type={showPassword?"text":"password"} disabled={loading} placeholder="Enter your password" className="border-[#DCD6CB] pr-11 focus:border-[#086B5A] focus:ring-[#086B5A]" onChange={(event)=>{setPassword(event.target.value);setSessionConflict(false);}}/><button type="button" className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-2 text-[#6F756F] hover:bg-[#F8F6F1] hover:text-[#086B5A]" aria-label={showPassword?"Hide password":"Show password"} onClick={()=>setShowPassword(v=>!v)}>{showPassword?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></div>{error&&<div role="alert" className="rounded-lg border border-[#C75D56]/25 bg-red-50 px-4 py-3 text-sm text-[#A44741]">{error}</div>}{sessionConflict&&<Button type="button" disabled={loading} className="w-full" onClick={()=>void signIn(true)}>Sign in and end previous session</Button>}<Button type="submit" loading={loading} className="w-full bg-[#086B5A] hover:bg-[#07594C] focus:ring-[#086B5A]"><LogIn size={18}/>{loading?"Signing in…":"Sign In"}</Button></form></div><p className="mt-6 text-center text-xs text-[#6F756F]">Authorized personnel only · Accounts are created by a system administrator.</p></div></section>
  </main>;
}
