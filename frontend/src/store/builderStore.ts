// src/store/builderStore.ts
import { create } from "zustand";
import type { PCBuild, BuildPart, BuildAnalysis, BuildSlot } from "../types";
import { analyzeBuild, saveBuild, loadBuild } from "../services/api";

interface BuilderState {
  build: PCBuild;
  analysis: BuildAnalysis | null;
  analyzing: boolean;
  saving: boolean;
  budget: number;
  totalBdt: number;
  budgetRemaining: number;
  setPart:      (part: BuildPart) => void;
  removePart:   (slot: BuildSlot) => void;
  setBuildName: (name: string) => void;
  setBudget:    (bdt: number) => void;
  analyze:      () => Promise<void>;
  save:         () => Promise<string | null>;
  loadBuild:    (id: string) => Promise<void>;
  reset:        () => void;
}

const empty = (): PCBuild => ({ name: "My Build", parts: [] });
const total = (parts: BuildPart[]) => parts.reduce((s, p) => s + p.price_bdt, 0);

export const useBuilderStore = create<BuilderState>((set, get) => ({
  build: empty(), analysis: null, analyzing: false, saving: false,
  budget: 0, totalBdt: 0, budgetRemaining: 0,

  setBuildName: (name) => set((s) => ({ build: { ...s.build, name } })),
  setBudget:    (bdt)  => set((s) => ({ budget: bdt, budgetRemaining: bdt - s.totalBdt })),

  setPart: (part) => {
    set((s) => {
      const parts = [...s.build.parts.filter((p) => p.slot !== part.slot), part];
      const t = total(parts);
      return { build: { ...s.build, parts }, totalBdt: t, budgetRemaining: s.budget - t };
    });
    get().analyze();
  },

  removePart: (slot) => {
    set((s) => {
      const parts = s.build.parts.filter((p) => p.slot !== slot);
      const t = total(parts);
      return { build: { ...s.build, parts }, totalBdt: t, budgetRemaining: s.budget - t };
    });
    get().analyze();
  },

  analyze: async () => {
    const { build } = get();
    if (!build.parts.length) { set({ analysis: null }); return; }
    set({ analyzing: true });
    try { set({ analysis: await analyzeBuild(build) }); }
    catch { /* swallow — compat is non-critical */ }
    finally { set({ analyzing: false }); }
  },

  save: async () => {
    set({ saving: true });
    try {
      const { build_id } = await saveBuild(get().build);
      set((s) => ({ build: { ...s.build, id: build_id } }));
      return build_id;
    } finally { set({ saving: false }); }
  },

  loadBuild: async (id) => {
    const build = await loadBuild(id);
    set({ build, totalBdt: total(build.parts) });
    get().analyze();
  },

  reset: () => set({ build: empty(), analysis: null, totalBdt: 0, budgetRemaining: 0 }),
}));
