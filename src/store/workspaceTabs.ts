import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface WorkspaceTab {
  id: string;
  path: string;
  title: string;
  pinned?: boolean;
  group?: string;
  lastActiveAt?: number;
}

interface WorkspaceTabsState {
  tabs: WorkspaceTab[];
  closedTabs: WorkspaceTab[];
  ensureTab: (tab: WorkspaceTab) => void;
  closeTab: (id: string) => { nextPath: string | null };
  closeOtherTabs: (id: string) => string | null;
  closeTabsToRight: (id: string) => string | null;
  closeAllTabs: () => string;
  reopenLastClosed: () => string | null;
  resetTabs: () => void;
}

const dashboardTab: WorkspaceTab = {
  id: "/dashboard",
  path: "/dashboard",
  title: "Dashboard",
  pinned: true,
  lastActiveAt: 0,
};

const rememberClosed = (closed: WorkspaceTab[], current: WorkspaceTab[]) =>
  [...closed, ...current].filter((tab, index, rows) =>
    !tab.pinned && rows.findIndex((item) => item.id === tab.id) === index,
  ).slice(0, 20);

export const useWorkspaceTabs = create<WorkspaceTabsState>()(
  persist(
    (set, get) => ({
      tabs: [dashboardTab],
      closedTabs: [],
      ensureTab: (tab) => {
        set((state) => {
          const now = Date.now();
          const exact = state.tabs.findIndex((item) => item.id === tab.id);
          if (exact >= 0) {
            return {
              tabs: state.tabs.map((item, index) =>
                index === exact ? { ...item, ...tab, lastActiveAt: now } : item,
              ),
            };
          }

          const grouped = tab.group
            ? state.tabs.findIndex((item) => item.group === tab.group && !item.pinned)
            : -1;
          if (grouped >= 0) {
            const replaced = state.tabs[grouped];
            const tabs = [...state.tabs];
            tabs[grouped] = { ...tab, lastActiveAt: now };
            return {
              tabs,
              closedTabs: rememberClosed([replaced], state.closedTabs),
            };
          }

          return { tabs: [...state.tabs, { ...tab, lastActiveAt: now }] };
        });
      },
      closeTab: (id) => {
        const state = get();
        const index = state.tabs.findIndex((tab) => tab.id === id);
        if (index < 0) return { nextPath: null };
        const target = state.tabs[index];
        if (target.pinned) return { nextPath: null };

        const remaining = state.tabs.filter((tab) => tab.id !== id);
        const next = [...remaining].sort((a, b) => (b.lastActiveAt || 0) - (a.lastActiveAt || 0))[0] ?? dashboardTab;
        set({
          tabs: remaining.length ? remaining : [dashboardTab],
          closedTabs: rememberClosed([target], state.closedTabs),
        });
        return { nextPath: next.path };
      },
      closeOtherTabs: (id) => {
        const state = get();
        const target = state.tabs.find((tab) => tab.id === id);
        if (!target) return null;
        const closing = state.tabs.filter((tab) => !tab.pinned && tab.id !== id);
        set({
          tabs: state.tabs.filter((tab) => tab.pinned || tab.id === id),
          closedTabs: rememberClosed(closing.reverse(), state.closedTabs),
        });
        return target.path;
      },
      closeTabsToRight: (id) => {
        const state = get();
        const index = state.tabs.findIndex((tab) => tab.id === id);
        if (index < 0) return null;
        const closing = state.tabs.slice(index + 1).filter((tab) => !tab.pinned);
        const closingIds = new Set(closing.map((tab) => tab.id));
        set({
          tabs: state.tabs.filter((tab) => !closingIds.has(tab.id)),
          closedTabs: rememberClosed(closing.reverse(), state.closedTabs),
        });
        return state.tabs[index].path;
      },
      closeAllTabs: () => {
        const state = get();
        const closing = state.tabs.filter((tab) => !tab.pinned);
        set({
          tabs: state.tabs.filter((tab) => tab.pinned).length
            ? state.tabs.filter((tab) => tab.pinned)
            : [dashboardTab],
          closedTabs: rememberClosed(closing.reverse(), state.closedTabs),
        });
        return dashboardTab.path;
      },
      reopenLastClosed: () => {
        const state = get();
        const target = state.closedTabs[0];
        if (!target) return null;
        set({
          tabs: state.tabs.some((tab) => tab.id === target.id)
            ? state.tabs
            : [...state.tabs, { ...target, lastActiveAt: Date.now() }],
          closedTabs: state.closedTabs.slice(1),
        });
        return target.path;
      },
      resetTabs: () => set({ tabs: [dashboardTab], closedTabs: [] }),
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
