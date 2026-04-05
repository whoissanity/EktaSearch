// src/services/api.ts  —  all backend calls in one place
import axios from "axios";
import type { SearchResponse, Cart, CartItem, PCBuild, BuildAnalysis } from "../types";

const api = axios.create({ baseURL: "/api", timeout: 15000 });

let _sid = localStorage.getItem("pcbd_session") ?? "";
if (!_sid) { _sid = crypto.randomUUID(); localStorage.setItem("pcbd_session", _sid); }
api.interceptors.request.use((c) => { c.headers["x-session-id"] = _sid; return c; });

export const searchProducts = (q: string) =>
  api.get<SearchResponse>("/search", { params: { q } }).then(r => r.data);

export const fetchCart     = () => api.get<Cart>("/cart").then(r => r.data);
export const addToCart     = (item: CartItem) => api.post<Cart>("/cart/add", item).then(r => r.data);
export const removeFromCart = (productId: string, retailer: string) =>
  api.delete<Cart>(`/cart/item/${productId}`, { params: { retailer } }).then(r => r.data);
export const clearCart     = () => api.delete("/cart");

export const analyzeBuild  = (build: PCBuild) =>
  api.post<BuildAnalysis>("/builder/analyze", build).then(r => r.data);
export const saveBuild     = (build: PCBuild) =>
  api.post<{ build_id: string }>("/builder/save", build).then(r => r.data);
export const loadBuild     = (id: string) =>
  api.get<PCBuild>(`/builder/${id}`).then(r => r.data);
