import { useLocation, useNavigate } from "react-router-dom";
import useWorkspaceTabs from "@/store/workspaceTabs";

export default function useWorkspaceBack() {
  const location = useLocation();
  const navigate = useNavigate();
  const disabled = location.pathname === "/dashboard";
  const back = () => {
    if (disabled) return;
    // Print routes are outside the workspace and must not close their source tab.
    if (location.pathname.endsWith("/print")) {
      const source = location.pathname === "/journal/register/print" ? "/journal"
        : location.pathname === "/finance-setup/coa/print" ? "/finance-setup"
        : /^\/pos\/sales\/\d+\/print$/.test(location.pathname) ? "/pos/sales"
        : location.pathname.slice(0, -6);
      navigate(`${source}${location.search}`, { replace: true });
      return;
    }
    const path = `${location.pathname}${location.search}`;
    const { nextPath } = useWorkspaceTabs.getState().closeTab(path);
    navigate(nextPath || "/dashboard", { replace: true });
  };
  return { back, disabled };
}
