import { useState } from "react";
import { Search, Loader, ExternalLink, CheckCircle, XCircle } from "lucide-react";
import axios from "axios";
import { formatBDT } from "../utils";
import { RETAILERS } from "../types";

interface ProductRow {
  title: string;
  price: number;
  original_price?: number;
  link: string;
  image?: string;
  shop_name: string;
  availability: boolean;
}

export default function ComparePage() {
  const [q, setQ] = useState("");
  const [groups, setGroups] = useState<ProductRow[][]>([]);
  const [loading, setLoading] = useState(false);

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!q.trim()) return;
    setLoading(true);
    try {
      const { data } = await axios.get("/api/compare", { params: { q } });
      setGroups(data.groups ?? []);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      <div>
        <h1>Price Compare</h1>
        <p className="text-silver-500 text-sm mt-1">
          Find the same product across all shops and compare side by side.
        </p>
      </div>

      <form onSubmit={run} className="flex gap-2 max-w-lg">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-silver-400" />
          <input
            className="input pl-9"
            placeholder="e.g. RTX 4070 Ti Super"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <button className="btn-primary" type="submit">Compare</button>
      </form>

      {loading && (
        <div className="flex justify-center py-12 text-silver-300">
          <Loader size={24} className="animate-spin" />
        </div>
      )}

      {!loading && groups.map((group, gi) => {
        const sorted = [...group].sort((a, b) => a.price - b.price);
        const low    = sorted.find((r) => r.availability)?.price ?? 0;
        return (
          <div key={gi} className="card overflow-hidden">
            {/* Product header */}
            <div className="flex items-center gap-3 p-4 border-b border-silver-100 bg-cream-50">
              {sorted[0]?.image && (
                <img src={sorted[0].image} alt="" className="w-14 h-14 object-contain rounded" />
              )}
              <div>
                <p className="font-medium text-silver-900 text-sm">{sorted[0]?.title}</p>
                <p className="text-xs text-silver-400 mt-0.5">{sorted.length} shops listed</p>
              </div>
            </div>

            {/* Price rows */}
            <div className="divide-y divide-silver-50">
              {sorted.map((r, i) => (
                <div key={i} className={`flex items-center gap-3 px-4 py-3
                     ${r.price === low && r.availability ? "bg-green-50/60" : ""}`}>
                  {/* Shop badge */}
                  <span
                    className="text-xs font-medium px-2 py-0.5 rounded-full text-white shrink-0"
                    style={{ backgroundColor: Object.values(RETAILERS).find(m => m.name === r.shop_name)?.color ?? "#888" }}
                  >
                    {r.shop_name}
                  </span>

                  {/* Stock */}
                  <span className="shrink-0">
                    {r.availability
                      ? <CheckCircle size={14} className="text-success" />
                      : <XCircle    size={14} className="text-silver-300" />}
                  </span>

                  {/* Price */}
                  <span className={`font-semibold text-sm flex-1
                       ${r.price === low && r.availability ? "text-success" : "text-silver-800"}`}>
                    {r.price > 0 ? formatBDT(r.price) : "N/A"}
                    {r.original_price && r.original_price > r.price && (
                      <span className="text-xs text-silver-400 line-through ml-2">
                        {formatBDT(r.original_price)}
                      </span>
                    )}
                  </span>

                  {/* Link */}
                  <a href={r.link} target="_blank" rel="noopener noreferrer"
                     className="btn-ghost py-1 px-2 text-xs shrink-0">
                    <ExternalLink size={12} /> View
                  </a>
                </div>
              ))}
            </div>
          </div>
        );
      })}

      {!loading && groups.length === 0 && q && (
        <p className="text-silver-400 text-sm text-center py-8">No results found.</p>
      )}
    </div>
  );
}
