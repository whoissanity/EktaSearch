import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { Loader, AlertCircle, SlidersHorizontal } from "lucide-react";
import { useSearchStore } from "../store/searchStore";
import ProductCard from "../components/search/ProductCard";
import SearchFilters from "../components/search/SearchFilters";
import { useState } from "react";

export default function SearchPage() {
  const [params] = useSearchParams();
  const query = params.get("q") ?? "";
  const { setQuery, runSearch, results, total, loading, error } = useSearchStore();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const ran = useRef("");

  useEffect(() => {
    if (query && query !== ran.current) {
      ran.current = query;
      setQuery(query);
      runSearch();
    }
  }, [query]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-silver-900">
            {loading ? "Searching…" : `${total} results for "${query}"`}
          </h1>
          <p className="text-xs text-silver-400 mt-0.5">Searched across 8 Bangladeshi retailers</p>
        </div>
        <button
          onClick={() => setFiltersOpen((v) => !v)}
          className="btn-secondary sm:hidden"
        >
          <SlidersHorizontal size={14} /> Filters
        </button>
      </div>

      <div className="flex gap-6">
        {/* Sidebar filters — desktop always visible, mobile toggleable */}
        <aside className={`w-52 shrink-0 ${filtersOpen ? "block" : "hidden"} sm:block`}>
          <SearchFilters />
        </aside>

        {/* Results grid */}
        <div className="flex-1 min-w-0">
          {loading && (
            <div className="flex justify-center items-center py-24 text-silver-300">
              <Loader size={28} className="animate-spin" />
            </div>
          )}
          {!loading && error && (
            <div className="flex items-center gap-2 text-danger text-sm py-8 justify-center">
              <AlertCircle size={16} /> {error}
            </div>
          )}
          {!loading && !error && results.length === 0 && query && (
            <p className="text-silver-400 text-sm text-center py-16">
              No results found for "{query}". Try a different search term.
            </p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {results.map((product, i) => (
              <ProductCard key={product.link + i} product={product} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
