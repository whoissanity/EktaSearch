// src/components/cart/CartSidebar.tsx
import { X, ShoppingCart, ExternalLink, Trash2 } from "lucide-react";
import { useCartStore } from "../../store/cartStore";
import { formatBDT } from "../../utils";

export default function CartSidebar() {
  const { cart, open, setOpen, removeItem, clearCart, totalBdt } = useCartStore();

  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-night-950/70 backdrop-blur-sm"
        onClick={() => setOpen(false)}
      />

      <aside
        className="fixed right-0 top-0 h-full w-80 z-50 glass-panel rounded-l-2xl border-l border-white/[0.12]
                   flex flex-col shadow-glass-lg"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.08]">
          <div className="flex items-center gap-2">
            <ShoppingCart size={16} className="text-accent-light" />
            <span className="font-medium text-sm text-zinc-100">Cart ({cart.items.length})</span>
          </div>
          <button onClick={() => setOpen(false)} className="btn-ghost p-1">
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {cart.items.length === 0 && (
            <p className="text-zinc-500 text-sm text-center mt-10">Your cart is empty.</p>
          )}
          {cart.items.map((item, idx) => (
            <div key={idx} className="card-flat p-3 flex gap-3">
              {item.image_url && (
                <img
                  src={item.image_url}
                  alt=""
                  className="w-12 h-12 object-contain rounded-lg bg-white/[0.04] border border-white/[0.06] shrink-0"
                />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-zinc-200 line-clamp-2 leading-snug">
                  {item.product_name}
                </p>
                <p className="text-xs text-zinc-500 mt-0.5">{item.retailer_name}</p>
                <p className="text-sm font-semibold text-zinc-50 mt-1">
                  {formatBDT(item.price_bdt)}
                  {item.quantity > 1 && (
                    <span className="text-xs text-zinc-500 ml-1">×{item.quantity}</span>
                  )}
                </p>
              </div>
              <div className="flex flex-col items-end gap-2 shrink-0">
                <a
                  href={item.product_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent-light hover:text-accent"
                  title="Buy on site"
                >
                  <ExternalLink size={13} />
                </a>
                <button
                  onClick={() => removeItem(item.product_id, item.retailer)}
                  className="text-zinc-600 hover:text-danger transition-colors"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>

        {cart.items.length > 0 && (
          <div className="border-t border-white/[0.08] px-4 py-3 space-y-2">
            <div className="flex justify-between text-sm font-semibold text-zinc-100">
              <span>Estimated total</span>
              <span>{formatBDT(totalBdt)}</span>
            </div>
            <p className="text-xs text-zinc-500">
              Each item opens the retailer's site to complete purchase.
            </p>
            <button onClick={clearCart} className="btn-secondary w-full justify-center text-xs">
              Clear cart
            </button>
          </div>
        )}
      </aside>
    </>
  );
}
