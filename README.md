**# ReviewIQ — AI-Powered Product Review Intelligence**

\> **\*\*Turn unstructured customer feedback into evidence-backed product intelligence.\*\***

**\*\*ReviewIQ\*\*** is a full-stack AI application that transforms raw product reviews into structured, explainable insights. Instead of returning free-form LLM text, ReviewIQ produces validated sentiment, rating information, aspect-level opinions, pros, cons, summaries, and—most importantly—evidence tied back to the original review.

**\*\*V1 is feature-complete, tested, live, and deployment-ready.\*\***

**---**

**## 1. What ReviewIQ Solves**

Product reviews contain valuable information, but manually extracting consistent insights from them is slow and difficult to scale.

ReviewIQ provides a structured analysis pipeline:

\`\`\`text

Customer Review

      │

      ▼

Request Validation

      │

      ▼

Gemini AI Analysis

      │

      ▼

Structured Output Validation

      │

      ▼

Evidence Grounding

      │

      ▼

Validated Review Intelligence

      │

      ├── Sentiment

      ├── Rating + rating source

      ├── Pros + evidence

      ├── Cons + evidence

      ├── Aspect sentiment + evidence

      └── Summary

\`\`\`

The V1 architecture deliberately prioritizes **\*\*reliability, explainability, deterministic validation, and practical deployment\*\*** over unnecessary AI complexity.

**---**

**# 2. V1 Feature Set**

**## Core AI Analysis**

\- **\*\*Structured JSON analysis\*\*** validated with Pydantic.

\- **\*\*Overall sentiment\*\***: \`positive | negative | neutral | mixed\`.

\- **\*\*Rating extraction\*\*** on a 1–5 scale.

\- **\*\*Rating honesty\*\*** with provenance:

  - \`explicit\`

  - \`inferred\`

  - \`not_found\`

\- **\*\*Aspect-Based Sentiment Analysis (ABSA)\*\***.

\- **\*\*Pros and cons extraction\*\***.

\- **\*\*Executive-style review summary\*\***.

\- **\*\*Evidence-backed insights\*\*** for pros, cons, and aspects.

\- **\*\*Evidence grounding validation\*\*** against the original review text.

\- Unsupported evidence is automatically rejected instead of being presented as fact.

**## AI Reliability**

\- **\*\*Gemini-first model strategy\*\***.

\- Deterministic **\*\*Gemini-only fallback pool\*\***.

\- Up to **\*\*5 verified Gemini models\*\*** in a controlled order.

\- Automatic fallback when a model returns an empty or invalid response.

\- Every fallback attempt goes through the same generation → parsing → Pydantic validation → grounding pipeline.

\- Grounding-filtered but otherwise valid results are accepted without unnecessary fallback.

**## Product Intelligence**

\- Product intelligence dashboard.

\- Review history.

\- Search and sentiment filtering.

\- Detailed review inspection.

\- Dataset analytics.

\- Product analytics.

\- Recommendation/comparison functionality retained in V1.

\- Responsive dashboard experience.

**## Persistence**

\- Supabase PostgreSQL persistence.

\- \`localStorage\` fallback for demo/development resilience.

\- Persistent rating source, aspects, evidence, sentiment, pros, cons, and summary.

\- Delete and clear-history functionality.

\- V1 demo-oriented Supabase RLS posture documented below.

**## Quality & Engineering**

\- FastAPI API layer.

\- Pydantic contract validation.

\- LangGraph orchestration.

\- Automated backend test suite.

\- Frontend tests with Vitest.

\- Production frontend build verification.

\- Safe API error handling.

\- Environment-based secret management.

\- CORS configuration.

\- No backend dependency on Supabase for AI analysis.

**---**

**# 3. The V1 Differentiator: Evidence Grounding**

ReviewIQ does not treat an LLM-generated explanation as automatically trustworthy.

For every evidence-backed insight, the system verifies that the normalized evidence actually occurs in the original review.

Example:

\`\`\`json

{

  "pros": [

    {

      "point": "Excellent battery life",

      "evidence": "The battery easily lasts two full days."

    }

  ],

  "cons": [

    {

      "point": "Expensive",

      "evidence": "The only downside is the high price."

    }

  ]

}

\`\`\`

The grounding layer normalizes text before comparison, including Unicode normalization, quote/apostrophe normalization, non-breaking-space normalization, case folding, punctuation normalization while preserving word boundaries, and whitespace normalization.

The complete normalized evidence must be supported by the original review.

**### Why this matters**

This turns ReviewIQ from a simple **\*\*"LLM says this"\*\*** application into an **\*\*evidence-backed analysis system\*\***.

The model may generate an interpretation, but the application decides whether the supporting evidence is actually present in the source review.

**---**

**# 4. Rating Honesty**

ReviewIQ distinguishes between what the customer explicitly stated and what the model inferred.

\`\`\`json

{

  "rating": 4,

  "rating_source": "explicit"

}

\`\`\`

or:

\`\`\`json

{

  "rating": 4,

  "rating_source": "inferred"

}

\`\`\`

or:

\`\`\`json

{

  "rating": null,

  "rating_source": "not_found"

}

\`\`\`

The contract enforces the relationship between these fields, preventing a missing rating from silently becoming a fabricated numeric fact.

**---**

**# 5. AI Orchestration**

V1 uses a single LangGraph orchestration path:

\`\`\`text

Review Input

     │

     ▼

Analyze Request

     │

     ▼

Gemini Primary

     │

     ▼

Structured Validation

     │

     ▼

Evidence Grounding

     │

     ▼

Final Response

\`\`\`

If a model attempt fails:

\`\`\`text

Gemini Primary

     │

     ├── success ───────────────► Validation ─► Grounding ─► Final

     │

     └── failure

            │

            ▼

      Next Gemini Model

            │

            ▼

        Validation

            │

            ▼

         Grounding

            │

            ▼

          Final

\`\`\`

**### V1 deliberately does not include**

\- Chain-of-Thought prompting

\- RAG

\- multi-provider fallback

\- cost-based model selection

\- model quantization

\- local LLM inference

\- caching

\- multi-agent architecture

These are intentionally outside the V1 scope.

**---**

**# 6. Technology Stack**

\| Layer | Technology |

\|---|---|

\| Frontend | React, TypeScript, Vite, Tailwind CSS, Axios, Lucide React |

\| Backend | Python, FastAPI, Uvicorn |

\| Validation | Pydantic v2 |

\| AI | Google Gemini API |

\| Orchestration | LangGraph |

\| Database | Supabase PostgreSQL |

\| Local persistence fallback | Browser \`localStorage\` |

\| Backend testing | pytest |

\| Frontend testing | Vitest |

\| Source control | Git + GitHub |

\| Backend deployment | Render |

\| Frontend deployment | Vercel |

\| AI service | Google Gemini API |

**---**

**# 7. Project Structure**

\`\`\`text

ReviewIQ/

│

├── frontend/

│   ├── src/

│   │   ├── components/

│   │   ├── pages/

│   │   │   └── Dashboard.tsx

│   │   ├── services/

│   │   │   ├── api.ts

│   │   │   ├── historyStorage.ts

│   │   │   └── supabase.ts

│   │   ├── types/

│   │   ├── App.tsx

│   │   └── main.tsx

│   ├── package.json

│   └── vite.config.ts

│

├── backend/

│   ├── main.py

│   ├── requirements.txt

│   ├── .env.example

│   ├── models/

│   ├── routes/

│   ├── services/

│   │   ├── ai_analyzer.py

│   │   ├── analysis_graph.py

│   │   ├── grounding_service.py

│   │   └── ...

│   ├── scripts/

│   └── tests/

│

├── supabase_schema.sql

├── README.md

└── .gitignore

\`\`\`

**---**

**# 8. Environment Configuration**

**## Backend**

Create \`backend/.env\`:

\`\`\`ini

GEMINI_API_KEY=your_gemini_api_key_here

HOST=127.0.0.1

PORT=8000

ALLOWED_ORIGINS=http\://localhost:5173,http\://127.0.0.1:5173

\`\`\`

The Gemini API key must remain server-side.

**## Frontend**

Create \`frontend/.env\`:

\`\`\`ini

VITE_API_BASE_URL=http\://localhost:8000

VITE_SUPABASE_URL=https\://your-project.supabase.co

VITE_SUPABASE_ANON_KEY=your-supabase-anon-key

\# or

VITE_SUPABASE_PUBLISHABLE_KEY=your-supabase-publishable-key

\`\`\`

\> **\*\*Security:\*\*** Never put \`GEMINI_API_KEY\` or a Supabase service-role key in the frontend environment.

Vite embeds \`VITE\_\*\` variables into the frontend build, so frontend environment changes require restarting the development server or rebuilding.

**---**

**# 9. Local Development**

**## Backend**

\`\`\`bash

cd backend

python -m venv .venv

\`\`\`

**### Windows**

\`\`\`bash

.venv\Scripts\activate

\`\`\`

**### macOS / Linux**

\`\`\`bash

source .venv/bin/activate

\`\`\`

Install dependencies:

\`\`\`bash

pip install -r requirements.txt

\`\`\`

Create the environment file:

\`\`\`bash

copy .env.example .env

\`\`\`

On macOS/Linux:

\`\`\`bash

cp .env.example .env

\`\`\`

Add the Gemini API key, then start FastAPI:

\`\`\`bash

uvicorn main\:app --reload --port 8000

\`\`\`

Backend: \`http\://localhost:8000\`

Swagger: \`http\://localhost:8000/docs\`

Health check: \`http\://localhost:8000/health\`

**## Frontend**

In a second terminal:

\`\`\`bash

cd frontend

npm install

npm run dev

\`\`\`

**---**

**# 10. Supabase Setup**

The canonical schema is available in:

\`\`\`text

supabase_schema.sql

\`\`\`

The V1 \`reviews\` table stores:

\- review text

\- sentiment

\- nullable rating

\- rating source

\- pros

\- cons

\- aspect analysis

\- summary

\- creation timestamp

The schema also contains the required rating and sentiment constraints.

**### V1 demo RLS posture**

The current V1 demo configuration permits anonymous/authenticated:

\- \`SELECT\`

\- \`INSERT\`

\- \`DELETE\`

There is intentionally no \`UPDATE\` policy.

\> **\*\*Important:\*\*** This posture is suitable for the V1 demonstration environment. It is **\*\*not\*\*** a multi-tenant production authorization model.

**---**

**# 11. API**

**## Health**

\`\`\`http

GET /health

\`\`\`

Example:

\`\`\`json

{

  "status": "ok",

  "service": "Product Review Analyzer Backend",

  "version": "1.0.0",

  "ai_provider": "Google Gemini",

  "ai_configured": true

}

\`\`\`

**## Analyze Review**

\`\`\`http

POST /api/analyze-review

\`\`\`

Request:

\`\`\`json

{

  "review": "The camera quality is excellent and the display is beautiful. Battery life is good for normal use, but the phone becomes hot while gaming. Overall I am happy with the product."

}

\`\`\`

Response shape:

\`\`\`json

{

  "success": true,

  "data": {

    "sentiment": "mixed",

    "rating": 4,

    "rating_source": "inferred",

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

\`\`\`

The complete API contract is maintained in:

\`docs/08_API_CONTRACT.md\`

**---**

**# 12. Testing & V1 Verification**

**### Backend**

\`\`\`bash

python -m pytest backend/tests

\`\`\`

**### Frontend**

\`\`\`bash

cd frontend

npm test

npm run build

\`\`\`

The V1 verification suite covers:

\- request validation

\- Pydantic output contracts

\- rating-source rules

\- sentiment behavior

\- ABSA scenarios

\- evidence grounding

\- invalid and empty AI responses

\- Gemini fallback orchestration

\- API error handling

\- API endpoint contracts

\- product endpoints

\- dataset/analytics/evaluation endpoints

\- persistence-related contracts

\- model configuration

\- security-sensitive error behavior

Gemini and Supabase are mocked/faked for automated backend tests, so the backend test suite does not require live external services.

V1 also underwent live end-to-end verification against the deployed application and Supabase persistence, including positive, negative, mixed, explicit-rating, inferred-rating, evidence-grounding, and no-rating scenarios.

**---**

**# 13. Production Deployment**

V1 deployment stack:

\`\`\`text

                 ┌──────────────────┐

                 │      Vercel      │

                 │ React + Vite UI  │

                 └────────┬─────────┘

                          │

                          ▼

                 ┌──────────────────┐

                 │      Render      │

                 │ FastAPI Backend  │

                 └────────┬─────────┘

                          │

                 ┌────────┴─────────┐

                 ▼                  ▼

        ┌────────────────┐  ┌────────────────┐

        │ Google Gemini  │  │    Supabase    │

        │       AI       │  │   PostgreSQL   │

        └────────────────┘  └────────────────┘

\`\`\`

**### Render Backend**

The V1 backend is deployed on Render with:

\`\`\`text

Root Directory: backend

Build Command: pip install -r requirements.txt

Start Command: uvicorn main\:app --host 0.0.0.0 --port $PORT

Health Check: /health

\`\`\`

The deployed service responds successfully to \`/health\`.

\> The backend root URL \`/\` is not an application page and may return \`404 Not Found\`. This is expected; \`/health\` is the service health endpoint and \`/docs\` exposes the FastAPI API documentation.

**### Vercel Frontend**

The frontend deployment uses:

\`\`\`text

VITE_API_BASE_URL=\<deployed Render backend URL>

VITE_SUPABASE_URL=\<Supabase project URL>

VITE_SUPABASE_ANON_KEY=\<Supabase anon key>

\`\`\`

**---**

**# 14. V1 Completion Status**

**## V1 — 100% Complete**

\| Area | Status |

\|---|:---:|

\| Core review analysis | ✅ |

\| Structured AI contract | ✅ |

\| Sentiment | ✅ |

\| Rating extraction | ✅ |

\| Rating provenance | ✅ |

\| ABSA | ✅ |

\| Pros / cons | ✅ |

\| Evidence grounding | ✅ |

\| Summary generation | ✅ |

\| Gemini fallback | ✅ |

\| LangGraph orchestration | ✅ |

\| API validation | ✅ |

\| Error handling | ✅ |

\| Product intelligence | ✅ |

\| Dataset analytics | ✅ |

\| Review history | ✅ |

\| Supabase persistence | ✅ |

\| Local persistence fallback | ✅ |

\| Automated backend tests | ✅ |

\| Frontend tests | ✅ |

\| Production build | ✅ |

\| Render backend deployment | ✅ |

\| V1 scope audit | ✅ |

\| Live end-to-end verification | ✅ |

**\*\*V1 completion: 100%\*\***

**---**

**# 15. Intentionally Deferred from V1**

These are deliberate future-scope decisions, not incomplete V1 requirements:

\- RAG

\- Vector database / ChromaDB

\- Chain-of-Thought prompting

\- multi-provider AI fallback

\- cost-aware model routing

\- response caching

\- local model inference

\- model quantization

\- multi-agent architecture

\- authentication

\- multi-tenant authorization

\- bulk review processing

\- advanced report export

V1 intentionally establishes a reliable and explainable foundation before introducing additional architectural complexity.

**---**

**# 16. V2 Direction

V2 extends the proven V1 pipeline into a **retrieval-augmented, evidence-grounded, cost-aware multi-model review intelligence system**.

V2 is intentionally designed as a **cloud/API-first architecture**. It does not introduce local LLM inference, model quantization, or multi-agent infrastructure.

## V2 Core Architecture

```text
                         ReviewIQ V2
                              │
                ┌─────────────▼─────────────┐
                │      Review API / UI      │
                └─────────────┬─────────────┘
                              │
                ┌─────────────▼─────────────┐
                │ Validation + Preprocessing│
                └─────────────┬─────────────┘
                              │
                ┌─────────────▼─────────────┐
                │       LangGraph           │
                │      Orchestrator         │
                └─────────────┬─────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Cache Check     │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │    Embeddings     │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │    Vector DB      │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Semantic Search  │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │   RAG Context     │
                    │      Builder      │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Cost-Aware Model  │
                    │      Router       │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │    AI Gateway     │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼────────────────┐
              │               │                │
          Gemini Models   Free-Tier Model   Other Provider
              │               │                │
              └───────────────┼────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Output Validation │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Evidence +        │
                    │ Confidence        │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Final Intelligence│
                    └───────────────────┘
```

## V2 Locked Feature Set

### Foundation

- V2 service and module boundaries.
- Unified dataset and manual-review analysis pipeline.
- Environment-based configuration and secret management.
- Cloud/API-first AI architecture.

### Review and Data Layer

- Dataset validation.
- Enhanced review preprocessing.
- Duplicate and near-duplicate review handling.
- Structured review metadata.

### Embeddings and Vector Search

- Cloud embedding generation.
- Provider-independent embedding abstraction.
- Vector database integration.
- Review metadata associated with vectors.
- Semantic similarity search.
- Metadata filtering.
- Embedding failure handling.

### Retrieval-Augmented Generation

- RAG retrieval pipeline.
- Top-K retrieval.
- Similarity thresholds.
- Metadata-aware retrieval.
- RAG context builder.
- Context-size management.
- Context-aware prompt construction.
- Retrieval metadata and similarity information.
- Safe no-result handling.
- RAG integration with the existing analysis contract.

### Evidence Grounding

- Evidence extraction.
- Evidence-to-conclusion mapping.
- Evidence relevance filtering.
- Evidence display in the UI.
- Grounded versus ungrounded result handling.
- Reuse and extension of V1's existing grounding validation.

### Multi-Model and Multi-Provider AI

V2 expands V1's Gemini-only fallback strategy.

```text
Primary task
    │
    ▼
Cost-Aware Model Router
    │
    ▼
Selected Model
    │
    ├── success ───────────────► Output Validation
    │
    └── failure
           │
           ▼
      Gemini Model Fallbacks
           │
           └── exhausted
                  │
                  ▼
          Free-Tier Provider Models
                  │
                  ▼
             Final fallback
```

V2 includes:

- AI provider abstraction.
- AI gateway.
- Gemini multi-model fallback.
- Configurable Gemini model order.
- Multi-provider fallback.
- Suitable free-tier API models/providers where available.
- Common provider request/response contract.
- Provider error normalization.
- Provider availability tracking.
- Timeout and retry handling.

Free-tier availability is configuration-dependent and may change over time; providers and models are therefore treated as replaceable adapters rather than permanent assumptions.

### Cost-Effective Model Selection

V2 separates **routing** from **fallback**.

**Routing** decides which model should be used first.

**Fallback** decides what to try when the selected model fails.

The model registry records information such as:

- Provider.
- Model.
- Task capability.
- Context capacity.
- Structured-output capability.
- Estimated cost.
- Expected latency.
- Quality tier.
- Availability/quota information.

The router can use:

```text
Task
+
Task complexity
+
Quality requirement
+
Token requirement
+
Estimated cost
+
Latency
+
Provider availability
+
Free-tier/quota availability
```

to select an appropriate model.

### LangGraph Orchestration

LangGraph coordinates the V2 analysis workflow and conditional recovery paths.

```text
START
  │
  ▼
Validate Input
  │
  ▼
Check Cache
  │
  ▼
Generate Embedding
  │
  ▼
Retrieve Context
  │
  ▼
Build RAG Context
  │
  ▼
Select Model
  │
  ▼
AI Gateway
  │
  ▼
Validate Output
  │
  ├── invalid ──► retry / alternate model
  │
  ▼
Evidence Check
  │
  ▼
Confidence
  │
  ▼
END
```

LangGraph is used for orchestration and controlled branching, not for exposing or storing model chain-of-thought.

### AI Reliability

- Structured AI output.
- Schema validation.
- Automatic retry.
- Exponential backoff for transient failures.
- Rate-limit handling.
- Timeout handling.
- Provider failure handling.
- Model/provider fallback.
- Safe error normalization.

### Advanced Review Intelligence

- Aspect extraction.
- Aspect-level sentiment.
- Customer pain-point detection.
- Positive pattern detection.
- Topic extraction.
- Evidence-based summaries.
- Review-level confidence/uncertainty signal.

### Caching and Efficiency

- LLM response caching.
- Embedding caching.
- TTL/invalidation strategy.
- Cache-hit/cache-miss tracking.
- Reduced repeated provider calls.

### Evaluation and Quality

- Fixed V2 evaluation dataset.
- V1 versus V2 comparison.
- RAG retrieval evaluation.
- Evidence relevance checks.
- Structured-output validity checks.
- Model/fallback behavior tests.
- Regression testing.

### Observability and Cost Tracking

- Request logging.
- Provider/model logging.
- Latency tracking.
- Fallback tracking.
- Token usage tracking.
- Estimated AI cost tracking.
- RAG retrieval logging.
- Model-selection logging.

### Product Integration

- Manual review → V2 analysis.
- Dataset → V2 analysis.
- RAG evidence shown in the UI.
- Aspect-level sentiment shown in the UI.
- Confidence/uncertainty shown in the UI.
- Clear AI error/fallback states.
- V2 end-to-end integration testing.

## V2 Explicit Exclusions

V2 remains cloud/API-first and does **not** include:

- Local LLM inference.
- Ollama.
- LM Studio.
- llama.cpp.
- Local GPU inference.
- GGUF models.
- Model quantization.
- Self-hosted LLM serving.
- Multi-agent architecture.
- Exposed or stored chain-of-thought.

These are outside the locked V2 scope.

## V2 Implementation Status

V2 is being implemented incrementally on the `v2-main` branch.

| Area | Status |
|---|:---:|
| V2 scope and architecture | 🔒 Locked |
| V2 README / documentation baseline | 🔄 In progress |
| V2 foundation | ⏳ |
| AI gateway | ⏳ |
| Gemini multi-model fallback | ⏳ |
| Multi-provider fallback | ⏳ |
| Cost-aware model routing | ⏳ |
| LangGraph V2 orchestration | ⏳ |
| Embeddings | ⏳ |
| Vector database | ⏳ |
| Semantic search | ⏳ |
| RAG pipeline | ⏳ |
| Evidence grounding expansion | ⏳ |
| Aspect-level intelligence | ⏳ |
| Caching | ⏳ |
| Reliability / rate-limit handling | ⏳ |
| Evaluation / regression testing | ⏳ |
| Observability / cost tracking | ⏳ |
| End-to-end V2 integration | ⏳ |
| V2 production readiness | ⏳ |

**V2 status:** Architecture and scope locked; implementation in progress.

---

# 17. Engineering Principles**

**### Evidence before confidence**

An insight is more useful when the user can trace it back to the source review.

**### Structured output over free-form output**

Machine-readable contracts make AI behavior testable and predictable.

**### Validation at boundaries**

AI output is not trusted simply because it is valid JSON. It must satisfy the application schema and grounding rules.

**### Graceful degradation**

Model failure should trigger a controlled fallback rather than silently returning an unreliable result.

**### Keep the architecture understandable**

V1 intentionally avoids RAG, agents, caching, local models, and other advanced components before they are needed.

**### Build, test, review, freeze**

Features are implemented against explicit contracts and verified before V1 is considered complete.

**---**

**# 18. Team Structure**

\| Area | Responsibility |

\|---|---|

\| **\*\*Rishi\*\*** | AI/NLP, analysis pipeline, testing & QA |

\| **\*\*Sri\*\*** | Backend, data, API & persistence |

\| **\*\*Alshifa\*\*** | Frontend, dashboard & product experience |

The project follows a collaborative, phase-based implementation and verification workflow.

**---**

**# 19. License**

MIT License.

**---**

**## ReviewIQ V1**

\> **\*\*AI can generate the insight. ReviewIQ verifies the evidence.\*\***