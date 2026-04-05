import { useEffect, useRef, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Loader, AlertCircle, SlidersHorizontal, ChevronLeft, ChevronRight } from "lucide-react";
import { useSearchStore } from "../store/searchStore";
import ProductCard from "../components/search/ProductCard";
import SearchFilters from "../components/search/SearchFilters";

const RESULTS_PER_PAGE = 24;

export default function SearchPage() {
  const [params] = useSearchParams();
  const query = params.get("q") ?? "";
  const { setQuery, runSearch, results, total, loading, error } = useSearchStore();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [uiPage, setUiPage] = useState(1);
  const ran = useRef("");

  useEffect(() => {
    setUiPage(1);
  }, [query]);

  const pageCount = Math.max(1, Math.ceil(results.length / RESULTS_PER_PAGE));
  const currentPage = Math.min(uiPage, pageCount);
  const pageSlice = useMemo(
    () =>
      results.slice(
        (currentPage - 1) * RESULTS_PER_PAGE,
        currentPage * RESULTS_PER_PAGE
      ),
    [results, currentPage]
  );

  useEffect(() => {
    if (uiPage > pageCount) setUiPage(pageCount);
  }, [uiPage, pageCount]);

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
          <h1 className="text-lg font-semibold text-zinc-50">
            {loading && results.length === 0
              ? "Searching…"
              : `${total} result${total === 1 ? "" : "s"} for "${query}"`}
          </h1>
          <p className="text-xs text-zinc-500 mt-0.5">
            Searched across 8 Bangladeshi retailers
            {pageCount > 1 && !loading && (
              <span className="text-zinc-400">
                {" "}
                · Page {currentPage} of {pageCount}
              </span>
            )}
          </p>
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
          <div className="glass p-4 rounded-xl sm:sticky sm:top-[4.5rem]">
            <SearchFilters />
          </div>
        </aside>

        {/* Results grid */}
        <div className="flex-1 min-w-0">
          {loading && results.length === 0 && (
            <div className="flex justify-center items-center py-24 text-zinc-600">
              <Loader size={28} className="animate-spin" />
            </div>
          )}
          {loading && results.length > 0 && (
            <p className="text-xs text-zinc-500 mb-3 flex items-center gap-2">
              <Loader size={14} className="animate-spin shrink-0" />
              Loading more pages from retailers…
            </p>
          )}
          {!loading && error && (
            <div className="flex items-center gap-2 text-danger text-sm py-8 justify-center">
              <AlertCircle size={16} /> {error}
            </div>
          )}
          {!loading && !error && results.length === 0 && query && (
            <p className="text-zinc-500 text-sm text-center py-16">
              No results found for "{query}". Try a different search term.
            </p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {pageSlice.map((product) => (
              <ProductCard
                key={`${product.shop_name}|${product.link}`}
                product={product}
              />
            ))}
          </div>

          {pageCount > 1 && results.length > 0 && (
            <nav
              className="mt-8 flex flex-wrap items-center justify-center gap-2"
              aria-label="Result pages"
            >
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-1 px-3 py-1.5 text-sm disabled:opacity-40"
                disabled={currentPage <= 1}
                onClick={() => setUiPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft size={16} /> Previous
              </button>
              <div className="flex flex-wrap items-center justify-center gap-1">
                {(() => {
                  const nums =
                    pageCount <= 9
                      ? Array.from({ length: pageCount }, (_, i) => i + 1)
                      : [
                          ...new Set(
                            [
                              1,
                              pageCount,
                              currentPage - 1,
                              currentPage,
                              currentPage + 1,
                            ].filter((n) => n >= 1 && n <= pageCount)
                          ),
                        ].sort((a, b) => a - b);
                  return nums.map((n, idx) => {
                    const prev = nums[idx - 1];
                    const showEllipsis = idx > 0 && prev !== undefined && n - prev > 1;
                    return (
                      <span key={n} className="inline-flex items-center gap-1">
                        {showEllipsis && (
                          <span className="px-1 text-zinc-600 text-sm">…</span>
                        )}
                        <button
                          type="button"
                          className={`min-w-[2.25rem] px-2 py-1.5 rounded-lg text-sm transition-colors ${
                            n === currentPage
                              ? "bg-violet-600 text-white"
                              : "bg-white/[0.06] text-zinc-300 hover:bg-white/[0.1]"
                          }`}
                          onClick={() => setUiPage(n)}
                        >
                          {n}
                        </button>
                      </span>
                    );
                  });
                })()}
              </div>
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-1 px-3 py-1.5 text-sm disabled:opacity-40"
                disabled={currentPage >= pageCount}
                onClick={() => setUiPage((p) => Math.min(pageCount, p + 1))}
              >
                Next <ChevronRight size={16} />
              </button>
            </nav>
          )}
        </div>
      </div>
    </div>
  );
}
