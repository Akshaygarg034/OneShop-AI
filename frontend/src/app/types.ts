export interface Product {
  id: number;
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
}

export interface CartLineItem {
  product: Product;
  qty: number;
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

export interface SignupPayload {
  name: string;
  phone: string;
  email: string;
}
