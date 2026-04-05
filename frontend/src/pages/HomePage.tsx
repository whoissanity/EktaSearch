import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Cpu, BarChart2, ShoppingCart, Wrench } from "lucide-react";
import { RETAILERS } from "../types";

const QUICK = ["RTX 4070", "Ryzen 5 7600X", "DDR5 RAM", "NVMe SSD", "ATX Case"];

export default function HomePage() {
  const [q, setQ] = useState("");
  const navigate = useNavigate();

  const go = (term: string) =>
    navigate(`/search?q=${encodeURIComponent(term)}`);

  return (
    <div className="max-w-3xl mx-auto px-4 py-16 text-center space-y-10">
      {/* Hero */}
      <div className="space-y-3">
        <div className="flex justify-center">
          <Cpu size={36} className="text-accent" />
        </div>
        <h1 className="text-3xl font-semibold text-silver-900">PC Bangladesh</h1>
        <p className="text-silver-500 text-base">
          Search PC parts across {Object.keys(RETAILERS).length} retailers in one go.
          Compare prices, build your rig, save money.
        </p>
      </div>

      {/* Search box */}
      <form
        onSubmit={(e) => { e.preventDefault(); if (q.trim()) go(q.trim()); }}
        className="flex gap-2 max-w-xl mx-auto"
      >
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-silver-400" />
          <input
            autoFocus
            className="input pl-9 py-3 text-base"
            placeholder="Search any PC part…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-primary px-6 py-3 text-base">
          Search
        </button>
      </form>

      {/* Quick searches */}
      <div className="flex flex-wrap justify-center gap-2">
        {QUICK.map((term) => (
          <button
            key={term}
            onClick={() => go(term)}
            className="badge-retailer cursor-pointer hover:bg-silver-200 transition-colors px-3 py-1.5 text-sm"
          >
            {term}
          </button>
        ))}
      </div>

      {/* Feature cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-left">
        {[
          { icon: <Search size={18} />, title: "Unified search", desc: "One query hits all 8 retailers at once." },
          { icon: <BarChart2 size={18} />, title: "Price compare", desc: "See every shop's price side by side." },
          { icon: <Wrench size={18} />, title: "PC builder", desc: "Pick parts, check compatibility, see wattage." },
        ].map((f) => (
          <div key={f.title} className="card p-4 space-y-2">
            <div className="text-accent">{f.icon}</div>
            <p className="font-medium text-silver-800 text-sm">{f.title}</p>
            <p className="text-xs text-silver-500">{f.desc}</p>
          </div>
        ))}
      </div>

      {/* Shop pills */}
      <div className="space-y-2">
        <p className="text-xs text-silver-400 uppercase tracking-wide">Shops covered</p>
        <div className="flex flex-wrap justify-center gap-2">
          {Object.entries(RETAILERS).map(([id, meta]) => (
            <span
              key={id}
              className="text-xs px-3 py-1 rounded-full text-white font-medium"
              style={{ backgroundColor: meta.color }}
            >
              {meta.name}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
