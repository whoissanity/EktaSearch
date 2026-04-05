// src/components/search/ProductCard.tsx
import { ShoppingCart, ExternalLink } from "lucide-react";
import type { ProductResult } from "../../types";
import { formatBDT, truncate } from "../../utils";
import { useCartStore } from "../../store/cartStore";
import { RETAILERS } from "../../types";

interface Props { product: ProductResult; }

export default function ProductCard({ product }: Props) {
  const addItem = useCartStore((s) => s.addItem);

  // Map shop_name back to retailer id for color lookup
  const retailerId = Object.entries(RETAILERS)
    .find(([, m]) => m.name === product.shop_name)?.[0] ?? "";
  const color = RETAILERS[retailerId]?.color ?? "#4A6FA5";

  const savings = product.original_price && product.original_price > product.price
    ? Math.round(((product.original_price - product.price) / product.original_price) * 100)
    : null;

  return (
    <div className="card p-4 flex flex-col gap-3 h-full">
      {/* Image + title row */}
      <div className="flex gap-3">
        <div
          className="w-16 h-16 shrink-0 rounded-lg bg-white/[0.04] border border-white/[0.1]
                        flex items-center justify-center overflow-hidden backdrop-blur-sm"
        >
          {product.image ? (
            <img src={product.image} alt={product.title} className="w-full h-full object-contain" />
          ) : (
            <span className="text-zinc-600 text-xs">No img</span>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-zinc-100 leading-snug line-clamp-3">
            {truncate(product.title, 80)}
          </p>
          <span
            className="inline-block mt-1 text-[10px] font-semibold px-2 py-0.5 rounded-full text-white"
            style={{ backgroundColor: color }}
          >
            {product.shop_name}
          </span>
        </div>
      </div>

      {/* Description */}
      {product.description && (
        <p className="text-xs text-zinc-500 leading-relaxed line-clamp-2">
          {product.description}
        </p>
      )}

      {/* Price row */}
      <div className="flex items-center gap-2 flex-wrap">
        {product.price > 0
          ? <span className="price-low">{formatBDT(product.price)}</span>
          : <span className="text-sm text-zinc-500">Price unavailable</span>}
        {product.original_price && product.original_price > product.price && (
          <span className="text-xs text-zinc-500 line-through">
            {formatBDT(product.original_price)}
          </span>
        )}
        {savings && (
          <span className="text-[10px] bg-emerald-500/15 text-emerald-300 border border-emerald-400/20 px-1.5 py-0.5 rounded-full font-medium">
            -{savings}%
          </span>
        )}
        <span className={`ml-auto ${product.availability ? "badge-instock" : "badge-outstock"}`}>
          {product.availability ? "In stock" : "Out of stock"}
        </span>
      </div>

      {/* Actions */}
      <div className="flex gap-2 mt-auto pt-1">
        <a
          href={product.link}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-secondary flex-1 justify-center text-xs py-1.5"
        >
          <ExternalLink size={12} /> View on site
        </a>
        <button
          disabled={!product.availability || product.price === 0}
          onClick={() => addItem({
            product_id:   product.link,
            product_name: product.title,
            retailer:     retailerId,
            retailer_name: product.shop_name,
            price_bdt:    product.price,
            product_url:  product.link,
            quantity:     1,
            image_url:    product.image,
          })}
          className="btn-primary flex-1 justify-center text-xs py-1.5
                     disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ShoppingCart size={12} /> Add
        </button>
      </div>
    </div>
  );
}
