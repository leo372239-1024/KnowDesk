import { create } from "zustand";

interface UiState {
  collapsed: boolean;
  toggleCollapsed: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  collapsed: false,
  toggleCollapsed: () => set((s) => ({ collapsed: !s.collapsed })),
}));
