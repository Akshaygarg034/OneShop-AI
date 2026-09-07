# Frontend — React + TypeScript + Vite

The OneShop AI storefront: catalog browsing, streaming chat, cart and checkout,
and an editable preference panel. See the [root README](../README.md) for the
full project overview.

## Running

```bash
npm install
cp .env.example .env   # only needed if the backend isn't on the default address
npm run dev            # → http://localhost:5173
```

| Script | Purpose |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Production build → `dist/` |
| `npm run typecheck` | `tsc --noEmit` (strict mode) |

The backend must be running for anything beyond the shell to work — see
[`backend/README.md`](../backend/README.md).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://127.0.0.1:8000` | Backend base URL, no trailing slash |
| `VITE_GOOGLE_CLIENT_ID` | *(empty)* | Google OAuth Client ID. Empty hides the Google button; email/password still works |

> Vite inlines `VITE_*` variables at **build time**. Changing one needs a
> rebuild, not just a restart — this is the usual reason a deployed frontend
> still points at `localhost`.

## Layout

```
src/
├── main.tsx
├── app/
│   ├── App.tsx                 # shell: header, view routing, footer, floating chat
│   ├── api/
│   │   ├── api.ts              # typed backend client (REST + SSE parsing)
│   │   └── session.ts          # guest/account session identity in localStorage
│   ├── auth/AuthContext.tsx    # current user, login/register/Google, logout
│   ├── cart/CartContext.tsx    # cart state, re-fetched when identity changes
│   ├── theme/ThemeProvider.tsx # light/dark, persisted
│   ├── components/
│   │   ├── views/Discovery.tsx # catalog grid, category tabs, search
│   │   ├── views/SmartCart.tsx # cart + multi-step checkout
│   │   ├── FloatingChat.tsx    # streaming chat, thread history, repositionable
│   │   ├── PreferencesPanel.tsx# view and edit what the assistant learned
│   │   ├── AuthModal.tsx       # sign in / sign up
│   │   ├── GoogleSignInButton.tsx
│   │   ├── StoreHeader.tsx     # search, voice input, account menu
│   │   ├── ErrorBoundary.tsx   # isolates panel failures from the page
│   │   └── ui/                 # shadcn/ui primitives
│   ├── lib/useSpeechRecognition.ts
│   └── types.ts                # shared view models
└── styles/theme.css            # light + dark design tokens
```

## Notes

**Design tokens.** Colors, radii, and spacing are CSS custom properties in
`styles/theme.css`, defined once per theme under `[data-theme]`. Components read
`var(--foreground)`, `var(--card)`, and friends — so both themes stay consistent
from a single place. Avoid hardcoding hex values.

**Session identity.** Every guest gets a random `session_id` in localStorage, so
carts and history never leak between visitors. On sign-in the backend merges
that guest session into one keyed by `user_id`, and a `oneshop-session-changed`
event tells mounted contexts to re-fetch under the new identity.

**Streaming.** `streamChat` in `api/api.ts` reads the SSE body directly and
handles `token`, `recommendations`, `nba`, and `done` events. Product cards
arrive inside the same stream, so no follow-up catalog fetch is needed.

---

Originally scaffolded from a
[Figma Make design](https://www.figma.com/design/35M1iAUvDaXUlQbUUxsFnc/Omnichannel-Consumer-AI-Engine);
see [ATTRIBUTIONS.md](ATTRIBUTIONS.md).
