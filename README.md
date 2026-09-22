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
- 📜 **Persistent Review History**: Client-side storage (`localStorage`) with keyword search, sentiment filtering, and detailed review inspector.
- 🧪 **"Try Sample Review"**: Instant one-click test with representative review text.
- 🔒 **Secure API Architecture**: Never exposes API keys in frontend code; backend strictly checks payloads and environment variables.
- 📱 **Fully Responsive**: Optimized for desktop, laptop, tablet, and mobile screens.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Axios, Lucide React, Supabase JS |
| **Backend** | Python 3.10+, FastAPI, Uvicorn, Pydantic v2, Python-Dotenv |
| **AI Provider** | Google Gemini API (`gemini-2.5-flash` / `gemini-1.5-flash` with structured outputs) |
| **Database** | Supabase (PostgreSQL) with automatic fallback & local caching |

---

## 📁 Project Structure

```
product-review-analyzer/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ReviewInput.tsx       # Textarea, char counter, sample review button, validation
│   │   │   ├── AnalysisResult.tsx    # Sentiment badge, stars, pros/cons cards, AI summary
│   │   │   ├── StatCard.tsx          # Metric statistics card
│   │   │   ├── ReviewHistory.tsx     # Local history log, search, filter, view modal, delete
│   │   │   └── LoadingState.tsx      # Pulsing radar AI analysis indicator
│   │   ├── pages/
│   │   │   └── Dashboard.tsx         # Main dashboard assembling layout & stats
│   │   ├── services/
│   │   │   └── api.ts                # Axios client for backend API communication
│   │   ├── types/
│   │   │   └── review.ts             # TypeScript interfaces for request, analysis, history
│   │   ├── App.tsx                   # Root React component
│   │   ├── main.tsx                  # React DOM entrypoint
│   │   └── index.css                 # Tailwind CSS & glassmorphism theme
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── tsconfig.json
│   └── .env                          # Frontend environment variables
│
├── backend/
│   ├── main.py                       # FastAPI application & CORS configuration
│   ├── requirements.txt              # Minimal backend dependencies
│   ├── .env                          # Backend environment variables (API keys)
│   ├── .env.example                  # Template for backend environment variables
│   ├── models/
│   │   └── review.py                 # Pydantic schemas (ReviewRequest, ReviewAnalysis)
│   ├── routes/
│   │   └── review.py                 # API endpoints (POST /api/analyze-review)
│   └── services/
│       └── ai_analyzer.py            # Gemini AI service with anti-hallucination prompts
│
├── README.md                         # Project documentation
└── .gitignore                        # Git ignore rules
```

---

## ⚙️ Environment Variables

### Backend (`backend/.env`)

```ini
# Google Gemini API Key (Required)
# Get a free key at: https://aistudio.google.com/
GEMINI_API_KEY=your_gemini_api_key_here

# Server Settings
HOST=0.0.0.0
PORT=8000
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### Frontend (`frontend/.env`)

```ini
# Backend API Base URL
VITE_API_BASE_URL=http://localhost:8000
```

> [!WARNING]
> Never place `GEMINI_API_KEY` in the frontend `.env` file or commit `.env` files to git.

---

## 🚀 Installation & Running

### 1. Backend Setup

```bash
# Navigate to backend directory
cd product-review-analyzer/backend

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
cd product-review-analyzer/frontend

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
    sentiment text not null check (sentiment in ('positive', 'negative', 'neutral')),
    rating integer not null check (rating >= 1 and rating <= 5),
    pros jsonb not null default '[]'::jsonb,
    cons jsonb not null default '[]'::jsonb,
    summary text not null,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

alter table public.reviews enable row level security;

create policy "Allow public read access" on public.reviews for select to anon, authenticated using (true);
create policy "Allow public insert access" on public.reviews for insert to anon, authenticated with check (true);
create policy "Allow public delete access" on public.reviews for delete to anon, authenticated using (true);
```

## 🔌 API Endpoints

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
    "sentiment": "positive",
    "rating": 4,
    "pros": [
      "Excellent camera quality",
      "Beautiful display",
      "Good battery life for normal use"
    ],
    "cons": [
      "Phone becomes hot while gaming"
    ],
    "summary": "The customer is satisfied with the phone's strong camera, display, and battery life, though it experiences heating issues during gaming."
  },
  "error": null
}
```

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

1. **Strict Model Validation**: AI outputs are parsed directly into Pydantic models with constrained types (`Literal["positive", "negative", "neutral"]` and `Field(ge=1, le=5)`).
2. **No Secret Leakage**: API keys remain strictly in backend memory and are never sent to the browser or returned in error traces.
3. **No Unsafe Code Execution**: Zero usage of `eval()` or unsanitized `dangerouslySetInnerHTML`.
4. **CORS Hardening**: CORS origins are restricted to configured client hosts.

---

## 🔮 Roadmap / Future Extensions

- [ ] **V2 - Bulk CSV Review Upload**: Upload `reviews.csv` with multiple columns and process batch reviews with progress tracking.
- [ ] **V3 - Advanced Analytics**: Word frequency cloud for pros/cons, rating distribution histograms, and multi-product comparisons.
- [ ] **V4 - Database Persistence**: Supabase / PostgreSQL schema integration with user sessions.
- [ ] **V5 - User Authentication**: Google OAuth and email/password sign-in.
- [ ] **V6 - Data Export**: Export reports to CSV, Excel, and PDF formats.

---

## 📜 License

MIT License. Designed for learning and production use.
