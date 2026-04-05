import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, BarChart2, Wrench } from "lucide-react";
import { RETAILERS } from "../types";
import EktaSearchWordmark from "../components/brand/EktaSearchWordmark";
import { useTypingCycle } from "../hooks/useTypingCycle";

const QUICK = ["RTX 4070", "Ryzen 5 7600X", "DDR5 RAM", "NVMe SSD", "ATX Case"];

const HERO_TAGLINES = [
  "EktaSearch All Products",
  "Find Products from major retailers without the hassle of multiple tabs",
] as const;

export default function HomePage() {
  const [q, setQ] = useState("");
  const navigate = useNavigate();
  const tagline = useTypingCycle(HERO_TAGLINES, { typeMs: 36, deleteMs: 20, holdMs: 2800 });

  const go = (term: string) => navigate(`/search?q=${encodeURIComponent(term)}`);

  return (
    <div className="max-w-3xl mx-auto px-4 py-16 text-center space-y-10">
      <div className="space-y-5">
        <div className="flex justify-center">
          <div className="glass rounded-2xl p-4 inline-flex">
            <Search size={36} className="text-cyan-400" strokeWidth={2} />
          </div>
        </div>
        <h1 className="m-0">
          <EktaSearchWordmark size="hero" />
        </h1>
        <p
          className="text-zinc-400 text-base sm:text-lg max-w-2xl mx-auto min-h-[4.5rem] sm:min-h-[3.5rem] flex items-center justify-center gap-0.5 px-2 leading-snug"
          aria-live="polite"
        >
          <span className="text-zinc-300">{tagline}</span>
          <span
            className="inline-block w-0.5 h-[1.15em] shrink-0 rounded-sm bg-cyan-400/90 animate-pulse"
            aria-hidden
          />
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) go(q.trim());
        }}
        className="flex flex-col sm:flex-row gap-2 max-w-xl mx-auto"
      >
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
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

      <div className="flex flex-wrap justify-center gap-2">
        {QUICK.map((term) => (
          <button
            key={term}
            onClick={() => go(term)}
            className="badge-retailer cursor-pointer px-3 py-1.5 text-sm"
          >
            {term}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-left">
        {[
          { icon: <Search size={18} />, title: "Unified search", desc: "One query hits all 8 retailers at once." },
          { icon: <BarChart2 size={18} />, title: "Price compare", desc: "See every shop's price side by side." },
          { icon: <Wrench size={18} />, title: "PC builder", desc: "Pick parts, check compatibility, see wattage." },
        ].map((f) => (
          <div key={f.title} className="card p-4 space-y-2">
            <div className="text-accent-light">{f.icon}</div>
            <p className="font-medium text-zinc-100 text-sm">{f.title}</p>
            <p className="text-xs text-zinc-500">{f.desc}</p>
          </div>
        ))}
      </div>

      <div className="space-y-2">
        <p className="text-xs text-zinc-500 uppercase tracking-wide">Shops covered</p>
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
