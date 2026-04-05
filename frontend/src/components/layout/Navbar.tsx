// src/components/layout/Navbar.tsx
import { Link, useNavigate } from "react-router-dom";
import { ShoppingCart, Search, Menu, X } from "lucide-react";
import EktaSearchWordmark from "../brand/EktaSearchWordmark";
import { useState } from "react";
import { useCartStore } from "../../store/cartStore";

export default function Navbar() {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [q, setQ] = useState("");
  const { totalItems, setOpen } = useCartStore();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (q.trim()) {
      navigate(`/search?q=${encodeURIComponent(q.trim())}`);
      setMenuOpen(false);
    }
  };

  return (
    <nav className="sticky top-0 z-50 glass-nav">
      <div className="max-w-7xl mx-auto px-4 flex items-center gap-4 h-14">
        <Link to="/" className="flex items-center gap-2 shrink-0 no-underline">
          <Search size={20} className="text-cyan-400 shrink-0" strokeWidth={2.25} />
          <EktaSearchWordmark size="sm" />
        </Link>

        <form onSubmit={handleSearch} className="hidden sm:flex flex-1 max-w-xl">
          <div className="relative w-full">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              className="input pl-9 py-1.5 text-sm"
              placeholder="Search CPUs, GPUs, RAM, storage…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
        </form>

        <div className="hidden sm:flex items-center gap-1 ml-auto text-sm">
          <Link to="/builder" className="btn-ghost">
            PC Builder
          </Link>
          <Link to="/compare" className="btn-ghost">
            Compare
          </Link>
        </div>

        <button onClick={() => setOpen(true)} className="relative btn-ghost" aria-label="Cart">
          <ShoppingCart size={18} />
          {totalItems > 0 && (
            <span
              className="absolute -top-1 -right-1 bg-gradient-to-br from-accent-light to-accent text-white
                             text-[10px] w-4 h-4 rounded-full flex items-center justify-center font-medium shadow-md shadow-accent/40"
            >
              {totalItems}
            </span>
          )}
        </button>

        <button className="sm:hidden btn-ghost" onClick={() => setMenuOpen((v) => !v)}>
          {menuOpen ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>

      {menuOpen && (
        <div className="sm:hidden px-4 pb-3 border-t border-white/[0.08] bg-night-950/60 backdrop-blur-xl space-y-2 pt-2">
          <form onSubmit={handleSearch}>
            <input
              className="input text-sm"
              placeholder="Search parts…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </form>
          <div className="flex gap-2">
            <Link
              to="/builder"
              className="btn-secondary text-xs"
              onClick={() => setMenuOpen(false)}
            >
              PC Builder
            </Link>
            <Link
              to="/compare"
              className="btn-secondary text-xs"
              onClick={() => setMenuOpen(false)}
            >
              Compare
            </Link>
          </div>
        </div>
      )}
    </nav>
  );
}
