# EktaSearch

### Bangladesh's PC Parts Search Engine

Search once. Compare across 8 retailers. Build a compatible PC. Save, share, and decide faster.

**"Most Bangladeshi e-commerce experiences were chaotic. So I built the fix."**

[Frontend](#tech-stack)
[Backend](#tech-stack)
[State](#tech-stack)
[Styling](#tech-stack)
[Data](#tech-stack)

---

## Why I Built This

PC buyers in Bangladesh usually have to:

- Open many tabs across multiple stores
- Manually compare prices and stock
- Guess part compatibility for custom builds
- Lose context between browsing, comparing, and purchasing

EktaSearch turns that fragmented flow into one product.

---

## What EktaSearch Does

- **Unified multi-retailer search** with a single query fan-out
- **Progressive streaming results** (NDJSON) so users see data as it arrives
- **Price comparison groups** for side-by-side retailer options
- **PC Builder** with live compatibility and wattage analysis
- **Guest cart sessions** tied to `x-session-id` (no login required)
- **Community forum** (posts, replies, votes, file attachments)
- **Auth system** for registered users and owner moderation signals

---

## Retailers Integrated (Live Adapter Registry)

- Ryans Computers
- Star Tech
- Tech Land BD
- Skyland
- Vibe Gaming
- Tech Diversity BD
- The Blisstronics
- PoTaka IT

---

## Architecture Overview

```text
React + Vite SPA
   |
   v
FastAPI API Layer
   |- /api/search        -> merged JSON results
   |- /api/search/stream -> progressive NDJSON chunks
   |- /api/compare       -> grouped alternatives
   |- /api/builder       -> compat + wattage + save/load
   |- /api/cart          -> session cart lifecycle
   |- /api/community     -> posts/replies/votes/attachments
   '- /api/auth          -> register/login/session token
   |
   v
Adapter Fan-out (8 retailers in parallel)
   |
   v
Relevance Scoring + De-dup + Filtering + Sorting
   |
   v
Redis cache (primary) + SQLAlchemy persistence (SQLite default)
```

---

## Why This Works

EktaSearch works because it is system-first, not page-first:

1. **Parallel retrieval** from all adapters reduces user effort and decision latency.
2. **Streaming-first UX** returns early chunks before full completion.
3. **Relevance + deterministic sorting** keeps results useful, not noisy.
4. **Stateful product flow** (search -> compare -> build -> cart -> community) keeps users in one loop.
5. **Cache strategy** cuts repeat query cost and stabilizes response time.

---

## Tech Stack

### Frontend

- React 18 + TypeScript
- Vite 5
- TailwindCSS
- Zustand (search/cart/builder state)
- Axios + Fetch streaming for NDJSON
- React Router v6

### Backend

- Python 3 + FastAPI
- Async fan-out with `asyncio`
- SQLAlchemy (async) + `aiosqlite`
- Redis cache
- Pydantic + pydantic-settings
- Tenacity, httpx/aiohttp, BeautifulSoup/lxml for resilient data ingestion

---

## Creator Profile

Hi, I am **Sowad Mubasshir**.

- I am a **14-year-old student from Bangladesh**.
- I enjoy **web scraping** and **testing limits**.
- My core interests are **robotics**, **web scraping**, and **automation**.

I built EktaSearch to learn fast, solve real local problems, and push my technical boundaries.

