// src/components/builder/PartPickerModal.tsx
import { useState, useEffect } from "react";
import { X, Search, Loader } from "lucide-react";
import type { BuildSlot, ProductResult } from "../../types";
import { SLOT_LABELS } from "../../types";
import { searchProducts } from "../../services/api";
import { formatBDT, debounce } from "../../utils";
import { useBuilderStore } from "../../store/builderStore";

interface Props {
  slot: BuildSlot;
  onClose: () => void;
}

const SLOT_HINT: Partial<Record<BuildSlot, string>> = {
  cpu: "",
  gpu: "",
  motherboard: "",
  ram: "",
  storage: "",
  psu: "",
  case: "",
  cooler: "",
};
const SLOT_EXAMPLE: Record<BuildSlot, string> = {
  cpu: "e.g. 7600X",
  gpu: "e.g. 4070 Ti",
  motherboard: "e.g. B650",
  ram: "e.g. DDR5 16GB",
  storage: "e.g. NVMe SSD or HDD",
  psu: "e.g. 750W Gold",
  case: "e.g. ATX case",
  cooler: "e.g. AK400",
};

export default function PartPickerModal({ slot, onClose }: Props) {
  const [query, setQuery] = useState(SLOT_HINT[slot] ?? "");
  const [results, setResults] = useState<ProductResult[]>([]);
  const [loading, setLoading] = useState(false);
  const setPart = useBuilderStore((s) => s.setPart);

  const doSearch = debounce(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const res = await searchProducts({ q, category: slot });
      setResults(res.results);
    } finally {
      setLoading(false);
    }
  }, 350);

  useEffect(() => {
    doSearch(query);
  }, [query]);

  const pick = (r: ProductResult) => {
    setPart({
      slot,
      product_id: r.link,
      product_name: r.title,
      price_bdt: r.price,
      retailer: r.shop_name,
      specs: {},
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-night-950/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative glass-panel rounded-2xl w-full max-w-6xl flex flex-col max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.08]">
          <h3 className="text-sm font-semibold text-zinc-100">Choose {SLOT_LABELS[slot]}</h3>
          <button onClick={onClose} className="btn-ghost p-1">
            <X size={16} />
          </button>
        </div>

        <div className="px-4 py-2 border-b border-white/[0.08]">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              autoFocus
              className="input pl-9 text-sm"
              placeholder={`Search ${SLOT_LABELS[slot].toLowerCase()} (${SLOT_EXAMPLE[slot]})`}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>

        <div className="overflow-y-auto flex-1 px-4 py-2">
          {loading && (
            <div className="flex justify-center py-8 text-zinc-600">
              <Loader size={20} className="animate-spin" />
            </div>
          )}
          {!loading && query && results.length === 0 && (
            <p className="text-sm text-zinc-500 text-center py-8">No results.</p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {results.map((r, i) => (
            <div key={i} className="card-flat p-3 flex items-center gap-3 min-h-[96px]">
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
                  <button onClick={() => pick(r)} className="btn-primary text-xs py-1 px-3 mt-1">
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
      </div>
    </div>
  );
}
