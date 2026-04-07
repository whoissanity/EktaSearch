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

export const SLOT_COMPONENT_ID: Record<BuildSlot, number> = {
  cpu: 2,
  cooler: 3,
  motherboard: 4,
  gpu: 5,
  ram: 6,
  storage: 7,
  psu: 8,
  case: 9,
};

export const COMPONENT_ID_SLOT: Record<number, BuildSlot> = {
  2: "cpu",
  3: "cooler",
  4: "motherboard",
  5: "gpu",
  6: "ram",
  7: "storage",
  8: "psu",
  9: "case",
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
  likes: number;
  dislikes: number;
  score: number;
  replies_count: number;
  user_vote: -1 | 0 | 1;
  replies: CommunityReply[];
  is_owner?: boolean;
  attachments?: CommunityAttachment[];
}

export interface CommunityReply {
  id: string;
  post_id: string;
  body: string;
  author_name: string;
  created_at: string | null;
  is_owner?: boolean;
  attachments?: CommunityAttachment[];
}

export interface CommunityAttachment {
  id: string;
  file_url: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
}

export interface AuthUser {
  id: string;
  email: string;
  username: string;
  is_owner: boolean;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
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
