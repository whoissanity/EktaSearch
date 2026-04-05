// src/components/cart/CartSidebar.tsx
import { X, ShoppingCart, ExternalLink, Trash2 } from "lucide-react";
import { useCartStore } from "../../store/cartStore";
import { formatBDT } from "../../utils";

export default function CartSidebar() {
  const { cart, open, setOpen, removeItem, clearCart, totalBdt } = useCartStore();

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setOpen(false)} />

      <aside className="fixed right-0 top-0 h-full w-80 bg-white z-50 shadow-panel
                        flex flex-col border-l border-silver-100">

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-silver-100">
          <div className="flex items-center gap-2">
            <ShoppingCart size={16} className="text-accent" />
            <span className="font-medium text-sm">Cart ({cart.items.length})</span>
          </div>
          <button onClick={() => setOpen(false)} className="btn-ghost p-1">
            <X size={16} />
          </button>
        </div>

        {/* Items */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {cart.items.length === 0 && (
            <p className="text-silver-400 text-sm text-center mt-10">Your cart is empty.</p>
          )}
          {cart.items.map((item, idx) => (
            <div key={idx} className="card-flat p-3 flex gap-3">
              {item.image_url && (
                <img src={item.image_url} alt="" className="w-12 h-12 object-contain rounded bg-cream-50 shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-silver-800 line-clamp-2 leading-snug">{item.product_name}</p>
                <p className="text-xs text-silver-400 mt-0.5">{item.retailer_name}</p>
                <p className="text-sm font-semibold text-silver-900 mt-1">
                  {formatBDT(item.price_bdt)}
                  {item.quantity > 1 && <span className="text-xs text-silver-400 ml-1">×{item.quantity}</span>}
                </p>
              </div>
              <div className="flex flex-col items-end gap-2 shrink-0">
                <a href={item.product_url} target="_blank" rel="noopener noreferrer"
                   className="text-accent hover:text-accent-dark" title="Buy on site">
                  <ExternalLink size={13} />
                </a>
                <button onClick={() => removeItem(item.product_id, item.retailer)}
                        className="text-silver-300 hover:text-danger transition-colors">
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        {cart.items.length > 0 && (
          <div className="border-t border-silver-100 px-4 py-3 space-y-2">
            <div className="flex justify-between text-sm font-semibold">
              <span>Estimated total</span>
              <span>{formatBDT(totalBdt)}</span>
            </div>
            <p className="text-xs text-silver-400">
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
