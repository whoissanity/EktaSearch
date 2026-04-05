// src/components/layout/Navbar.tsx
import { Link, useNavigate } from "react-router-dom";
import { ShoppingCart, Cpu, Search, Menu, X } from "lucide-react";
import { useState } from "react";
import { useCartStore } from "../../store/cartStore";

export default function Navbar() {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [q, setQ] = useState("");
  const { totalItems, setOpen } = useCartStore();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (q.trim()) { navigate(`/search?q=${encodeURIComponent(q.trim())}`); setMenuOpen(false); }
  };

  return (
    <nav className="sticky top-0 z-50 bg-white border-b border-silver-100 shadow-card">
      <div className="max-w-7xl mx-auto px-4 flex items-center gap-4 h-14">

        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 shrink-0 no-underline">
          <Cpu size={20} className="text-accent" />
          <span className="font-semibold text-silver-900 text-sm tracking-tight">
            PC<span className="text-accent">BD</span>
          </span>
        </Link>

        {/* Search bar — desktop */}
        <form onSubmit={handleSearch} className="hidden sm:flex flex-1 max-w-xl">
          <div className="relative w-full">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-silver-400" />
            <input
              className="input pl-9 py-1.5 text-sm"
              placeholder="Search CPUs, GPUs, RAM, storage…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
        </form>

        {/* Nav links */}
        <div className="hidden sm:flex items-center gap-1 ml-auto text-sm">
          <Link to="/builder" className="btn-ghost">PC Builder</Link>
          <Link to="/compare" className="btn-ghost">Compare</Link>
        </div>

        {/* Cart icon */}
        <button onClick={() => setOpen(true)} className="relative btn-ghost" aria-label="Cart">
          <ShoppingCart size={18} />
          {totalItems > 0 && (
            <span className="absolute -top-1 -right-1 bg-accent text-white
                             text-[10px] w-4 h-4 rounded-full flex items-center justify-center font-medium">
              {totalItems}
            </span>
          )}
        </button>

        {/* Mobile menu toggle */}
        <button className="sm:hidden btn-ghost" onClick={() => setMenuOpen((v) => !v)}>
          {menuOpen ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div className="sm:hidden px-4 pb-3 border-t border-silver-100 bg-white space-y-2 pt-2">
          <form onSubmit={handleSearch}>
            <input
              className="input text-sm"
              placeholder="Search parts…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </form>
          <div className="flex gap-2">
            <Link to="/builder" className="btn-secondary text-xs" onClick={() => setMenuOpen(false)}>PC Builder</Link>
            <Link to="/compare" className="btn-secondary text-xs" onClick={() => setMenuOpen(false)}>Compare</Link>
          </div>
        </div>
      )}
    </nav>
  );
}
