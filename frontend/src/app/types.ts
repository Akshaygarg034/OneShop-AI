export interface Product {
  id: string;
  name: string;
  brand: string;
  category: string;
  price: number;
  monthlyPrice: number;
  /** Pre-discount price; 0 when the product isn't discounted. */
  originalPrice: number;
  discountPct: number;
  image: string;
  badge: string;
  badgeColor: string;
  stars: number;
  reviews: number;
  colors: string[];
  /** Human-readable key specs, e.g. ["8GB RAM", "128GB", "6.1\""] */
  specs: string[];
  attributes: Record<string, unknown>;
  tags: string[];
  inStock: boolean;
  trend: string;
}

/** The learned preference profile, as returned by GET /session/profile. */
export interface PreferenceAffinity {
  score: number;
  hard: boolean;
  last_seen: string;
}

export interface BudgetPreference {
  min: number | null;
  max: number | null;
  period: "onetime" | "monthly";
  source: "stated" | "inferred";
}

export interface Preferences {
  /** Per-category budgets; the "any" key holds a general fallback budget. */
  budgets: Record<string, BudgetPreference>;
  brands: Record<string, PreferenceAffinity>;
  categories: Record<string, PreferenceAffinity>;
  features: Record<string, PreferenceAffinity>;
  attributes: Record<string, { min?: number; max?: number; values?: string[] }>;
  rejected_products: Record<string, string>;
  prefers_deals: boolean;
}

export interface CartLineItem {
  product: Product;
  qty: number;
  billing: "onetime" | "monthly";
}

export interface AppNotification {
  id: number;
  title: string;
  body: string;
  time: string;
  read: boolean;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  text: string;
  products?: Product[];
  timestamp: string;
}

export interface LiveActivity {
  viewers: number;
  stockLeft: number;
}

export interface ShippingDetails {
  fullName: string;
  address: string;
  city: string;
  postalCode: string;
}

export interface PaymentDetails {
  cardName: string;
  cardNumber: string;
  expiry: string;
  cvc: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  name?: string;
  phone?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface AuthUser {
  userId: string;
  email: string;
  name: string;
  token: string;
}
