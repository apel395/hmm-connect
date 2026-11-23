import { Navigate, useLocation } from "react-router-dom";

export default function LegacyGeneralLedgerRedirect() {
  const location = useLocation();
  return <Navigate to={{ pathname: "/journal/general-ledger", search: location.search }} replace />;
}
