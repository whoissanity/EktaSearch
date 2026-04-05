// src/store/searchStore.ts
import { create } from "zustand";
import type { ProductResult, SearchFilters } from "../types";
import { searchProducts } from "../services/api";

interface SearchState {
  query: string;
  filters: SearchFilters;
  results: ProductResult[];
  total: number;
  loading: boolean;
  error: string | null;
  setQuery: (q: string) => void;
  setFilters: (f: Partial<SearchFilters>) => void;
  runSearch: () => Promise<void>;
}

export const useSearchStore = create<SearchState>((set, get) => ({
  query: "", filters: { sort_by: "price_asc" },
  results: [], total: 0, loading: false, error: null,

  setQuery:   (q) => set({ query: q }),
  setFilters: (f) => set((s) => ({ filters: { ...s.filters, ...f } })),

  runSearch: async () => {
    const { query } = get();
    if (!query.trim()) return;
    set({ loading: true, error: null });
    try {
      const res = await searchProducts(query);
      set({ results: res.results, total: res.total });
    } catch {
      set({ error: "Search failed. Please try again." });
    } finally {
      set({ loading: false });
    }
  },
}));
