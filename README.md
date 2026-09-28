# ReviewIQ

> **AI-Powered Product Review Intelligence**

ReviewIQ is a full-stack AI application that converts unstructured e-commerce reviews into **structured, evidence-grounded and actionable product intelligence**.

Instead of treating a review as only positive or negative, ReviewIQ combines LLM-based language understanding with embeddings, semantic retrieval, RAG, structured validation, evidence grounding, multi-provider AI orchestration, reliability mechanisms, caching, evaluation, and observability.

**Core engineering principle:**  
> **LLM for intelligence, deterministic software for control.**

---

## 1. Problem

Large e-commerce products can have thousands or millions of customer reviews. A simple average rating does not explain:

- What customers like or dislike
- Which product aspects drive those opinions
- Whether sentiment is mixed
- Whether a rating was explicit or inferred
- What statements support an AI conclusion
- What customers say across a larger review corpus
- How the AI behaves when a provider fails or is rate-limited

ReviewIQ turns those unstructured reviews into structured product intelligence.

Example:

```text
"The display is excellent and the battery lasts all day,
but the camera struggles at night."

Overall sentiment: Mixed

Pros:
- Excellent display
- Good battery life

Cons:
- Poor low-light camera performance

Aspects:
- Display → Positive
- Battery → Positive
- Camera → Negative
```

---

## 2. Goals

ReviewIQ demonstrates practical AI/LLM engineering through:

1. LLM-based review understanding
2. Structured AI output
3. Evidence grounding
4. Aspect-level review intelligence
5. Embeddings
6. Semantic vector search
7. Retrieval-Augmented Generation (RAG)
8. LangGraph orchestration
9. AI provider abstraction
10. Multi-model/multi-provider fallback
11. Cost-aware routing
12. Retry and rate-limit handling
13. AI and embedding caching
14. Evaluation and regression testing
15. Safe AI observability
16. Product-level review intelligence

---

## 3. Scope

### Included

- Gemini-based review intelligence
- Gemini embeddings
- Vector retrieval
- RAG
- LangGraph
- AI Gateway/provider abstraction
- Gemini/Groq/OpenRouter providers
- Retry and fallback
- Cost-aware routing
- Caching
- Evaluation
- Observability
- Product/review intelligence

### Explicitly excluded

- Local LLM inference
- Ollama
- LM Studio
- llama.cpp
- GGUF models
- Local GPU inference
- Quantization
- Multi-agent architecture
- Exposed/stored chain-of-thought

---

# 4. High-Level Architecture

```text
                         USER
                           │
                           ▼
                 ┌───────────────────┐
                 │   React Frontend  │
                 │ TypeScript / Vite │
                 └─────────┬─────────┘
                           │ HTTP / JSON
                           ▼
                 ┌───────────────────┐
                 │  FastAPI Backend  │
                 │     Pydantic      │
                 └─────────┬─────────┘
                           ▼
                 ┌───────────────────┐
                 │   LangGraph Flow  │
                 └─────────┬─────────┘
                           │
                  ┌────────┴────────┐
                  │                 │
                  ▼                 ▼
             RAG Enabled       RAG Disabled
                  │                 │
                  ▼                 │
             Embeddings             │
                  │                 │
                  ▼                 │
          Vector Retrieval          │
          pgvector + HNSW           │
                  │                 │
                  ▼                 │
            RAG Context             │
                  │                 │
                  └────────┬────────┘
                           ▼
                  ┌───────────────────┐
                  │    AI Gateway     │
                  └─────────┬─────────┘
                            ▼
                   Provider Abstraction
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
          Gemini           Groq        OpenRouter
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                     Retry / Fallback
                            ▼
                    Structured LLM Output
                            ▼
                    Pydantic Validation
                            ▼
                    Evidence Grounding
                            ▼
                      Aspect Support
                            ▼
                       Cache/Store
                            ▼
                      Observability
                            ▼
                       Final Result
                            ▼
                       React UI
```

---

# 5. Core AI Flow

```text
User Review
    ↓
Input Validation
    ↓
LangGraph Orchestration
    ↓
Optional RAG Retrieval
    ↓
AI Gateway
    ↓
Routing
    ↓
Provider / Model
    ↓
Retry if transient failure
    ↓
Fallback if necessary
    ↓
Structured LLM Output
    ↓
Pydantic Validation
    ↓
Evidence Grounding
    ↓
Aspect Support
    ↓
Cache / Persistence
    ↓
Observability
    ↓
Final Review Intelligence
```

---

# 6. LLM Responsibilities

The LLM is used for tasks requiring language understanding/generation:

- Review understanding
- Sentiment
- Rating analysis
- Rating provenance
- Pros
- Cons
- Summary
- Aspect extraction
- Aspect-level sentiment
- Evidence generation/selection
- RAG-based synthesis

The LLM is **not treated as the final authority for correctness**. Deterministic application logic validates and controls generated output.

---

# 7. Structured Output

Conceptually:

```text
LLM
 ↓
Structured response
 ↓
Pydantic validation
 ↓
Application model
```

The analysis contract includes fields such as:

- sentiment
- rating
- rating source
- pros
- cons
- summary
- aspects
- evidence
- aspect support

This prevents arbitrary model text from becoming trusted application data.

---

# 8. Rating Provenance

ReviewIQ distinguishes:

```text
explicit
inferred
not_found
```

**Explicit:** customer directly supplied a rating.

**Inferred:** system estimated a rating from review text.

**Not found:** insufficient information exists to determine one.

This prevents an inferred AI value from being presented as the customer's original rating.

---

# 9. Evidence Grounding

LLMs can produce plausible statements that are not supported by the source review.

ReviewIQ validates evidence against the original review:

```text
Original Review
      ↓
LLM Analysis
      ↓
Evidence
      ↓
Normalization
      ↓
Containment Check
      ↓
Grounded Result
```

The implementation uses deterministic normalized containment and deterministic duplicate-evidence handling.

The system does not treat an arbitrary model confidence score as proof of support.

---

# 10. Aspect-Level Intelligence

A review can contain different opinions about different aspects:

```text
"The display is excellent but the camera is poor at night."

Display → Positive
Camera  → Negative
```

ReviewIQ can derive deterministic support levels:

```text
Strong
Moderate
Weak
```

These are based on grounding/evidence rules rather than invented numeric confidence.

Conceptually:

```text
Strong:
grounded + evidence supported + evidence mentions aspect

Moderate:
grounded + evidence mentions aspect

Weak:
grounded + evidence does not explicitly mention aspect
```

---

# 11. Embeddings

Configured embedding model:

```text
gemini-embedding-001
```

Configured vector dimension:

```text
768
```

Flow:

```text
Text
 ↓
Embedding Model
 ↓
Vector
 ↓
Vector Store
```

Embeddings allow reviews and queries to be represented in a semantic vector space.

---

# 12. Vector Search

The vector retrieval layer uses:

```text
PostgreSQL
+
pgvector
+
HNSW
+
cosine similarity
```

### Cosine similarity

Measures directional similarity between vectors and is useful for semantic nearest-neighbor retrieval.

### HNSW

An approximate nearest-neighbor indexing technique that makes vector search more efficient as the vector collection grows.

Important distinction:

```text
Cosine similarity → similarity measure
HNSW              → efficient nearest-neighbor indexing/search
```

---

# 13. Why Semantic Retrieval?

Keyword search depends heavily on lexical overlap.

Example:

```text
Query:
"battery life is poor"

Review:
"I need to charge the phone twice every day."
```

The wording differs, but the meaning is related.

Embedding-based retrieval can capture that semantic relationship.

Keyword search remains useful for exact matching and filtering; semantic retrieval is used because natural-language reviews express the same idea in many different ways.

---

# 14. RAG — Retrieval-Augmented Generation

RAG connects the LLM to ReviewIQ's review corpus.

Without RAG:

```text
Question
   ↓
LLM
   ↓
Answer
```

With RAG:

```text
Question
   ↓
Embedding
   ↓
Vector Retrieval
   ↓
Relevant Reviews
   ↓
Context
   ↓
LLM
   ↓
Answer
```

RAG is useful when an answer needs information from the application's actual review data.

---

# 15. RAG Retrieval States

The retrieval layer distinguishes:

```text
disabled
ok
empty
unavailable
invalid
```

**Empty:** retrieval worked but found no relevant results.

**Unavailable:** retrieval infrastructure could not be used.

**Invalid:** retrieval request or retrieved data failed validation.

The system must not fabricate retrieved evidence when no supporting context exists.

---

# 16. LangGraph

LangGraph is used as the orchestration layer.

Ordinary Python could implement the workflow, but LangGraph provides an explicit graph-based representation for multi-step AI execution and conditional paths.

Conceptually:

```text
Prepare
  ↓
Retrieve
  ↓
AI Gateway
  ↓
Validate
  ↓
Ground
  ↓
Finish
```

Failure paths can include:

```text
Model failure
     ↓
   Retry
     ↓
Fallback
```

LangGraph is therefore used because ReviewIQ has a multi-stage AI workflow with retrieval, validation, grounding, retry and fallback paths.

---

# 17. AI Gateway

The application separates AI business logic from provider-specific SDK details:

```text
Application
     ↓
AI Gateway
     ↓
Provider Abstraction
     ↓
Provider Adapter
```

### Gemini

```text
gemini-3.8-flash
gemini-flash-latest
gemini-3.6-flash
gemini-3.5-flash
gemini-3.5-flash-lite
```

### Groq

```text
openai/gpt-oss-120b
openai/gpt-oss-20b
qwen/qwen3.8-27b
```

### OpenRouter

```text
openrouter/free
```

The gateway makes provider-specific behavior easier to isolate and supports routing, retry and fallback.

---

# 18. Retry vs Fallback

### Retry

Retry means trying the **same target** again:

```text
Gemini Model A
      ↓
    429
      ↓
   Retry
      ↓
Gemini Model A
```

Retryable conditions include selected:

- Rate-limit failures
- Timeouts
- Transient failures

### Fallback

Fallback means switching to a **different target**:

```text
Gemini Model A
      ↓
    failure
      ↓
Gemini Model B
```

or:

```text
Gemini
  ↓
failure
  ↓
Groq
```

> **Retry = same target. Fallback = different target.**

---

# 19. Cost-Effective Routing

Supported routing strategies include:

```text
gemini_first
cost_aware
```

The default is:

```text
gemini_first
```

The cost-aware policy considers:

```text
Free-tier status
Verified total cost
Quality tier
Provider/model priority
Configured chain order
```

Unknown/unverified cost is handled conservatively rather than inventing a price.

No billing dashboard or cost API is exposed.

---

# 20. Reliability

AI providers can fail outside application control.

ReviewIQ uses bounded retries and supports:

- Rate-limit handling
- Timeout handling
- Transient failures
- Retry-After
- Exponential backoff
- Jitter
- Provider/model fallback

The system avoids indefinite retries.

---

# 21. Caching

ReviewIQ supports caching for:

- LLM responses
- Document embeddings
- Query embeddings

Conceptually:

```text
Request
  ↓
Cache lookup
  ├── HIT  → cached result
  └── MISS → AI/Embedding → Cache → Result
```

Configured TTL categories:

```text
LLM, RAG off        → 7 days
LLM, RAG on         → 1 hour
Document embeddings → 90 days
Query embeddings    → 30 days
```

Cache behavior is version-aware and designed to fail open in ordinary cases.

---

# 22. Evaluation

ReviewIQ contains a fixed evaluation set of:

```text
40 records
```

Important limitations:

- Expected rating is a genuine human label.
- Expected sentiment is a deterministic rating-derived pseudo-label.
- Sentiment labels are **not independent human annotations**.
- Quantitative aspect/evidence/RAG metrics are not claimed where reliable gold labels are unavailable.

The fixed set provides a stable basis for regression testing.

---

# 23. Testing

Testing covers:

- Backend unit/integration tests
- AI/provider tests
- RAG tests
- Grounding tests
- Retry/fallback tests
- Cache tests
- Evaluation/regression tests
- API contract tests
- Frontend tests
- TypeScript checks
- Production-build checks
- End-to-end verification

AI behavior is tested as software rather than treated as an untestable black box.

---

# 24. Observability

The fixed AI request outcome contains:

```text
request_id
task
outcome
provider
model
fallback
retry_attempts
retry_count
cache
rag_status
provider_latency_ms
total_ms
```

The system intentionally avoids logging:

- Raw review text
- Raw prompts
- RAG document bodies
- Provider response bodies
- API keys
- Database connection strings
- PII
- Billing information

This provides operational visibility without turning logs into a copy of user/AI data.

---

# 25. Product Intelligence

ReviewIQ supports:

- Product search
- Product summaries
- Review analysis
- Review exploration
- Pros and cons
- Themes
- Similar reviews
- Recommendations
- Review history
- Dataset-backed insights

Direct Review AI analysis can continue even when local dataset-backed product features are unavailable.

---

# 26. Local Dataset

Product Search, Dataset Explorer and Insights use gitignored local files under:

```text
backend/data/
```

Build the seeded local dataset:

```bash
python scripts/seed_sample_data.py
```

For full-scale product search:

```bash
python scripts/ingest_dataset.py
```

The dataset is intentionally not committed to Git.

Without dataset files:

- Direct Review AI analysis continues.
- Dataset-backed endpoints return safe failure responses until data is built.

---

# 27. Repository Structure

> This tree intentionally shows the **meaningful application structure**, not every generated or machine-specific file.

```text
ReviewIQ/
│
├── backend/
│   ├── data/
│   │   └── local / gitignored datasets
│   │
│   ├── models/
│   │   └── application and review contracts
│   │
│   ├── routes/
│   │   └── FastAPI API routes
│   │
│   ├── services/
│   │   ├── ai/
│   │   │   ├── contracts
│   │   │   ├── errors
│   │   │   ├── gateway
│   │   │   ├── provider registry
│   │   │   └── provider adapters
│   │   │
│   │   ├── embeddings/
│   │   │   └── embedding generation/configuration
│   │   │
│   │   ├── retrieval/
│   │   │   └── semantic retrieval/RAG support
│   │   │
│   │   └── observability.py
│   │       └── safe AI request telemetry
│   │
│   ├── tests/
│   │   └── backend/unit/integration/regression tests
│   │
│   └── main.py
│       └── FastAPI application entry point
│
├── frontend/
│   └── React / TypeScript / Vite application
│
├── scripts/
│   ├── seed_sample_data.py
│   └── ingest_dataset.py
│
├── docs/
│   └── project/design/decision documentation
│
├── README.md
└── project configuration files
```

### Structure rule

Do not interpret these as architecture:

- `.venv`
- `node_modules`
- Python/JS caches
- IDE metadata
- build output
- temporary files
- local secrets
- generated datasets
- local database files

The architecture should be understood from meaningful source directories and files.

---

# 28. Backend Architecture

Conceptually:

```text
Routes
  ↓
Application / AI orchestration
  ↓
Services
  ↓
Provider / Retrieval / Embedding abstractions
  ↓
External AI or local data systems
```

This separates HTTP concerns, business logic, AI orchestration, provider-specific logic, retrieval and validation.

---

# 29. Frontend Architecture

The frontend uses:

```text
React
+
TypeScript
+
Vite
+
Tailwind
```

Responsibilities:

1. Collect user input
2. Call backend APIs
3. Represent loading/error/empty states
4. Work with API contracts through TypeScript
5. Display AI/product intelligence
6. Provide product/review exploration
7. Display sentiment, rating, rating source, pros, cons, summary, aspects, evidence and support

Core LLM orchestration remains in the backend.

---

# 30. Backend ↔ Frontend Contract

```text
React / TypeScript
        ↕
       JSON
        ↕
FastAPI / Pydantic
```

The main analysis endpoint uses the established envelope:

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

Internal implementation metadata is not exposed merely because it exists internally.

---

# 31. AI Engineering Principles

### LLM for intelligence

Use the model where language understanding is valuable.

### Deterministic software for control

Use application code for:

- Validation
- Contracts
- Grounding
- Retry rules
- Routing
- Cache behavior
- Evaluation
- Observability

### Fail explicitly

Distinguish states such as:

```text
empty
unavailable
invalid
failure
```

instead of silently pretending success.

### Do not fabricate evidence

A plausible LLM statement is not automatically grounded.

### Document limitations

Evaluation and infrastructure limitations are stated instead of being presented as solved problems.

### Keep providers replaceable

Provider-specific SDK behavior stays behind provider abstractions.

---

# 32. AI Knowledge Map

A person responsible for the AI/LLM side should understand:

### LLM fundamentals

- Tokens
- Context windows
- Transformer architecture
- Self-attention
- Inference
- Temperature
- Prompt engineering

### Review intelligence

- Sentiment analysis
- Rating extraction
- Rating provenance
- Pros/cons extraction
- Summarization
- Aspect-based sentiment analysis

### Reliable generation

- Structured output
- Pydantic validation
- Evidence grounding
- Deterministic validation
- Hallucination control

### Retrieval

- Embeddings
- Vector representations
- Cosine similarity
- Nearest-neighbor search
- HNSW
- RAG
- Retrieval quality

### AI engineering

- LangGraph
- AI Gateway
- Provider abstraction
- Model routing
- Multi-provider fallback
- Retry
- Rate limits
- Timeouts
- Exponential backoff
- Jitter
- Retry-After

### AI performance

- LLM caching
- Embedding caching
- TTL
- Cache invalidation

### AI quality

- Evaluation datasets
- Regression testing
- Baselines
- Metrics
- Evaluation limitations

### AI operations

- Request correlation
- Provider latency
- Retry telemetry
- RAG status
- Safe observability
- Sensitive-data handling

---

# 33. Viva Framework

For every AI component, explain it using:

> **What is it? → Why did we use it? → How does it work in ReviewIQ? → What happens when it fails?**

Example: RAG

**What?** Retrieval-Augmented Generation.

**Why?** To give the LLM relevant review-corpus context.

**How?** Query → embedding → vector search → retrieved reviews → LLM.

**Failure?** Explicit retrieval states such as empty/unavailable/invalid prevent the system from pretending supporting context exists.

---

# 34. Key Technical Questions

### Why Gemini embeddings?

We use `gemini-embedding-001` because it integrates with the existing Gemini-based AI stack and provides embeddings for semantic retrieval.

### Why 768 dimensions?

768 is the configured dimensionality of the embedding pipeline. The vector-store schema is configured to match it.

### Why cosine similarity?

It measures directional similarity between embedding vectors, which is useful for semantic nearest-neighbor retrieval.

### Why HNSW?

HNSW is an approximate nearest-neighbor index that makes vector search more efficient as the collection grows.

### Why not keyword search?

Keyword search depends heavily on lexical overlap. Semantic retrieval can identify related meaning even when the wording differs.

### Why RAG?

RAG retrieves relevant application-specific review data and provides it to the LLM as context.

### What if retrieval returns nothing?

The system records an explicit empty retrieval state and does not fabricate supporting context.

### Why LangGraph?

Ordinary Python could implement the workflow, but LangGraph provides explicit graph-based orchestration for the multi-step AI workflow and conditional paths.

### Retry vs fallback?

Retry repeats the same target. Fallback switches to another model/provider.

### Why an AI Gateway?

It decouples application logic from individual AI providers and centralizes provider abstraction, routing, retry and fallback behavior.

---

# 35. What Makes ReviewIQ an LLM Engineering Project?

It is not simply:

```text
Review
  ↓
Gemini API
  ↓
Answer
```

It is:

```text
Customer Review
      ↓
LLM Understanding
      ↓
Structured Output
      ↓
Deterministic Validation
      ↓
Evidence Grounding
      ↓
Aspect Intelligence
      ↓
Embedding / Retrieval
      ↓
RAG
      ↓
LangGraph Orchestration
      ↓
AI Gateway
      ↓
Model Routing
      ↓
Retry / Fallback
      ↓
Caching
      ↓
Evaluation
      ↓
Observability
      ↓
Product Intelligence
```

The project demonstrates both **AI capability** and **AI engineering discipline**.

---

# 36. Local Development

### Backend

Use the project's Python environment and dependency configuration, then start the FastAPI application using its configured entry point.

### Frontend

Install frontend dependencies and start the Vite development server using the configured frontend scripts.

### AI configuration

Provider credentials are supplied through environment variables and must never be committed to Git.

### Dataset-backed features

Build local dataset files when using Product Search, Dataset Explorer or Insights:

```bash
python scripts/seed_sample_data.py
```

For the full dataset:

```bash
python scripts/ingest_dataset.py
```

---

# 37. Development Workflow

```text
Inspect
  ↓
Implement
  ↓
Test
  ↓
Review diff
  ↓
Document
  ↓
User manually commits
  ↓
User pushes
```

Coding agents must **not** commit or push project changes.

---

# 38. Project Philosophy

> **Quality over Quantity.**

The goal is not to add AI buzzwords or unnecessary components.

Every major technology should answer:

```text
What problem does this solve?
Why is it needed?
How does it work?
How do we validate it?
What happens when it fails?
```

That is the standard used throughout ReviewIQ.
