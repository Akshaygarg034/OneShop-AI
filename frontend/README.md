# Frontend — Telekom Smart Shopping Assistant

React + Vite. OneShop (web) and OneApp (mobile view) share one session → omnichannel.

## Run
```bash
npm install
npm run dev        # http://localhost:5173
```
Backend must be running on `:8000` (see ../backend). Override the URL with `VITE_API_URL`.

## Layout (folder = owner)
```
src/
  api/client.js              SHARED - all backend calls go through here
  shared/Layout.jsx          SHARED - header + web/mobile toggle
  App.jsx                    SHARED - assembles the slices
  features/chat/             P1     - chat UI
  features/product-card/     P2     - product card + stock badge
  features/why-panel/        P3     - nudges + trust receipts
  features/cart/             P4     - cart + checkout
  oneapp/                    P4     - phone-shaped mobile view
```

Toggle **OneShop / OneApp** in the header to demo omnichannel (same session id).
