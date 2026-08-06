import { useEffect, useState } from "react";
import { Cpu, ServerCog, ShieldCheck } from "lucide-react";
import api from "@/api/interceptor";

interface Capabilities {
  runtime?: string;
  worker?: boolean;
}

interface Props {
  title: string;
  description: string;
}

export default function WorkerRequiredPage({ title, description }: Props) {
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);

  useEffect(() => {
    api.get<Capabilities>("/api/v1/system/capabilities")
      .then((response) => setCapabilities(response.data))
      .catch(() => setCapabilities({ runtime: "lambda", worker: false }));
  }, []);

  const enabled = capabilities?.worker === true;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#A77A2B]">Worker Services</p>
        <h1 className="mt-2 font-serif text-3xl font-semibold text-[#173E37]">{title}</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{description}</p>
      </div>

      <section className="overflow-hidden rounded-2xl border border-[#E8E2D8] bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-[#EEE8DE] bg-[#FBF9F5] px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-[#E7F1EE] text-[#086B5A]">
              <ServerCog className="h-5 w-5" />
            </div>
            <div>
              <div className="font-semibold text-[#173E37]">HMM Processing Service</div>
              <div className="text-xs text-slate-500">Excel processing, large reports, and scheduled jobs</div>
            </div>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${enabled ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-800"}`}>
            {enabled ? "Available" : "Worker Required"}
          </span>
        </div>

        <div className="grid gap-4 p-6 md:grid-cols-3">
          <div className="rounded-xl border border-slate-200 p-4">
            <Cpu className="mb-3 h-5 w-5 text-[#086B5A]" />
            <div className="text-sm font-semibold">Heavy processing</div>
            <p className="mt-1 text-xs leading-5 text-slate-500">Runs outside Lambda to keep daily transactions fast and reliable.</p>
          </div>
          <div className="rounded-xl border border-slate-200 p-4">
            <ShieldCheck className="mb-3 h-5 w-5 text-[#086B5A]" />
            <div className="text-sm font-semibold">Controlled access</div>
            <p className="mt-1 text-xs leading-5 text-slate-500">Only administrators and authorized finance staff can start worker jobs.</p>
          </div>
          <div className="rounded-xl border border-slate-200 p-4">
            <ServerCog className="mb-3 h-5 w-5 text-[#086B5A]" />
            <div className="text-sm font-semibold">EC2 deployment</div>
            <p className="mt-1 text-xs leading-5 text-slate-500">This module activates automatically after the processing worker is deployed.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
