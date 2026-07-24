// Assembles the four slices into OneShop (web) and OneApp (mobile) views. SHARED.
// Each team member mainly edits their own feature component, not this file.
import React, { useEffect, useState } from "react";
import Layout from "./shared/Layout.jsx";
import Chat from "./features/chat/Chat.jsx";
import ProductCard from "./features/product-card/ProductCard.jsx";
import WhyPanel from "./features/why-panel/WhyPanel.jsx";
import CartView from "./features/cart/Cart.jsx";
import OneApp from "./oneapp/OneApp.jsx";
import {
  sendChat, getCatalog, getCart, addToCart, removeFromCart, checkout,
} from "./api/client.js";

export default function App() {
  const [channel, setChannel] = useState("web");
  const [messages, setMessages] = useState([]);
  const [recs, setRecs] = useState([]);
  const [nba, setNba] = useState([]);
  const [receipts, setReceipts] = useState(null);
  const [cart, setCart] = useState(null);
  const [products, setProducts] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getCatalog().then((list) => {
      const map = {};
      list.forEach((p) => (map[p.id] = p));
      setProducts(map);
    });
    getCart().then(setCart).catch(() => {});
  }, []);

  const onSend = async (message) => {
    setMessages((m) => [...m, { role: "user", content: message }]);
    setBusy(true);
    try {
      const r = await sendChat(message);
      setMessages((m) => [...m, { role: "assistant", content: r.reply_text }]);
      setRecs(r.recommendations || []);
      setNba(r.nba || []);
      setReceipts(r.receipts || null);
      setCart(r.cart || cart);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: "⚠️ Backend not reachable. Is the server running on :8000?" }]);
    } finally {
      setBusy(false);
    }
  };

  const onAdd = async (pid) => setCart(await addToCart(pid));
  const onRemove = async (pid) => setCart(await removeFromCart(pid));
  const onCheckout = async () => {
    const summary = await checkout();
    setMessages((m) => [...m, { role: "assistant", content: `✅ Order confirmed! Total €${summary.total}.` }]);
    setCart(await getCart());
  };

  const content = (
    <div className={`layout ${channel === "mobile" ? "mobile" : ""}`}>
      <div>
        <Chat messages={messages} onSend={onSend} busy={busy} />
      </div>
      <div>
        <div className="panel">
          <h3>Recommendations</h3>
          {recs.length === 0 && <div className="receipts">Ask something to see grounded picks.</div>}
          {recs.map((r) => (
            <ProductCard key={r.product_id} product={products[r.product_id]} why={r.why} onAdd={onAdd} />
          ))}
        </div>
        <WhyPanel nba={nba} receipts={receipts} />
        <CartView cart={cart} products={products} onRemove={onRemove} onCheckout={onCheckout} />
      </div>
    </div>
  );

  return (
    <Layout channel={channel} setChannel={setChannel}>
      {channel === "mobile" ? (
        <OneApp>{content}</OneApp>
      ) : (
        <div className="container">{content}</div>
      )}
    </Layout>
  );
}
