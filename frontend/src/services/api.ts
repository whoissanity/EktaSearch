// src/services/api.ts  —  all backend calls in one place
import axios from "axios";
import type {
  SearchResponse,
  Cart,
  CartItem,
  PCBuild,
  BuildAnalysis,
  ProductResult,
  CommunityPost,
  CommunityTopic,
} from "../types";
import { applySearchFilters, sortSearchResults } from "../utils/searchResults";
import type { SearchFilters } from "../types";

const api = axios.create({ baseURL: "/api", timeout: 60000 });

let _sid = localStorage.getItem("pcbd_session") ?? "";
if (!_sid) { _sid = crypto.randomUUID(); localStorage.setItem("pcbd_session", _sid); }
api.interceptors.request.use((c) => { c.headers["x-session-id"] = _sid; return c; });

export type SearchRequestParams = {
  q: string;
  sort_by?: string;
  in_stock_only?: boolean;
  min_price?: number;
  max_price?: number;
  retailers?: string;
  category?: string;
};

function cleanParams(p: SearchRequestParams): Record<string, string | number | boolean> {
  const o: Record<string, string | number | boolean> = { q: p.q };
  if (p.sort_by != null && p.sort_by !== "") o.sort_by = p.sort_by;
  if (p.in_stock_only) o.in_stock_only = true;
  if (p.min_price != null && !Number.isNaN(p.min_price)) o.min_price = p.min_price;
  if (p.max_price != null && !Number.isNaN(p.max_price)) o.max_price = p.max_price;
  if (p.retailers != null && p.retailers !== "") o.retailers = p.retailers;
  if (p.category != null && p.category !== "") o.category = p.category;
  return o;
}

export function searchProducts(params: SearchRequestParams) {
  return api.get<SearchResponse>("/search", { params: cleanParams(params) }).then((r) => r.data);
}

type StreamMsg =
  | { type: "chunk"; shop: string; page?: number; results: ProductResult[] }
  | { type: "done"; total: number; query: string };

/**
 * NDJSON /api/search/stream — merges chunks, applies filters/sort like the JSON search endpoint.
 */
export async function searchProductsStream(
  params: SearchRequestParams,
  filters: SearchFilters,
  opts?: { signal?: AbortSignal; onChunk?: (items: ProductResult[]) => void }
): Promise<ProductResult[]> {
  const sp = new URLSearchParams();
  const c = cleanParams(params);
  for (const [k, v] of Object.entries(c)) {
    sp.set(k, String(v));
  }
  const res = await fetch(`/api/search/stream?${sp.toString()}`, { signal: opts?.signal });
  if (!res.ok) throw new Error(`Search stream failed: ${res.status}`);
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const dec = new TextDecoder();
  let buf = "";
  const byLink = new Map<string, ProductResult>();

  const flushMerged = () => {
    const raw = [...byLink.values()];
    const filtered = applySearchFilters(raw, filters);
    return sortSearchResults(filtered, filters.sort_by ?? "relevance");
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const msg = JSON.parse(line) as StreamMsg;
      if (msg.type === "chunk") {
        for (const p of msg.results) {
          byLink.set(p.link, p);
        }
        opts?.onChunk?.(flushMerged());
      }
    }
  }
  if (buf.trim()) {
    try {
      const msg = JSON.parse(buf) as StreamMsg;
      if (msg.type === "done") {
        /* handled below */
      }
    } catch {
      /* ignore incomplete */
    }
  }

  return flushMerged();
}

export const fetchCart     = () => api.get<Cart>("/cart").then(r => r.data);
export const addToCart     = (item: CartItem) => api.post<Cart>("/cart/add", item).then(r => r.data);
export const removeFromCart = (productId: string, retailer: string) =>
  api.delete<Cart>(`/cart/item/${productId}`, { params: { retailer } }).then(r => r.data);
export const clearCart     = () => api.delete("/cart");

export const analyzeBuild  = (build: PCBuild) =>
  api.post<BuildAnalysis>("/builder/analyze", build).then(r => r.data);

export type CommunityListParams = {
  topic?: CommunityTopic;
  retailer_id?: string;
  skip?: number;
  limit?: number;
};

export function fetchCommunityPosts(params?: CommunityListParams) {
  return api
    .get<{ posts: CommunityPost[]; total: number }>("/community/posts", { params: params ?? {} })
    .then((r) => r.data);
}

export function createCommunityPost(body: {
  title: string;
  body: string;
  topic: CommunityTopic;
  retailer_id?: string | null;
  author_name: string;
}) {
  return api.post<CommunityPost>("/community/posts", body).then((r) => r.data);
}
export const saveBuild     = (build: PCBuild) =>
  api.post<{ build_id: string }>("/builder/save", build).then(r => r.data);
export const loadBuild     = (id: string) =>
  api.get<PCBuild>(`/builder/${id}`).then(r => r.data);
