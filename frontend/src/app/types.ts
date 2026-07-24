export interface Product {
  id: string;
  name: string;
  category: string;
  price: number;
  monthlyPrice: number;
  image: string;
  badge: string;
  badgeColor: string;
  aiScore: number;
  stars: number;
  reviews: number;
  tags: string[];
  reasons: string[];
  inStock: boolean;
  trend: string;
  /** Real signal breakdown behind `aiScore`, straight from the backend's
   *  recommend.rank_products() - relevance / preference / budget / popularity,
   *  each 0-1. Absent only if the catalog call failed to include it. */
  signals?: Record<string, number>;
  /** "cold_start" (ranked by relevance + popularity - we don't know this user
   *  yet) or "personalized" (biased by their learned preference profile). */
  personalizationBasis?: "cold_start" | "personalized";
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
