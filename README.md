# StudyIA Copilot

StudyIA Copilot is a fullstack AI application for asking grounded questions over PDF documents. The project combines PDF ingestion, retrieval, reranking, conversational context, and source highlighting in a modern chat workspace.

Live application:
[https://study-ia-copilot.vercel.app/](https://study-ia-copilot.vercel.app/)

> Important
>
> The public demo backend is hosted on Render free tier. Cold starts can take around 30 to 50 seconds after inactivity.
>
> The repository keeps a stronger local `full` mode for technical evaluation, while the deployed version uses a lighter mode focused on zero-cost availability.

## What This Project Demonstrates

This repository is meant to showcase more than a prompt wrapper:
- PDF upload and text extraction
- chunking with positional metadata
- semantic retrieval with FAISS
- reranking before answer generation
- conversational follow-up support with short-term chat history
- grounded answers with clickable sources
- PDF highlights in the original document viewer
- frontend session persistence for chats and selected documents
- backend-powered document catalog sync on frontend load
- system readiness signals for LLM, embeddings, reranker, and retrieval mode
- automated backend API contract tests for upload, ask, catalog, and PDF serving
- observability logs for retrieval and generation timings

## Stack

### Frontend
- React
- TypeScript
- Vite
- Tailwind-style design tokens
- `react-pdf` for document rendering

### Backend
- FastAPI
- PyMuPDF for PDF parsing
- sentence-transformers for embeddings
- FAISS for similarity search
- reranking for final context selection
- Google AI Studio for answer generation

## Architecture Overview

```text
PDF upload
  -> text extraction + positional metadata
  -> chunk persistence
  -> embedding generation
  -> FAISS index
  -> retrieval + lexical fallback
  -> reranking
  -> grounded prompt assembly
  -> LLM answer
  -> source chips + PDF highlight in UI
```

## Runtime Modes

The project supports two different execution strategies:

- `full`: local technical demo mode with the complete retrieval stack
- `lite`: deployment-oriented mode with lighter behavior for free hosting

This split is intentional. It keeps the strongest AI engineering story in the repository without making the public demo too fragile for free infrastructure.

## Repository Structure

```text
.
|-- backend
|   |-- app
|   |   |-- db
|   |   |-- models
|   |   |-- routes
|   |   `-- services
|   |-- requirements-deploy.txt
|   |-- requirements-full.txt
|   `-- render.yaml
`-- frontend
    |-- src
    `-- package.json
```

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/Charleradiniz/StudyIA_Copilot.git
cd StudyIA_Copilot
```

### 2. Backend setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements-full.txt
```

Create `backend/.env`:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash-lite
RAG_MODE=full
LOG_LEVEL=INFO
```

Optional:

```env
DATABASE_URL=sqlite:///./studycopilot.db
CORS_ORIGINS=http://localhost:5173
```

Start the backend:

```bash
uvicorn app.main:app --reload
```

### 3. Frontend setup

In a separate terminal:

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```env
VITE_API_URL=http://127.0.0.1:8000
```

Start the frontend:

```bash
npm run dev
```

## Validation

Backend API contract tests:

```bash
cd backend
venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v
```

Frontend quality checks:

```bash
cd frontend
npm run lint
npm run build
```

## Observability

The backend now logs the most useful steps of the RAG pipeline:
- retrieval time
- rerank time
- LLM generation time
- total request time
- number of retrieved chunks
- number of selected chunks
- document id and effective query

These logs make the project easier to debug and easier to discuss in interviews, because you can explain not only what the system does, but how you inspect retrieval quality and latency.

## Frontend Product Improvements

The current UI includes:
- persistent sidebar for documents, navigation, and chat history
- split workspace with chat on the left and PDF viewer on the right
- runtime status card showing whether vector retrieval and reranking are available
- document cards with chunk count, page count, preview, and retrieval readiness
- loading skeletons and streaming responses
- mobile-friendly upload flow
- local persistence of sessions with `localStorage` plus backend document catalog hydration

This makes the app feel closer to a production SaaS experience rather than a single-screen prototype.

## Suggested Demo Flow

If you are presenting this project in an interview:

1. Upload a PDF with real text.
2. Ask for a summary.
3. Ask a follow-up question like `E o que mais?`.
4. Open a returned source chip.
5. Show the highlighted evidence inside the PDF viewer.
6. Explain the retrieval logs in the backend terminal.

That flow demonstrates:
- ingestion
- retrieval
- grounded generation
- conversational memory
- explainability
- fullstack UX integration
- operational visibility

## Engineering Decisions Worth Mentioning In Interviews

- The app separates a stronger local `full` mode from a cheaper public `lite` mode instead of deleting the advanced pipeline for deployment convenience.
- PDF chunks keep positional metadata, which enables evidence highlighting instead of only plain-text citations.
- Follow-up questions are contextualized with recent chat history so short prompts can still retrieve the right chunks.
- The frontend persists sessions locally, which makes the product feel continuous across refreshes.
- Logs capture retrieval and generation timing, which is useful for latency analysis and debugging retrieval quality.
- The backend exposes document catalog and runtime readiness endpoints so the UI can surface operational state instead of hiding infrastructure assumptions.
- The repository includes API contract tests for the core user flow, which makes the project stronger in technical interviews and safer to evolve.

## Portfolio Signals

What makes this repository stronger than a typical AI demo:
- the product explains where answers came from instead of only generating text
- the backend has explicit runtime modes and communicates trade-offs between local depth and free-tier deployment
- the frontend exposes technical system state in a user-friendly way, which helps both debugging and demo storytelling
- the PDF viewer is integrated into the retrieval flow with direct evidence jumps and highlights
- the core backend flow is covered by automated tests, not only manual demo steps

## Current Gaps

The project is already strong for a portfolio, but the next steps that would raise employability even more are:
- frontend component or e2e tests
- structured evaluation for retrieval quality
- session persistence in a real database
- provider abstraction for Gemini and Ollama
- richer analytics and monitoring dashboards

## Deployment Notes

### Render backend

Use the lighter deployment requirements:

```bash
pip install -r requirements-deploy.txt
```

Expected environment variables:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash-lite
RAG_MODE=lite
CORS_ORIGINS=https://your-frontend.vercel.app
DATABASE_URL=your_database_url
```

### Vercel frontend

```env
VITE_API_URL=https://your-render-service.onrender.com
```

## Why This Project Is Good For A Fullstack AI Portfolio

This project shows a combination that recruiters and interviewers often look for:
- product thinking
- applied AI engineering
- retrieval grounding
- UX attention around evidence and explainability
- deployment trade-off awareness
- fullstack ownership from interface to inference
