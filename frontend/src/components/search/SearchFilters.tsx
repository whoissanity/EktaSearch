// src/components/search/SearchFilters.tsx
import { useSearchStore } from "../../store/searchStore";
import { debounce } from "../../utils";

const debouncedRunSearch = debounce(() => {
  useSearchStore.getState().runSearch();
}, 280);

export default function SearchFilters() {
  const { filters, setFilters } = useSearchStore();
  const apply = (f: Parameters<typeof setFilters>[0]) => {
    setFilters(f);
    debouncedRunSearch();
  };

  return (
    <div className="space-y-5 text-sm">
      <div>
        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-2">Sort</p>
        <select className="input text-sm"
          value={filters.sort_by ?? "price_asc"}
          onChange={(e) => apply({ sort_by: e.target.value as "price_asc"|"price_desc"|"relevance" })}>
          <option value="price_asc">Price: Low → High</option>
          <option value="price_desc">Price: High → Low</option>
          <option value="relevance">Relevance</option>
        </select>
      </div>

      <div>
        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-2">Price (৳)</p>
        <div className="flex gap-2">
          <input type="number" className="input text-sm" placeholder="Min"
            value={filters.min_price ?? ""}
            onChange={(e) => apply({ min_price: e.target.value === "" ? undefined : Number(e.target.value) })} />
          <input type="number" className="input text-sm" placeholder="Max"
            value={filters.max_price ?? ""}
            onChange={(e) => apply({ max_price: e.target.value === "" ? undefined : Number(e.target.value) })} />
        </div>
      </div>

      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          className="rounded border-white/20 bg-white/5 text-accent focus:ring-accent/40"
          checked={!!filters.in_stock_only}
          onChange={(e) => apply({ in_stock_only: e.target.checked })}
        />
        <span className="text-zinc-300">In stock only</span>
      </label>
    </div>
  );
}
