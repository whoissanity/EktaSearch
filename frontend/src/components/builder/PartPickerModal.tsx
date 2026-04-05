// src/components/builder/PartPickerModal.tsx
import { useState, useEffect } from "react";
import { X, Search, Loader } from "lucide-react";
import type { BuildSlot, ProductResult } from "../../types";
import { SLOT_LABELS } from "../../types";
import { searchProducts } from "../../services/api";
import { formatBDT, debounce } from "../../utils";
import { useBuilderStore } from "../../store/builderStore";

interface Props { slot: BuildSlot; onClose: () => void; }

// Map slot → keyword prefix for smarter searches
const SLOT_HINT: Partial<Record<BuildSlot, string>> = {
  cpu: "processor", gpu: "graphics card", motherboard: "motherboard",
  ram: "DDR5 RAM", storage: "SSD NVMe", psu: "power supply",
  case: "ATX case", cooler: "CPU cooler",
};

export default function PartPickerModal({ slot, onClose }: Props) {
  const [query, setQuery]   = useState(SLOT_HINT[slot] ?? "");
  const [results, setResults] = useState<ProductResult[]>([]);
  const [loading, setLoading] = useState(false);
  const setPart = useBuilderStore((s) => s.setPart);

  const doSearch = debounce(async (q: string) => {
    if (!q.trim()) { setResults([]); return; }
    setLoading(true);
    try {
      const res = await searchProducts(q);
      setResults(res.results.slice(0, 24));
    } finally {
      setLoading(false);
    }
  }, 350);

  useEffect(() => { doSearch(query); }, [query]);

  const pick = (r: ProductResult) => {
    setPart({
      slot,
      product_id:   r.link,           // use URL as unique ID
      product_name: r.title,
      price_bdt:    r.price,
      retailer:     r.shop_name,
      specs:        {},
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-panel w-full max-w-lg
                      flex flex-col max-h-[82vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-silver-100">
          <h3 className="text-sm font-semibold">Choose {SLOT_LABELS[slot]}</h3>
          <button onClick={onClose} className="btn-ghost p-1"><X size={16} /></button>
        </div>

        {/* Search */}
        <div className="px-4 py-2 border-b border-silver-100">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-silver-400" />
            <input
              autoFocus
              className="input pl-9 text-sm"
              placeholder={`Search ${SLOT_LABELS[slot].toLowerCase()}…`}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>

        {/* Results */}
        <div className="overflow-y-auto flex-1 px-4 py-2 space-y-2">
          {loading && (
            <div className="flex justify-center py-8 text-silver-300">
              <Loader size={20} className="animate-spin" />
            </div>
          )}
          {!loading && query && results.length === 0 && (
            <p className="text-sm text-silver-400 text-center py-8">No results.</p>
          )}
          {results.map((r, i) => (
            <div key={i} className="card-flat p-3 flex items-center gap-3">
              {r.image && (
                <img src={r.image} alt="" className="w-10 h-10 object-contain rounded bg-cream-50 shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-silver-900 line-clamp-2">{r.title}</p>
                <p className="text-xs text-silver-400 mt-0.5">{r.shop_name}</p>
              </div>
              <div className="text-right shrink-0">
                <p className="text-sm font-semibold text-silver-800">{formatBDT(r.price)}</p>
                {r.availability
                  ? <button onClick={() => pick(r)} className="btn-primary text-xs py-1 px-3 mt-1">Select</button>
                  : <span className="badge-outstock text-xs">Out of stock</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
