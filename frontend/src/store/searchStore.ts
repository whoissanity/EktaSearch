// src/store/searchStore.ts
import { create } from "zustand";
import type { ProductResult, SearchFilters } from "../types";
import { searchProductsStream } from "../services/api";

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

let searchGen = 0;
let searchAbort: AbortController | null = null;

export const useSearchStore = create<SearchState>((set, get) => ({
  query: "",
  filters: { sort_by: "relevance" },
  results: [],
  total: 0,
  loading: false,
  error: null,

  setQuery: (q) => set({ query: q }),
  setFilters: (f) => set((s) => ({ filters: { ...s.filters, ...f } })),

  runSearch: async () => {
    const { query, filters } = get();
    if (!query.trim()) return;
    searchAbort?.abort();
    const ac = new AbortController();
    searchAbort = ac;
    const signal = ac.signal;
    const gen = ++searchGen;
    set({ loading: true, error: null });
    try {
      const params = {
        q: query.trim(),
        sort_by: filters.sort_by ?? "relevance",
        in_stock_only: !!filters.in_stock_only,
        min_price: filters.min_price,
        max_price: filters.max_price,
        retailers:
          filters.retailers?.length ? filters.retailers.join(",") : undefined,
      };
      const merged = await searchProductsStream(params, filters, {
        signal,
        onChunk: (items) => {
          if (gen !== searchGen) return;
          set({
            results: items,
            total: items.length,
            loading: items.length === 0,
          });
        },
      });
      if (gen !== searchGen) return;
      set({ results: merged, total: merged.length });
    } catch (e: unknown) {
      if (gen !== searchGen) return;
      const aborted =
        (e instanceof DOMException && e.name === "AbortError") ||
        (e instanceof Error && e.name === "AbortError");
      if (aborted) return;
      set({ error: "Search failed. Please try again." });
    } finally {
      if (gen === searchGen) set({ loading: false });
    }
  },
}));
