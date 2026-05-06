# InvoiceSaaS

Invoicing SaaS for freelancers. Send invoices, get paid via Stripe Connect.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 15 App Router, Tailwind v4, TypeScript |
| Backend | FastAPI, Python 3.12+, Pydantic V2, SQLAlchemy 2.0 async |
| Database | Supabase (Postgres + RLS + Realtime + Auth) |
| Queue | BullMQ + Redis |
| Payments | Stripe Connect Express + Stripe Billing |
| Email | Resend |
| PDF | WeasyPrint |

## Repo structure

```
/
├── apps/
│   ├── api/          ← FastAPI backend
│   └── web/          ← Next.js frontend
├── workers/          ← BullMQ workers (separate Railway process)
├── supabase/
│   └── migrations/   ← SQL migration files (NNN_description.sql)
└── .github/
    └── workflows/    ← ci.yml
```

## Local setup

### Prerequisites
- Node 20+, Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker (for Supabase local)

### 1. Clone & install

```bash
git clone <repo>
cd invoicesaas

# JS deps
npm install

# Python deps
cd apps/api && uv sync
```

### 2. Supabase local

```bash
npx supabase start
# outputs local keys — copy to apps/api/.env
```

### 3. Env files

```bash
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.local.example apps/web/.env.local
# fill in values
```

### 4. Run

```bash
# Terminal 1 — API
cd apps/api && uv run uvicorn app.main:app --reload

# Terminal 2 — Next.js
cd apps/web && npm run dev

# Terminal 3 — Workers
cd workers && npm run dev
```

## Environment branches

| Branch | API | Web | DB | Stripe |
|---|---|---|---|---|
| `dev` | localhost:8000 | localhost:3000 | Supabase dev | test keys |
| `main` | Railway prod | Vercel prod | Supabase prod | **live keys** |

## Deployment

Railway and Vercel both deploy via their native GitHub integrations — no deploy workflow needed.
`main` branch → auto-deploy to prod on both platforms.

## Commit discipline

- Max ~500 lines per commit
- Each commit = one atomic feature or migration
- Never mix migrations with app code

## Phase plan

P0 Infra & CI/CD → **you are here**  
P1 Database migrations  
P2 Backend bootstrap  
...  
P18 CI/CD enhancements
