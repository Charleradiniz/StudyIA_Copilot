# StudyIA Copilot

StudyIA Copilot is a document intelligence assistant built to answer questions over PDF files using a Retrieval-Augmented Generation pipeline.

Live application:
[https://study-ia-copilot.vercel.app/](https://study-ia-copilot.vercel.app/)

> Important
>
> The public demo backend is hosted on Render free tier. Because of free-tier cold starts, the server can take around 30 to 50 seconds to wake up after inactivity.
>
> This is an intentional trade-off to keep the project publicly accessible at no cost. The repository preserves a stronger local `full` mode for technical evaluation, while the deployed version uses a lighter configuration focused on availability and zero-cost hosting.

The project was designed to work well as both:
- a technical reference for a real-world RAG application
- a deployable product with a lightweight public demo mode

## What This Project Shows

This is not just a chat UI connected to an LLM. The project includes:
- PDF ingestion and text extraction
- document chunking with positional metadata
- semantic retrieval
- reranking
- source-grounded answers
- PDF source highlighting in the frontend
- two execution modes: `full` and `lite`

That split is intentional.

The `full` mode preserves the more technically impressive architecture for local demonstration and technical discussion:
- embeddings
- vector search
- reranking
- richer retrieval pipeline

The `lite` mode exists to make the public deployment viable on free infrastructure:
- lighter dependencies
- lower memory footprint
- simpler retrieval fallback for short documents
- easier deployment on Render free tier

## Why The Project Uses Two Modes

Free deployment platforms are great for demos, but they are not ideal for heavyweight NLP stacks that depend on packages such as `torch`, `transformers`, and `sentence-transformers`.

To avoid removing the strongest technical part of the project, the application supports two different runtime strategies:

- `full`: intended for local execution and technical evaluation
- `lite`: intended for public deployment on Render free tier

This allows the repository to keep the more complete RAG architecture while still offering a live version that is easy to test.

## Architecture

### Frontend
- React
- TypeScript
- Vite
- `react-pdf` for document rendering
- source-aware chat interface
- click-to-open source snippets inside the original PDF

### Backend
- FastAPI
- PDF parsing with `PyMuPDF`
- local document persistence
- retrieval service
- answer generation through Google AI Studio in the deployed version

### Retrieval Design

In `full` mode, the project is structured around:
- semantic embeddings
- FAISS-based similarity search
- reranking
- context assembly for grounded answers

In `lite` mode, the system falls back to a lighter retrieval strategy that is more deployment-friendly while preserving the same product experience.

## Live Demo Strategy

The deployed version is intentionally not identical to the heaviest local version.

### Public Deployment
- Frontend: Vercel
- Backend: Render
- LLM provider: Google AI Studio
- Runtime mode: `RAG_MODE=lite`

### Why

The original local stack is heavier and better for technical inspection, but free-tier deployment can time out or fail when building large ML dependencies. Instead of removing those features from the codebase, the project keeps them available for local execution and deeper evaluation.

This is a trade-off in favor of:
- keeping the demo online
- preserving the stronger engineering story in the repository
- making the architecture discussion more realistic

## Repository Structure

```text
.
├── backend
│   ├── app
│   │   ├── routes
│   │   ├── services
│   │   ├── db
│   │   └── models
│   ├── requirements-deploy.txt
│   ├── requirements-full.txt
│   └── render.yaml
└── frontend
    ├── src
    └── package.json
```

## Local Setup

### 1. Clone and install

```bash
git clone https://github.com/Charleradiniz/StudyIA_Copilot.git
cd StudyIA_Copilot
```

### 2. Frontend

```bash
cd frontend
npm install
```

Create a `.env` file in `frontend/`:

```bash
VITE_API_URL=http://127.0.0.1:8000
```

Start the frontend:

```bash
npm run dev
```

### 3. Backend

In a separate terminal:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-full.txt
```

Start the API:

```bash
uvicorn app.main:app --reload
```

## Local Full Mode With Google AI Studio

The current repository uses Google AI Studio in the active LLM service file.

Set these environment variables before starting the backend:

```bash
set GEMINI_API_KEY=your_key_here
set GEMINI_MODEL=gemini-2.5-flash-lite
set RAG_MODE=full
```

Optional:

```bash
set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/studycopilot
```

If no database is available, the app can still start for demo purposes.

## Local Ollama Version

The original local prototype used Ollama for answer generation. That path is still relevant as a local-only demo strategy, especially if you want to showcase a fully local workflow.

### When to use it
- you want a local LLM instead of a hosted API
- you want to demonstrate an offline-style development setup
- you want to discuss portability between hosted and local inference

### Recommended local stack
- `RAG_MODE=full`
- `requirements-full.txt`
- Ollama running locally

### Ollama steps

1. Install Ollama
2. Pull a model such as:

```bash
ollama pull llama3.1
```

3. Start Ollama locally

```bash
ollama serve
```

4. Replace the backend LLM provider implementation in `backend/app/services/llm.py` with an Ollama-based version like the original prototype:

```python
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1"
```

5. Run the backend with:

```bash
set RAG_MODE=full
uvicorn app.main:app --reload
```

### Important note

The deployed repository is configured around Google AI Studio because that was the most practical option for a public free-tier demo. Ollama is best treated here as a local development and presentation path, not the public deployment path.

## Deployment Configuration

### Render Backend

The backend uses the lightweight deployment requirements:

```bash
pip install -r requirements-deploy.txt
```

Environment variables expected in Render:

```bash
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash-lite
RAG_MODE=lite
CORS_ORIGINS=https://your-frontend.vercel.app
DATABASE_URL=your_database_url
```

### Vercel Frontend

Environment variable:

```bash
VITE_API_URL=https://your-render-service.onrender.com
```

## Engineering Notes

The strongest technical value of this project is not only the live demo, but the engineering decisions behind it:
- preserving a heavier RAG stack for local execution
- adapting the product for free-tier deployment instead of deleting complexity
- grounding answers in retrievable document sources
- surfacing those sources visually in the original PDF
- treating deployment constraints as part of the architecture, not as an afterthought

This project intentionally highlights:
- product thinking
- infrastructure trade-off awareness
- applied AI engineering beyond prompt wrappers

## Suggested Demo Flow

If you are reviewing this project locally:

1. Upload a PDF
2. Ask for a summary
3. Ask a specific question
4. Open the returned source snippets
5. Verify the highlighted evidence inside the PDF viewer

That flow demonstrates:
- ingestion
- retrieval
- grounded generation
- explainability
- UX integration between search and source verification

## Current Status

- Public demo mode is optimized for free-tier deployment
- Local mode remains the best way to inspect the full technical architecture
- The repository intentionally documents the difference between those two realities

## Future Improvements

- provider abstraction for Gemini and Ollama in the same code path
- richer multi-document retrieval in lite mode
- stronger observability around retrieval quality
- automated evaluation for answer grounding
- more explicit benchmark comparison between `full` and `lite`
