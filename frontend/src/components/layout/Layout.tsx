import { Outlet } from "react-router-dom";
import { useEffect } from "react";
import Navbar from "./Navbar";
import CartSidebar from "../cart/CartSidebar";
import { useCartStore } from "../../store/cartStore";

export default function Layout() {
  const fetchCart = useCartStore((s) => s.fetchCart);
  useEffect(() => { fetchCart(); }, []);

  return (
    <div className="min-h-screen flex flex-col bg-cream-100">
      <Navbar />
      <main className="flex-1">
        <Outlet />
      </main>
      <CartSidebar />
      <footer className="border-t border-silver-100 bg-white py-6 mt-12">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-silver-400">
          PC Bangladesh — A free, open tool to help you find the best prices.
          We don't sell anything — all purchases happen on the retailer's site.
        </div>
      </footer>
    </div>
  );
}
