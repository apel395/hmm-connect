import {
  ArrowDownRight,
  ArrowUpRight,
  Box,
  ShoppingCart,
  Users,
} from "lucide-react";

const stats = [
  {
    label: "Total Revenue",
    value: "$0.00",
    change: "0%",
    positive: true,
    icon: ShoppingCart,
  },
  {
    label: "Total Products",
    value: "0",
    change: "0%",
    positive: true,
    icon: Box,
  },
  {
    label: "Total Customers",
    value: "0",
    change: "0%",
    positive: true,
    icon: Users,
  },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          Dashboard
        </h1>

        <p className="mt-1 text-sm text-slate-500">
          Welcome back. Here's what's happening today.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {stats.map((stat) => {
          const Icon = stat.icon;

          return (
            <div
              key={stat.label}
              className="rounded-xl border border-slate-200 bg-white p-5"
            >
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100">
                  <Icon
                    size={20}
                    className="text-slate-700"
                  />
                </div>

                <span
                  className={`flex items-center gap-1 text-sm ${
                    stat.positive
                      ? "text-emerald-600"
                      : "text-red-600"
                  }`}
                >
                  {stat.positive ? (
                    <ArrowUpRight size={16} />
                  ) : (
                    <ArrowDownRight size={16} />
                  )}

                  {stat.change}
                </span>
              </div>

              <p className="mt-5 text-sm text-slate-500">
                {stat.label}
              </p>

              <p className="mt-1 text-2xl font-semibold text-slate-900">
                {stat.value}
              </p>
            </div>
          );
        })}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="font-semibold text-slate-900">
          Overview
        </h2>

        <div className="flex h-64 items-center justify-center text-sm text-slate-400">
          No data available yet
        </div>
      </div>
    </div>
  );
}