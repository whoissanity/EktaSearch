// Client-side filter/sort aligned with backend search_service (post-fetch).
import type { ProductResult, SearchFilters } from "../types";

export function applySearchFilters(
  items: ProductResult[],
  f: SearchFilters
): ProductResult[] {
  let out = items;
  if (f.in_stock_only) {
    out = out.filter((r) => r.availability);
  }
  if (f.min_price != null && !Number.isNaN(f.min_price)) {
    out = out.filter((r) => r.price >= f.min_price!);
  }
  if (f.max_price != null && !Number.isNaN(f.max_price)) {
    out = out.filter((r) => r.price <= f.max_price!);
  }
  return out;
}

function stockRank(a: ProductResult, b: ProductResult): number {
  const sa = !a.availability ? 1 : 0;
  const sb = !b.availability ? 1 : 0;
  return sa - sb;
}

export function sortSearchResults(
  items: ProductResult[],
  sortBy: SearchFilters["sort_by"]
): ProductResult[] {
  const arr = [...items];
  const sb = sortBy ?? "relevance";
  if (sb === "price_desc") {
    arr.sort((a, b) => {
      const s = stockRank(a, b);
      if (s !== 0) return s;
      return b.price - a.price;
    });
  } else if (sb === "price_asc") {
    arr.sort((a, b) => {
      const s = stockRank(a, b);
      if (s !== 0) return s;
      return a.price - b.price;
    });
  } else {
    arr.sort((a, b) => {
      const s = stockRank(a, b);
      if (s !== 0) return s;
      const dr = (b.relevance_score ?? 0) - (a.relevance_score ?? 0);
      if (dr !== 0) return dr;
      return a.price - b.price;
    });
  }
  return arr;
}
