import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Loader, Search } from "lucide-react";
import { searchProducts } from "../services/api";
import type { BuildSlot, ProductResult } from "../types";
import { COMPONENT_ID_SLOT, SLOT_LABELS } from "../types";
import { formatBDT, debounce } from "../utils";
import { useBuilderStore } from "../store/builderStore";

const SLOT_EXAMPLE: Record<BuildSlot, string> = {
  cpu: "7600X",
  gpu: "4070 Ti",
  motherboard: "B650",
  ram: "DDR5 16GB",
  storage: "NVMe SSD or HDD",
  psu: "750W Gold",
  case: "ATX case",
  cooler: "AK400",
};

export default function BuilderChoosePage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const setPart = useBuilderStore((s) => s.setPart);
  const componentId = Number(params.get("component_id") ?? "0");
  const slot = COMPONENT_ID_SLOT[componentId];
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ProductResult[]>([]);
  const [loading, setLoading] = useState(false);

  const title = useMemo(() => (slot ? SLOT_LABELS[slot] : "Component"), [slot]);

  const runSearch = debounce(async (q: string, s: BuildSlot) => {
    setLoading(true);
    try {
      const res = await searchProducts({ q, category: s });
      setResults(res.results);
    } finally {
      setLoading(false);
    }
  }, 250);

  useEffect(() => {
    if (!slot) return;
    runSearch(query, slot);
  }, [query, slot]);

  if (!slot) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <p className="text-zinc-400 text-sm">Invalid component id.</p>
        <Link className="text-cyan-300 text-sm" to="/builder">Back to builder</Link>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate("/builder")} className="btn-ghost text-xs">
            <ArrowLeft size={14} /> Back
          </button>
          <h1 className="text-lg font-semibold text-zinc-50">Choose {title}</h1>
        </div>
        <p className="text-xs text-zinc-500">{results.length} items</p>
      </div>

      <div className="relative mb-4">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
        <input
          autoFocus
          className="input pl-9 text-sm w-full"
          placeholder={`Filter ${title.toLowerCase()} (e.g. ${SLOT_EXAMPLE[slot]})`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {loading && (
        <div className="flex justify-center py-8 text-zinc-600">
          <Loader size={20} className="animate-spin" />
        </div>
      )}

      {!loading && results.length === 0 && (
        <p className="text-sm text-zinc-500 text-center py-8">No results found for this category.</p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {results.map((r, i) => (
          <div key={r.link + i} className="card-flat p-3 flex items-center gap-3 min-h-[96px]">
            {r.image && (
              <img
                src={r.image}
                alt=""
                className="w-10 h-10 object-contain rounded-lg bg-white/[0.04] border border-white/[0.06] shrink-0"
              />
            )}
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-zinc-100 line-clamp-2">{r.title}</p>
              <p className="text-xs text-zinc-500 mt-0.5">{r.shop_name}</p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-sm font-semibold text-zinc-200">{formatBDT(r.price)}</p>
              {r.availability ? (
                <button
                  onClick={() => {
                    setPart({
                      slot,
                      product_id: r.link,
                      product_name: r.title,
                      price_bdt: r.price,
                      retailer: r.shop_name,
                      specs: {},
                    });
                    navigate("/builder");
                  }}
                  className="btn-primary text-xs py-1 px-3 mt-1"
                >
                  Select
                </button>
              ) : (
                <span className="badge-outstock text-xs">Out of stock</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
