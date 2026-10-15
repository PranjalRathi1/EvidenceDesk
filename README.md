# EvidenceDesk

An evidence-first document question-answering app. Upload PDFs, ask questions about
them, and get answers where every claim is tied to a verbatim, page-numbered quote
from your own documents — verified, not just asserted. When the documents don't
contain the answer, EvidenceDesk says so instead of guessing.

## 1. What it does

- Upload PDFs into a "collection" (e.g. a course or research topic).
- Ask a question; the system retrieves relevant passages, generates an answer
  grounded only in those passages, and breaks the answer into individual claims.
- Each claim carries a citation (document, page, exact quote) and a verification
  status: **Supported**, **Weak**, or **Not found** — computed by two independent
  checks, not asserted by the model that wrote the answer.
- If the evidence doesn't support an answer, EvidenceDesk refuses rather than
  guessing, and shows the most relevant passages it did find.
- An evaluation harness measures retrieval quality, citation accuracy, refusal
  behavior, and latency against a labelled question set, and compares retrieval
  configurations (vector / keyword / hybrid / hybrid+rerank) on the same data.

## 2. The problem it solves

General-purpose "chat with your PDF" tools produce confident-sounding prose with
citations that may not actually say what's claimed, or may not exist in the
source at all. EvidenceDesk treats that as the central risk for a study tool and
designs around it: every citation's quote is checked against the actual source
text (not just trusted), every claim's support is independently judged, and the
system is built to refuse rather than fabricate when evidence is thin.

## 3. Features implemented today

- Page-aware PDF extraction (PyMuPDF) with per-page text, scanned/image-only
  detection (refuses to silently index blank OCR-needed pages), and duplicate
  upload detection via content hash.
- Chunking with page + character-offset metadata preserved end to end.
- Local embeddings (Ollama, `nomic-embed-text`) and local generation
  (Ollama, `qwen2.5:7b`) — no paid API required.
- Vector search (Chroma, embedded/persistent, no server), BM25 keyword search,
  Reciprocal Rank Fusion hybrid retrieval, and an optional cross-encoder reranker.
- Structured, schema-validated answer generation (Pydantic) with per-claim
  citations.
- Two-layer verification: (1) deterministic exact-quote-exists check against the
  cited chunk, whitespace-normalized but never fuzzy; (2) an LLM-judge semantic
  support check, which only runs if layer 1 passes, and fails safe (never
  auto-upgrades to "supported") if the judge call errors or returns garbage.
- One bounded retry: if verification support is too low, the system regenerates
  once with feedback about which quotes failed, then refuses if it's still
  insufficient.
- A React/TypeScript frontend: document workspace (upload, status, delete),
  question interface with citation chips and verification badges, a source-page
  viewer, and an evaluation dashboard.
- A FastAPI backend with OpenAPI docs, typed request/response models, and
  sensible HTTP status codes.
- 45 backend tests (pytest) covering extraction, chunking, verification,
  retrieval, document lifecycle, and the full API, using deterministic fakes for
  the LLM/embedding calls so the suite doesn't require Ollama to be running.
- A 54-case labelled evaluation dataset (synthetic sample documents, generated
  programmatically) and a one-command evaluation runner.

## 4. Features not yet implemented

- OCR for scanned PDFs (explicitly out of scope per the project brief; scanned
  pages are detected and reported, not silently indexed as empty).
- A hosted LLM provider for comparison (`hosted_provider_enabled` exists as a
  config seam in `app/llm_client.py`, but no hosted integration was implemented —
  doing so without a verified account/key would mean inventing capabilities).
- Precise on-page highlight-rectangle rendering of the cited quote. The source
  viewer shows the exact quote text in a callout and the full page text below it,
  rather than attempting a highlight overlay that could point at the wrong text
  if character offsets and PDF rendering ever disagree.
- Multi-user accounts/auth (intentionally out of scope — single-user prototype).
- Alembic migrations (schema is created via `create_all`; see `DECISIONS.md`).

## 5. Architecture

```
┌─────────────────┐      HTTP (JSON / multipart)      ┌──────────────────────┐
│  React frontend  │ ───────────────────────────────▶ │   FastAPI backend     │
│  (Vite + TS)     │ ◀─────────────────────────────── │   (app/main.py)       │
└─────────────────┘                                    └──────────┬───────────┘
                                                                    │
                   ┌────────────────────────────────────────────────────────────┐
                   │                                                            │
         ┌─────────▼─────────┐   ┌──────────────────┐   ┌─────────────────────┐ │
         │  document_service │   │    retrieval      │   │     generation       │ │
         │  (ingest pipeline)│   │ vector + BM25 +    │   │  structured answer + │ │
         │  PyMuPDF, chunking│   │ RRF fusion +       │   │  claims + retry/     │ │
         └─────────┬─────────┘   │ optional rerank    │   │  refusal workflow    │ │
                   │             └─────────┬──────────┘   └──────────┬───────────┘ │
                   │                       │                          │            │
         ┌─────────▼─────────┐   ┌─────────▼──────────┐   ┌──────────▼───────────┐ │
         │  SQLite (SQLAlchemy)│  │  Chroma (embedded) │   │     verification      │ │
         │  collections/docs/  │  │  vector store       │   │  exact-quote check +  │ │
         │  chunks/query logs  │  │                     │   │  LLM-judge support     │ │
         └──────────────────────┘ └──────────────────────┘ └───────────┬───────────┘ │
                                                                         │             │
                                                              ┌──────────▼───────────┐ │
                                                              │   Ollama (local)      │◀┘
                                                              │ qwen2.5:7b (chat) +    │
                                                              │ nomic-embed-text       │
                                                              └────────────────────────┘
```

Everything runs locally: no Docker, no cloud database, no paid API.

## 6. Technology stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | FastAPI + Pydantic | typed, OpenAPI docs for free |
| PDF extraction | PyMuPDF (`fitz`) | page-aware, also used to generate the sample PDFs |
| Metadata DB | SQLite via SQLAlchemy | see `DECISIONS.md` for why not Postgres |
| Vector store | Chroma, embedded/persistent | no Docker/server needed |
| Keyword search | `rank-bm25` | pure Python |
| Reranker | `sentence-transformers` cross-encoder | optional, CPU-only, lazy-loaded |
| LLM + embeddings | Ollama (`qwen2.5:7b`, `nomic-embed-text`) | fully local |
| Frontend | React + TypeScript + Vite | no component framework dependency |
| Tests | pytest (backend), `tsc` + `vite build` (frontend) | |

See `DECISIONS.md` for the reasoning behind each deviation from the originally
recommended stack (Postgres/Docker).

## 7. Prerequisites

- Windows with PowerShell (this was built and tested on Windows 11).
- Python 3.13 (Python 3.11+ should work).
- Node.js 20+ and npm.
- [Ollama](https://ollama.com) installed and running locally.
- ~2GB free disk for the Python venv (incl. CPU torch for the optional reranker)
  and ~5GB for the two Ollama models (one of which you likely already have).

## 8. Setup

From the project root (`C:\Users\rathi\Desktop\EvidenceDesk`):

```powershell
# Backend
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env   # defaults work out of the box

# Frontend
cd ..\frontend
npm install
```

## 9. Configuring Ollama and model names

```powershell
ollama pull nomic-embed-text   # ~274MB, embeddings
ollama pull qwen2.5:7b         # ~4.7GB, chat/generation/judge — reuse any model you already have
```

Model names are set in `backend/.env` (`LLM_MODEL`, `EMBEDDING_MODEL`) or left at
their defaults (`qwen2.5:7b`, `nomic-embed-text`). Any Ollama chat model that
supports `"format": "json"` constrained output will work as `LLM_MODEL`.

## 10. Running the app

```powershell
# Terminal 1 — backend (from backend/)
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend (from frontend/)
npm run dev
```

Open http://localhost:5173. The backend serves its OpenAPI docs at
http://localhost:8000/docs.

## 11. Running tests

```powershell
cd backend
.venv\Scripts\python -m pytest tests/ -v
```

**Actual result at time of writing: 45 passed, 0 failed, ~6s.** These tests use
deterministic fakes for the embedding/chat calls (see `tests/conftest.py`) so they
do not require Ollama to be running; they do exercise the real PDF extraction,
chunking, verification logic, SQLite, and Chroma code paths.

```powershell
cd frontend
npm run build   # tsc type-check + vite production build
```

**Actual result: build succeeds, 0 type errors.** (No frontend unit tests were
added; the frontend was smoke-tested against the running backend via curl/manual
flows rather than an automated browser test, since no browser automation tool was
available in this environment — see "Known issues.")

## 12. Running the evaluation

```powershell
cd backend
.venv\Scripts\python scripts\run_eval.py
```

This seeds (or reuses) a "Demo Study Collection" containing three synthetic
sample PDFs, runs the 54-case labelled evaluation, saves a JSON report to
`data/eval_reports/`, and prints a summary. You can also trigger/view it from the
frontend's **Evaluation** tab, or via `POST /api/collections/{id}/evaluate` and
`GET /api/evaluations/{run_id}`.

### Actual measured results (54 cases, local `qwen2.5:7b` + `nomic-embed-text`, CPU)

Retrieval comparison (every mode gets at least one expected page into the top-8
here, because the sample collection is small — 18 chunks total — so Recall@k
saturates; MRR is the more informative number at this scale):

| Mode | Recall@k | MRR | p50 latency |
|---|---|---|---|
| Vector only | 1.00 | 0.939 | 3335ms |
| Keyword only (BM25) | 1.00 | 0.983 | 6ms |
| Hybrid (RRF) | 1.00 | 0.953 | 3344ms |
| Hybrid + rerank | 1.00 | **1.000** | 4053ms |

Generation pipeline (primary mode: hybrid):

- **Citation precision: 0.979** · **citation recall: 0.939**
- **Refusal accuracy on unanswerable cases: 1.00** (8/8 correctly refused)
- **False refusal rate on answerable cases: 0.087** (4/46 answerable cases were
  incorrectly refused)
- **Verification outcomes across all claims:** 46 supported, 0 weak, 3 not_found
- **Latency:** p50 14,967ms · p95 20,989ms (CPU-only 7B model; no GPU)
- **Mean retries per question:** 0.056

**What the 3 "not_found" claims actually were** (inspected by hand, not just
counted): this is the verification layer doing its job, not a bug.
- Two were the model paraphrasing a source sentence just enough to fail the
  verbatim-quote check — e.g. the source says *"Each process moves through
  states..."* and the model quoted *"A process moves through states..."*.
  Substantively correct, but not an exact quote, so layer 1 correctly refused
  to call it "supported."
- One (`db-2`, "What does Isolation mean for concurrent transactions?") cited
  the **wrong page**: the model attached a quote that's actually on page 1
  (ACID properties) to a chunk from page 5 (concurrency control) — a genuine
  citation-pointer error that exact-quote verification caught before it could
  reach the user as a false "page 5, supported" citation.
- All three led to a retry, and then a refusal rather than a wrong answer,
  which is the intended trade-off: these numbers show the system erring toward
  refusing over presenting an unverified citation as solid.
- One additional false refusal (`distract-6`, a segmentation-vs-network-segment
  distractor question) was the generating model itself deciding the passages
  were insufficient, not a verification failure — a real retrieval/generation
  miss on a deliberately tricky distractor question, included here rather than
  excluded.

These are the actual numbers from one real run (see `data/eval_reports/` for the
full report with all 54 per-case results); they are not hand-picked or
hardcoded, and a re-run will vary slightly since the local LLM calls are not
perfectly deterministic.

## 13. How citations and verification work

1. Generation: the model is given the question plus the retrieved passages
   (each tagged with `chunk_id`/document/page) and must respond with structured
   claims, each citing one `chunk_id` and a verbatim quote from it.
2. **Layer 1 (exact quote check, deterministic):** the quote is checked against
   the actual text of the cited chunk, after whitespace normalization only — no
   fuzzy matching, so fabricated text is never accepted as "found."
3. **Layer 2 (semantic support, LLM judge):** only runs if layer 1 passes. A
   separate model call judges whether the passage actually supports the claim
   (`supported` / `weak` / `not_found`). If the judge call fails or returns an
   invalid shape, the result fails safe to `not_found` — it never defaults to
   "supported."
4. If overall evidence support across claims is below a threshold, the system
   regenerates once with feedback, then refuses if still insufficient.

This proves the citation is *real* (the quote exists where claimed) and *checked*
for relevance — it does not prove the generating model's internal reasoning
actually depended on that text.

## 14. How retrieval metrics are calculated

- **Recall@k**: fraction of answerable evaluation cases where at least one
  expected (document, page) pair appears anywhere in the top-k retrieved chunks.
- **MRR**: mean of 1/rank of the first retrieved chunk that matches expected
  evidence, averaged over answerable cases (0 if none retrieved).
- **Citation precision/recall**: precision = correct cited (document, page)
  pairs ÷ all cited pairs; recall = correct cited pairs ÷ all expected pairs,
  both computed only over answerable cases.
- **Refusal accuracy**: fraction of unanswerable cases correctly refused.
  **False refusal rate**: fraction of answerable cases incorrectly refused.
- **Latency**: p50/p95/mean wall-clock time per case.

Full definitions are in `backend/app/evaluation/metrics.py`.

## 15. Known limitations

- The evaluation dataset uses synthetic, programmatically generated sample PDFs
  (one topic per page) rather than real messy course material, so it doesn't
  exercise multi-column layouts, footnotes, tables, or scanned pages. See
  `DECISIONS.md` for why.
- The LLM judge (layer 2 verification) is itself a 7B local model — it is not
  infallible, and its verdict is recorded with its method (`llm_judge` vs.
  `judge_unavailable`) precisely so this can be audited, not treated as ground
  truth.
- SQLite is single-writer; this prototype is single-user by design.
- No OCR; scanned/image-only PDFs are detected and reported, not processed.
- The reranker depends on `sentence-transformers`/`torch` (CPU-only here); if
  that dependency is missing or fails to load, `hybrid_rerank` mode falls back
  to the unranked hybrid order rather than erroring.
- Prompt injection from uploaded document content is not specially sandboxed
  beyond treating retrieved text as data in the prompt template (never as
  instructions the system prompt would obey); this residual risk is not
  eliminated, only reduced by the verification layer catching claims that don't
  actually trace back to real text.

## 16. Privacy and data-handling notes

- Everything runs locally: uploaded PDFs, the SQLite database, and the vector
  store all live under `data/` in the project directory and never leave the
  machine (no telemetry, no cloud calls — Ollama runs locally).
- Deleting a document removes its file, its SQL rows, and its vectors.
  Deleting a collection cascades the same way.
- No hosted LLM provider is enabled by default, so no document content is sent
  to a third party unless you explicitly configure and enable one yourself.

## 17. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/api/health` shows `ollama.available: false` | Ollama isn't running | `ollama serve`, or check it's installed |
| Upload fails with "Embedding generation failed" | embedding model not pulled | `ollama pull nomic-embed-text` |
| Every question is refused | model/chunking mismatch, or genuinely unanswerable | check the "Show retrieved passages" panel to see what was found |
| Frontend can't reach backend | backend not running, or CORS origin mismatch | confirm backend is on :8000 and `FRONTEND_ORIGIN` in `.env` matches the frontend's actual origin |
| Evaluation run stays "running" for a long time | expected — it runs real local LLM calls for 54 cases | check backend logs; a 7B CPU model takes seconds per call |

## 18. Demonstration workflow

1. Start the backend and frontend (section 10).
2. In the sidebar, create a collection (or run `scripts/seed_demo.py` first and
   refresh to see "Demo Study Collection" already populated).
3. Upload `data/sample_documents/operating_systems_notes.pdf` (or your own
   text-based PDF).
4. Switch to the **Ask** tab and ask: *"What are the four conditions required
   for a deadlock to occur?"* — expect a grounded answer citing page 4 with a
   **Supported** badge.
5. Ask something unrelated, e.g. *"What is the capital of Australia?"* — expect
   a refusal.
6. Click a citation chip to open the **source viewer** and see the exact page
   and quote.
7. Switch to the **Evaluation** tab and run the evaluation to see aggregate
   metrics across 54 labelled questions.

## 19. Future improvements

- Add a real hosted-provider adapter behind the existing `llm_client` seam, with
  cost tracking, once a specific provider/key is actually available to test.
- Add OCR for scanned PDFs.
- Add precise highlight-rectangle rendering using PyMuPDF's text-search-on-page
  API (`page.search_for`) to locate the quote's bounding box, with a tested
  fallback to the current "show excerpt" behavior.
- Replace the on-demand BM25 rebuild with an incrementally updated index if
  collections grow large.
- Add Alembic migrations if/when this moves off SQLite.
