import { createContext } from "react";

export type WorkspaceArea = "Master data" | "Inventory" | "Accounting" | "Reports";
export const DataWorkspaceContext = createContext<{
  area: WorkspaceArea;
  dense: boolean;
  toggleDensity: () => void;
} | null>(null);
