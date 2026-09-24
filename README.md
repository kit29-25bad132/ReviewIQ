# 🚀 Product Review Analyzer

> Turn customer feedback into actionable insights with structured AI analysis.

**Product Review Analyzer** is a full-stack web application designed to analyze unstructured customer product reviews using Large Language Models (Google Gemini API). It extracts strictly validated structured information including **sentiment**, **1-5 star ratings**, **evidence-based pros**, **cons**, and **executive summaries**, displayed in a futuristic, glassmorphic dark dashboard.

---

## ✨ Features

- 🎯 **Strict Structured JSON Output**: Validated with Pydantic schemas (zero uncontrolled markdown or text chatter).
- 🛡️ **Anti-Hallucination Engine**: Extracts *only* features and pros/cons explicitly supported by the review text.
- ⭐ **Accurate 1–5 Star Rating**: Explicitly extracted or intelligently inferred from sentiment and evidence.
- 🎨 **Dark Futuristic UI**: Built with React, Tailwind CSS, Lucide icons, glassmorphism cards, and gradient accents.
- 📊 **Dynamic Dashboard Analytics**: Real-time calculated metrics (Total Reviews, Positive, Negative, Neutral, Average Rating) based on actual processed data.
- 📜 **Persistent Review History**: Supabase (when configured) with local `localStorage` fallback, keyword search, sentiment filtering, and detailed review inspector.
- 🧪 **"Try Sample Review"**: Instant one-click test with representative review text.
- 🔒 **Secure API Architecture**: Never exposes API keys in frontend code; backend strictly checks payloads and environment variables.
- 📱 **Fully Responsive**: Optimized for desktop, laptop, tablet, and mobile screens.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Axios, Lucide React, Supabase JS |
| **Backend** | Python 3.10+, FastAPI, Uvicorn, Pydantic v2, Python-Dotenv |
| **AI Provider** | Google Gemini API (`gemini-3.8-flash` primary + verified Gemini fallback pool via LangGraph structured outputs) |
| **Database** | Supabase (PostgreSQL) with local `localStorage` fallback (demo RLS: anon read/insert/delete) |

---

## 📁 Project Structure

```
ReviewIQ/
├── frontend/
│   ├── src/
│   │   ├── components/          # Analysis, history, dataset, product, evaluation UI
│   │   ├── pages/Dashboard.tsx  # Main dashboard (analysis + product intelligence)
│   │   ├── services/
│   │   │   ├── api.ts           # Axios client for backend API
│   │   │   ├── historyStorage.ts# Supabase persistence + localStorage fallback
│   │   │   └── supabase.ts      # Supabase client (URL + anon/publishable key)
│   │   ├── types/               # review.ts, ecommerce.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts           # Vitest config included
│
├── backend/
│   ├── main.py                  # FastAPI app, CORS, global exception handler
│   ├── requirements.txt
│   ├── .env.example
│   ├── models/                  # review.py, dataset.py, ecommerce.py (Pydantic)
│   ├── routes/                  # review, products, reviews, dataset, analytics, evaluation
│   ├── services/                # ai_analyzer, analysis_graph, grounding, dataset, etc.
│   ├── scripts/ingest_dataset.py # Optional local CSV → SQLite ingestion
│   └── tests/                   # pytest suite (offline, mocked)
│
├── supabase_schema.sql          # Canonical reviews table + RLS policies
├── README.md
└── .gitignore
```

---

## ⚙️ Environment Variables

### Backend (`backend/.env`)

```ini
# Google Gemini API Key (Required)
# Get a free key at: https://aistudio.google.com/
GEMINI_API_KEY=your_gemini_api_key_here

# Server Settings (defaults match backend/.env.example)
HOST=127.0.0.1
PORT=8000
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### Frontend (`frontend/.env`)

```ini
# Backend API Base URL
VITE_API_BASE_URL=http://localhost:8000

# Supabase project URL and frontend anon/publishable key
VITE_SUPABASE_URL=https://your-project.supabase.co
# Set one key:
# VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
# VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_your-key
```

> [!WARNING]
> Never place `GEMINI_API_KEY` or a Supabase service-role key in the frontend `.env` file. The frontend uses only the project URL and anon/publishable key.

Vite embeds `VITE_*` values at build time. After changing `frontend/.env`, restart the dev server or rebuild the production bundle.

---

## 🚀 Installation & Running

### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env and set your Gemini API key
copy .env.example .env
# Edit .env and enter your valid GEMINI_API_KEY

# Start backend server
uvicorn main:app --reload --port 8000
```

Backend will be running at: `http://localhost:8000`  
Interactive API Docs (Swagger): `http://localhost:8000/docs`

---

### 2. Frontend Setup

Open a new terminal:

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

### 3. Supabase Database Setup
1. Open your [Supabase SQL Editor](https://supabase.com/dashboard/project/_/sql).
2. Copy and run the contents of [`supabase_schema.sql`](./supabase_schema.sql):

```sql
create table if not exists public.reviews (
    id uuid primary key default gen_random_uuid(),
    review_text text not null,
    sentiment text not null check (sentiment in ('positive', 'negative', 'neutral', 'mixed')),
    rating integer check (rating is null or (rating >= 1 and rating <= 5)),
    rating_source text check (rating_source is null or rating_source in ('explicit', 'inferred', 'not_found')),
    pros jsonb not null default '[]'::jsonb,
    cons jsonb not null default '[]'::jsonb,
    aspects jsonb not null default '[]'::jsonb,
    summary text not null,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

alter table public.reviews enable row level security;

create policy "Allow public read access" on public.reviews for select to anon, authenticated using (true);
create policy "Allow public insert access" on public.reviews for insert to anon, authenticated with check (true);
create policy "Allow public delete access" on public.reviews for delete to anon, authenticated using (true);
```

> Demo posture: RLS allows any anon/publishable key holder to read, insert, and delete rows. Acceptable for V1 demos only — not for multi-tenant production data.

---

## 🧪 Testing

```bash
# Backend (from repo root, with backend .venv active)
.venv\Scripts\python.exe -m pytest backend\tests

# Frontend
cd frontend
npm test          # vitest
npm run build     # tsc + vite production build
```

Tests are offline: Gemini and Supabase are mocked/faked; no network required.

## 🔌 API Endpoints

Full endpoint list, request/response schemas, and error envelopes: [`docs/08_API_CONTRACT.md`](docs/08_API_CONTRACT.md). Key endpoints below.

### 1. Health Check
- **Endpoint**: `GET /health`
- **Description**: Returns service health and AI configuration status without leaking keys.
- **Response**:
```json
{
  "status": "ok",
  "service": "Product Review Analyzer Backend",
  "version": "1.0.0",
  "ai_provider": "Google Gemini",
  "ai_configured": true
}
```

---

### 2. Analyze Review
- **Endpoint**: `POST /api/analyze-review`
- **Description**: Analyzes customer review text and returns validated structured JSON.

#### Request Body:
```json
{
  "review": "The camera quality is excellent and the display is beautiful. Battery life is good for normal use, but the phone becomes hot while gaming. Overall I am happy with the product."
}
```

#### Response Body:
```json
{
  "success": true,
  "data": {
    "sentiment": "mixed",
    "rating": 4,
    "rating_source": "explicit",
    "summary": "The customer praises the camera, display, and battery life but notes heating while gaming.",
    "aspects": [
      {
        "aspect": "camera",
        "sentiment": "positive",
        "evidence": "camera quality is excellent"
      },
      {
        "aspect": "gaming thermals",
        "sentiment": "negative",
        "evidence": "the phone becomes hot while gaming"
      }
    ],
    "pros": [
      {
        "point": "Excellent camera quality",
        "evidence": "camera quality is excellent"
      },
      {
        "point": "Beautiful display",
        "evidence": "the display is beautiful"
      }
    ],
    "cons": [
      {
        "point": "Heats up while gaming",
        "evidence": "the phone becomes hot while gaming"
      }
    ]
  },
  "error": null
}
```

`sentiment` is one of `positive | negative | neutral | mixed`. `rating` is an integer 1–5 or `null` (with `rating_source = "not_found"`). `rating_source` is `explicit | inferred | not_found`. `pros`/`cons` are arrays of `{ "point", "evidence" }` objects.

---

## 🧪 Acceptance Test Case

Input review:
> *"The camera is excellent and the display looks beautiful. Battery life is good during normal use, but the phone gets very hot while gaming. Overall, I am satisfied."*

Expected result:
- **Sentiment**: `positive`
- **Rating**: `4` (or `4/5`)
- **Pros**: Contains camera quality, display, battery life
- **Cons**: Heating during gaming
- **Anti-Hallucination**: Does NOT mention unreferenced attributes (e.g. processor brand, headphone jack, waterproof rating, etc.)

---

## 🛡️ Security & Quality Best Practices

1. **Strict Model Validation**: AI outputs are parsed directly into Pydantic models with constrained types (`Literal["positive", "negative", "neutral", "mixed"]`, `rating_source` Literal, nullable `Field(ge=1, le=5)` rating, and `PointEvidence` objects).
2. **No Secret Leakage**: API keys remain strictly in backend memory and are never sent to the browser or returned in error traces. API error responses use safe generic messages (provider/parser details stay in server logs).
3. **No Unsafe Code Execution**: Zero usage of `eval()` or unsanitized `dangerouslySetInnerHTML`.
4. **CORS Hardening**: CORS origins are restricted to configured client hosts.

---

## 🔮 Roadmap / Future Extensions

- [ ] **V2 - Bulk CSV Review Upload**: Upload `reviews.csv` with multiple columns and process batch reviews with progress tracking.
- [x] **V3 - Advanced Analytics**: Product-level analytics, rating distributions, and pros/cons analysis from the 4M dataset.
- [x] **V4 - Database Persistence**: Supabase / PostgreSQL schema with local `localStorage` fallback.
- [ ] **V5 - User Authentication**: Google OAuth and email/password sign-in.
- [ ] **V6 - Data Export**: Export reports to CSV, Excel, and PDF formats.

---

## 📜 License

MIT License. Designed for learning and production use.
