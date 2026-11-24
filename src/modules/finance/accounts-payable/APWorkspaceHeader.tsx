import { NavLink, useLocation } from "react-router-dom";

const tabs = [
  { label: "Payables Summary", to: "/accounts-payable", exact: true },
  { label: "Payables Detail", to: "/accounts-payable/detail" },
  { label: "AP Aging", to: "/accounts-payable/aging" },
  { label: "AP Movement", to: "/accounts-payable/movement" },
  { label: "Supplier Invoices", to: "/accounts-payable/invoices" },
  { label: "Payment Vouchers", to: "/finance/payment-vouchers" },
  { label: "Payments", to: "/accounts-payable/payments" },
  { label: "Credit / Debit Notes", to: "/accounts-payable/adjustments" },
];

export default function APWorkspaceHeader() {
  const location = useLocation();

  return (
    <nav className="flex min-w-max gap-6 overflow-x-auto border-b border-slate-200" aria-label="Accounts Payable workspace">
      {tabs.map((tab) => {
        const active = tab.exact
          ? location.pathname === tab.to
          : location.pathname.startsWith(tab.to) || (tab.to === "/finance/payment-vouchers" && location.pathname.startsWith("/payment-vouchers"));
        return (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={`relative whitespace-nowrap px-1 pb-2 pt-1 text-[13px] font-medium transition-colors ${
              active ? "text-[#086B5A]" : "text-slate-500 hover:text-slate-900"
            }`}
          >
            {tab.label}
            {active && <span className="absolute inset-x-0 bottom-0 h-0.5 bg-[#086B5A]" />}
          </NavLink>
        );
      })}
    </nav>
  );
}
