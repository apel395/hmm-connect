import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface WorkspaceTab {
  id: string;
  path: string;
  title: string;
  pinned?: boolean;
}

interface WorkspaceTabsState {
  tabs: WorkspaceTab[];
  closedTabs: WorkspaceTab[];
  ensureTab: (tab: WorkspaceTab) => void;
  closeTab: (id: string) => { nextPath: string | null };
  reopenLastClosed: () => string | null;
}

const dashboardTab: WorkspaceTab = {
  id: "/dashboard",
  path: "/dashboard",
  title: "Dashboard",
  pinned: true,
};

export const useWorkspaceTabs = create<WorkspaceTabsState>()(
  persist(
    (set, get) => ({
      tabs: [dashboardTab],
      closedTabs: [],
      ensureTab: (tab) => {
        set((state) => {
          const exists = state.tabs.some((item) => item.id === tab.id);
          if (exists) {
            return {
              tabs: state.tabs.map((item) =>
                item.id === tab.id && item.title !== tab.title
                  ? { ...item, title: tab.title }
                  : item,
              ),
            };
          }
          return { tabs: [...state.tabs, tab] };
        });
      },
      closeTab: (id) => {
        const state = get();
        const index = state.tabs.findIndex((tab) => tab.id === id);
        if (index < 0) return { nextPath: null };
        const target = state.tabs[index];
        if (target.pinned) return { nextPath: null };

        const remaining = state.tabs.filter((tab) => tab.id !== id);
        const next = remaining[Math.min(index, remaining.length - 1)] ?? dashboardTab;
        set({
          tabs: remaining.length ? remaining : [dashboardTab],
          closedTabs: [target, ...state.closedTabs].slice(0, 20),
        });
        return { nextPath: next.path };
      },
      reopenLastClosed: () => {
        const state = get();
        const target = state.closedTabs[0];
        if (!target) return null;
        set({
          tabs: state.tabs.some((tab) => tab.id === target.id)
            ? state.tabs
            : [...state.tabs, target],
          closedTabs: state.closedTabs.slice(1),
        });
        return target.path;
      },
    }),
    {
      name: "hmm-workspace-tabs",
      partialize: (state) => ({ tabs: state.tabs, closedTabs: state.closedTabs }),
      merge: (persisted, current) => {
        const saved = persisted as Partial<WorkspaceTabsState> | undefined;
        const tabs = saved?.tabs?.length ? saved.tabs : [dashboardTab];
        return {
          ...current,
          ...saved,
          tabs: tabs.some((tab) => tab.id === dashboardTab.id)
            ? tabs.map((tab) => tab.id === dashboardTab.id ? { ...tab, pinned: true } : tab)
            : [dashboardTab, ...tabs],
        };
      },
    },
  ),
);

export default useWorkspaceTabs;
