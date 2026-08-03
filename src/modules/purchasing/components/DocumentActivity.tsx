import Card from "@/components/ui/Card";

export interface DocumentActivityItem { id: number; action: string; summary: string; actor_name?: string | null; occurred_at: string }

export default function DocumentActivity({ events = [] }: { events?: DocumentActivityItem[] }) {
  return <Card><h2 className="mb-4 font-semibold">Activity History</h2>{events.length === 0 ? <p className="text-sm text-slate-500">No activity recorded.</p> : <div className="divide-y">{events.map((event) => <div key={event.id} className="grid gap-1 py-3 text-sm md:grid-cols-4"><div>{new Date(event.occurred_at).toLocaleString()}</div><div className="font-medium">{event.action}</div><div>{event.actor_name ?? "System"}</div><div className="text-slate-600">{event.summary}</div></div>)}</div>}</Card>;
}
