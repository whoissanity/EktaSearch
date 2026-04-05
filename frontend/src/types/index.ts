// src/types/index.ts  —  mirrors backend ProductResult exactly

export interface ProductResult {
  title: string;
  price: number;
  original_price?: number;
  description?: string;
  link: string;
  image?: string;
  shop_name: string;
  availability: boolean;
  relevance_score?: number;
}

export interface SearchResponse {
  query: string;
  total: number;
  results: ProductResult[];
}

export interface SearchFilters {
  sort_by?: "price_asc" | "price_desc" | "relevance";
  in_stock_only?: boolean;
  retailers?: string[];
  min_price?: number;
  max_price?: number;
}

export interface CartItem {
  product_id: string;
  product_name: string;
  retailer: string;
  retailer_name: string;
  price_bdt: number;
  product_url: string;
  quantity: number;
  image_url?: string;
}

export interface Cart { items: CartItem[]; }

export type BuildSlot =
  | "cpu" | "motherboard" | "ram" | "gpu"
  | "storage" | "psu" | "case" | "cooler";

export const SLOT_LABELS: Record<BuildSlot, string> = {
  cpu:         "Processor (CPU)",
  motherboard: "Motherboard",
  ram:         "Memory (RAM)",
  gpu:         "Graphics Card (GPU)",
  storage:     "Storage",
  psu:         "Power Supply (PSU)",
  case:        "Case",
  cooler:      "CPU Cooler",
};

export interface BuildPart {
  slot: BuildSlot;
  product_id: string;
  product_name: string;
  price_bdt: number;
  retailer: string;
  specs: Record<string, string>;
}

export interface PCBuild {
  id?: string;
  name: string;
  parts: BuildPart[];
}

export interface CompatibilityIssue {
  severity: "error" | "warning";
  slot_a: string;
  slot_b?: string;
  message: string;
}

export interface BuildAnalysis {
  build: PCBuild;
  compatibility: { compatible: boolean; issues: CompatibilityIssue[] };
  wattage: { total_estimated_watts: number; recommended_psu_watts: number; breakdown: { slot: string; component: string; estimated_watts: number }[] };
}

export type CommunityTopic = "review" | "issue" | "suggestion" | "general";

export interface CommunityPost {
  id: string;
  title: string;
  body: string;
  topic: CommunityTopic;
  retailer_id: string | null;
  author_name: string;
  created_at: string | null;
}

export const RETAILERS: Record<string, { name: string; color: string }> = {
  ryans:         { name: "Ryans Computers",  color: "#1E40AF" },
  startech:      { name: "Star Tech",        color: "#065F46" },
  techland:      { name: "Tech Land BD",     color: "#92400E" },
  skyland:       { name: "Skyland",          color: "#5B21B6" },
  vibe:          { name: "Vibe Gaming",      color: "#BE185D" },
  techdiversity: { name: "Tech Diversity BD",color: "#0E7490" },
  blisstronics:  { name: "The Blisstronics", color: "#166534" },
  potaka:        { name: "PoTaka IT",        color: "#9A3412" },
};
