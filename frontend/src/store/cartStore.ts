// src/store/cartStore.ts
import { create } from "zustand";
import type { Cart, CartItem } from "../types";
import { fetchCart, addToCart, removeFromCart, clearCart } from "../services/api";

interface CartState {
  cart: Cart;
  loading: boolean;
  open: boolean;
  totalItems: number;
  totalBdt: number;
  fetchCart:   () => Promise<void>;
  addItem:     (item: CartItem) => Promise<void>;
  removeItem:  (productId: string, retailer: string) => Promise<void>;
  clearCart:   () => Promise<void>;
  setOpen:     (v: boolean) => void;
}

const totals = (cart: Cart) => ({
  totalItems: cart.items.reduce((n, i) => n + i.quantity, 0),
  totalBdt:   cart.items.reduce((n, i) => n + i.price_bdt * i.quantity, 0),
});

export const useCartStore = create<CartState>((set) => ({
  cart: { items: [] }, loading: false, open: false,
  totalItems: 0, totalBdt: 0,

  setOpen: (v) => set({ open: v }),

  fetchCart: async () => {
    set({ loading: true });
    try {
      const cart = await fetchCart();
      set({ cart, ...totals(cart) });
    } finally { set({ loading: false }); }
  },

  addItem: async (item) => {
    const cart = await addToCart(item);
    set({ cart, open: true, ...totals(cart) });
  },

  removeItem: async (productId, retailer) => {
    const cart = await removeFromCart(productId, retailer);
    set({ cart, ...totals(cart) });
  },

  clearCart: async () => {
    await clearCart();
    set({ cart: { items: [] }, totalItems: 0, totalBdt: 0 });
  },
}));
