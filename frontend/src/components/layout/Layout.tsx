import { Outlet } from "react-router-dom";
import { useEffect } from "react";
import Navbar from "./Navbar";
import CartSidebar from "../cart/CartSidebar";
import { useCartStore } from "../../store/cartStore";

export default function Layout() {
  const fetchCart = useCartStore((s) => s.fetchCart);
  useEffect(() => {
    fetchCart();
  }, []);

  return (
    <div className="relative min-h-screen flex flex-col bg-night-950 text-zinc-300">
      {/* Liquid-style ambient background */}
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none" aria-hidden>
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_90%_60%_at_50%_-30%,rgba(74,111,165,0.45),transparent_55%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_50%_at_100%_50%,rgba(139,92,246,0.12),transparent_50%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_40%_at_0%_80%,rgba(34,211,238,0.08),transparent_45%)]" />
        <div
          className="absolute -top-32 left-[10%] h-[420px] w-[420px] rounded-full bg-accent/30 blur-[100px] animate-blob"
        />
        <div
          className="absolute top-1/3 -right-24 h-[380px] w-[380px] rounded-full bg-violet-500/25 blur-[110px] animate-blob-slow animation-delay-2000"
        />
        <div
          className="absolute bottom-0 left-1/3 h-[320px] w-[320px] rounded-full bg-cyan-400/20 blur-[90px] animate-blob animation-delay-4000"
        />
        <div
          className="absolute inset-0 opacity-[0.35] mix-blend-overlay"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
            backgroundSize: "180px 180px",
          }}
        />
      </div>

      <Navbar />
      <main className="relative z-0 flex-1">
        <Outlet />
      </main>
      <CartSidebar />
      <footer className="relative z-0 glass-footer py-6 mt-12">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-zinc-500">
          EktaSearch — A free, open tool to help you find the best prices.
          We don't sell anything — all purchases happen on the retailer's site.
        </div>
      </footer>
    </div>
  );
}
