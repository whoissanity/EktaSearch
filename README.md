# PC Bangladesh — Unified PC Parts Aggregator

A free, open personal project that aggregates PC parts from 8 major Bangladeshi retailers into one unified search, price comparison, PC builder, and cart experience.

## Retailers Covered
- Ryans Computers
- Star Tech
- Tech Land BD
- Skyland
- Ultra Technology
- Vibe Gaming
- PoTaka IT
- Blisstyle

## Stack
- **Frontend**: React + Vite + TailwindCSS + Zustand
- **Backend**: Python + FastAPI + Redis (cache) + SQLite (local dev) / PostgreSQL (prod)
- **Data**: Retailer APIs (adapters per retailer) + BeautifulSoup fallback scrapers

## Folder Structure
```
pc-bd/
├── frontend/          # React app
│   └── src/
│       ├── pages/         # Route-level pages
│       ├── components/    # UI components (max 200 lines each)
│       │   ├── search/
│       │   ├── builder/
│       │   ├── compare/
│       │   ├── cart/
│       │   └── layout/
│       ├── hooks/         # Custom React hooks
│       ├── store/         # Zustand state slices
│       ├── services/      # API call layer (axios)
│       └── utils/         # Helpers
└── backend/           # FastAPI app
    └── app/
        ├── routers/       # Route handlers (search, build, compare, cart)
        ├── adapters/      # One file per retailer (API clients)
        ├── scrapers/      # BeautifulSoup scrapers (fallback)
        ├── models/        # Pydantic schemas
        ├── core/          # Config, cache, CORS, app factory
        └── services/      # Business logic (compatibility, wattage, search merge)
```

## Quick Start

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your API keys
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Adding API Keys
Edit `backend/.env` — one variable per retailer. See `.env.example`.

## Contributing / Extending
- To add a new retailer: copy `backend/app/adapters/_template.py`, implement the 4 methods, register in `adapters/__init__.py`.
- Every file must stay under 200 lines.
