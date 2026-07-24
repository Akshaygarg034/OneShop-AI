import type {
  Product, AppNotification, LiveActivity, SignupPayload,
  ShippingDetails, PaymentDetails,
} from "../types";

/**
 * Every function here simulates a real network round-trip (latency + the
 * possibility of failure). Swap the body of any function for a real
 * `fetch(...)` call against a backend without touching any component.
 */
function simulateRequest<T>(data: T, { delay = 450, failRate = 0 }: { delay?: number; failRate?: number } = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (Math.random() < failRate) {
        reject(new Error("Network request failed. Please try again."));
      } else {
        resolve(data);
      }
    }, delay);
  });
}

const PRODUCTS: Product[] = [
  {
    id: 1,
    name: "Samsung Galaxy S25 Ultra",
    category: "Phones",
    price: 1249,
    monthlyPrice: 52,
    image: "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=400&h=400&fit=crop&auto=format",
    badge: "Top Pick",
    badgeColor: "var(--primary)",
    aiScore: 97,
    stars: 4.8,
    reviews: 2847,
    tags: ["5G", "200MP Camera", "AI Features"],
    reasons: [
      "Matches your last 3 upgrades — high-camera preference",
      "78% of Munich professionals chose this model",
      "Eligible for your loyalty discount (€150 off)",
      "Same tier as your current plan — no upgrade needed",
    ],
    inStock: true,
    trend: "+24% this week",
  },
  {
    id: 2,
    name: "iPhone 16 Pro Max",
    category: "Phones",
    price: 1329,
    monthlyPrice: 55,
    image: "https://images.unsplash.com/photo-1695048133142-1a20484429be?w=400&h=400&fit=crop&auto=format",
    badge: "Trending",
    badgeColor: "#7B61FF",
    aiScore: 91,
    stars: 4.9,
    reviews: 4120,
    tags: ["5G", "A18 Pro", "Camera Control"],
    reasons: [
      "89% of iOS users on your plan chose this",
      "Complements your Apple Watch — seamless ecosystem",
      "Camera Control matches your photography usage pattern",
      "Bundles with current AirPods plan at no extra cost",
    ],
    inStock: true,
    trend: "+18% this week",
  },
  {
    id: 3,
    name: "Magenta L 5G Plan",
    category: "Plans",
    price: 49.95,
    monthlyPrice: 49.95,
    image: "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&h=400&fit=crop&auto=format",
    badge: "Best Value",
    badgeColor: "#00C2A8",
    aiScore: 88,
    stars: 4.6,
    reviews: 9341,
    tags: ["Unlimited", "5G+", "EU Roaming"],
    reasons: [
      "Your current usage avg 45GB — this fits perfectly",
      "Save €12/mo vs your current plan",
      "Includes MagentaTV S worth €7.99/mo free",
      "Top-rated in your area for 5G coverage",
    ],
    inStock: true,
    trend: "Most popular",
  },
  {
    id: 4,
    name: "Samsung Galaxy Watch 7",
    category: "Accessories",
    price: 329,
    monthlyPrice: 14,
    image: "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400&h=400&fit=crop&auto=format",
    badge: "AI Paired",
    badgeColor: "#FF6B35",
    aiScore: 84,
    stars: 4.7,
    reviews: 1823,
    tags: ["Health AI", "LTE", "Galaxy Ecosystem"],
    reasons: [
      "Paired recommendation for Galaxy S25 Ultra in your cart",
      "Syncs natively with Samsung Health on your phone",
      "62% of S25 buyers add this within 30 days",
      "Bundle with Galaxy S25 saves €80 total",
    ],
    inStock: true,
    trend: "Frequently paired",
  },
  {
    id: 5,
    name: "Home & Mobile Bundle XL",
    category: "Bundles",
    price: 79.90,
    monthlyPrice: 79.90,
    image: "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&h=400&fit=crop&auto=format",
    badge: "Bundle Save",
    badgeColor: "#FFD700",
    aiScore: 79,
    stars: 4.5,
    reviews: 3210,
    tags: ["Fiber + Mobile", "Smart Home", "TV Included"],
    reasons: [
      "You searched for home broadband last Tuesday",
      "Combines your current mobile plan + new fiber at €22/mo savings",
      "Includes 3 months MagentaTV Max free",
      "Same-day installation available in your area",
    ],
    inStock: true,
    trend: "Limited offer",
  },
  {
    id: 6,
    name: "Sony WH-1000XM5",
    category: "Accessories",
    price: 299,
    monthlyPrice: 13,
    image: "https://images.unsplash.com/photo-1606220945770-b5b6c2c55bf1?w=400&h=400&fit=crop&auto=format",
    badge: "AI Suggested",
    badgeColor: "var(--primary)",
    aiScore: 76,
    stars: 4.8,
    reviews: 5672,
    tags: ["ANC", "30hr Battery", "Multipoint"],
    reasons: [
      "Complements your commute usage pattern (2h/day audio)",
      "Compatible with both S25 and iPhone 16 Pro Max",
      "68% of users in your profile own premium headphones",
      "Price drop alert: €50 lower than last month",
    ],
    inStock: false,
    trend: "Back in stock soon",
  },
  {
    id: 7,
    name: "Samsung 45W Fast Charger",
    category: "Accessories",
    price: 39.99,
    monthlyPrice: 0,
    image: "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?w=400&h=400&fit=crop&auto=format",
    badge: "Frequently Bought",
    badgeColor: "#00C2A8",
    aiScore: 78,
    stars: 4.4,
    reviews: 6120,
    tags: ["45W", "USB-C", "Fast Charging"],
    reasons: [
      "Required for fastest charging speed on your Galaxy",
      "Frequently bought together with Galaxy S25 Ultra",
    ],
    inStock: true,
    trend: "Frequently bought together",
  },
];

export function getProducts(): Promise<Product[]> {
  return simulateRequest(PRODUCTS);
}

export function getBundleSuggestions(excludeIds: number[]): Promise<Product[]> {
  const suggestions = PRODUCTS
    .filter((p) => !excludeIds.includes(p.id) && p.inStock)
    .sort((a, b) => b.aiScore - a.aiScore)
    .slice(0, 3);
  return simulateRequest(suggestions, { delay: 350 });
}

const NOTIFICATIONS: AppNotification[] = [
  { id: 1, title: "Price drop", body: "Samsung Galaxy S25 Ultra is now €30 cheaper.", time: "2h ago", read: false },
  { id: 2, title: "Back in stock", body: "Sony WH-1000XM5 restocks tomorrow in your area.", time: "5h ago", read: false },
  { id: 3, title: "Order update", body: "Your loyalty discount is available until your contract renewal.", time: "1d ago", read: true },
];

export function getNotifications(): Promise<AppNotification[]> {
  return simulateRequest(NOTIFICATIONS, { delay: 300 });
}

export function getLiveActivity(productId: number): Promise<LiveActivity> {
  const seed = (productId * 37) % 11;
  return simulateRequest(
    { viewers: 2 + (seed % 6), stockLeft: 4 + (seed % 12) },
    { delay: 300 },
  );
}

interface AssistantReply {
  reply: string;
  products?: Product[];
}

export function askAssistant(message: string): Promise<AssistantReply> {
  const text = message.toLowerCase();
  let reply = `Here's what I found based on "${message}" — take a look at these options, or tell me more about your budget and priorities.`;
  let products: Product[] | undefined;

  if (text.includes("plan")) {
    reply = "Here's our best-matching plan for your usage pattern:";
    products = PRODUCTS.filter((p) => p.category === "Plans");
  } else if (text.includes("camera") || text.includes("photo")) {
    reply = "These have the strongest camera systems in your budget range:";
    products = PRODUCTS.filter((p) => p.tags.some((t) => t.toLowerCase().includes("camera"))).slice(0, 2);
  } else if (text.includes("bundle") || text.includes("deal")) {
    reply = "This bundle combines your mobile plan with home connectivity for the biggest savings:";
    products = PRODUCTS.filter((p) => p.category === "Bundles");
  } else if (text.includes("headphone") || text.includes("audio")) {
    reply = "Top-rated audio accessory for your listening habits:";
    products = PRODUCTS.filter((p) => p.tags.includes("ANC"));
  } else if (text.includes("watch")) {
    reply = "This pairs well with your current devices:";
    products = PRODUCTS.filter((p) => p.category === "Accessories" && p.name.includes("Watch"));
  } else if (text.includes("compare")) {
    reply = "Here's a side-by-side of our two top phones:";
    products = PRODUCTS.filter((p) => p.category === "Phones");
  }

  return simulateRequest({ reply, products }, { delay: 900 });
}

export interface OrderResult {
  orderNumber: string;
  estimatedDelivery: string;
}

export function createOrder(_shipping: ShippingDetails, _payment: PaymentDetails, _items: unknown): Promise<OrderResult> {
  const orderNumber = `OS-${Math.floor(100000 + Math.random() * 900000)}`;
  const eta = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000);
  return simulateRequest(
    { orderNumber, estimatedDelivery: eta.toLocaleDateString("de-DE", { day: "2-digit", month: "short" }) },
    { delay: 900 },
  );
}

export function submitSignup(_payload: SignupPayload): Promise<{ success: true }> {
  return simulateRequest({ success: true as const }, { delay: 700 });
}
