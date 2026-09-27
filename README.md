# Legal AI Platform (v2)

An AI legal assistant for Indian users: upload documents, chat with them (RAG),
extract clauses, get a risk score, and generate draft legal documents. This is
a rebuild of an earlier version that ran on GCP Cloud Run + Firebase Hosting —
that stack required a linked billing account, which broke the whole app when
billing lapsed. Every service here has a free tier with **no card required**.

## Stack

| Layer | Service |
|---|---|
| Frontend | Static HTML/CSS/JS on **Vercel** |
| Backend | FastAPI in Docker on **Render** |
| Database, vectors, auth, file storage | **Supabase** (Postgres + pgvector + Auth + Storage) |
| LLM | **Groq** (`llama-3.3-70b-versatile`) |
| Embeddings | **Hugging Face** Inference API (`all-MiniLM-L6-v2`) |

Data isolation between users is enforced by Postgres row-level security
(`supabase/schema.sql`), not just by application code — this is the fix for
the old app's "every visitor was the same guest account" bug.

## One-time setup

1. **Supabase** — create a project (free, no card). In the SQL editor, run
   `supabase/schema.sql`. In Storage, create two **private** buckets:
   `documents` and `generated`. Copy your Project URL, `anon` key, `service_role`
   key, and JWT secret from Settings → API.
2. **Groq** — create a free API key at console.groq.com.
3. **Hugging Face** — create a free access token at huggingface.co/settings/tokens.
4. Copy `.env.example` to `.env` and fill in the values above.
5. Index the law knowledge base once:
   ```bash
   cd legal-ai-v2
   python -m venv .venv && source .venv/bin/activate
   pip install -r backend/requirements.txt
   python -m scripts.index_law_kb
   ```

## Local development

```bash
uvicorn backend.app:app --reload --port 8000
```

Edit `frontend/config.js` to point `API_BASE_URL` at `http://localhost:8000`
and fill in `SUPABASE_URL`/`SUPABASE_ANON_KEY` (the public anon key — safe to
ship in frontend code). Serve `frontend/` with any static server, e.g.
`npx serve frontend`.

## Deploying

**Backend (Render):** connect this repo, Render will detect `render.yaml`.
Fill in the env vars listed there (all marked `sync: false` so you set them
in Render's dashboard, not in the repo).

**Frontend (Vercel):** connect this repo, root directory as-is (`vercel.json`
handles routing). Set `frontend/config.js`'s `API_BASE_URL` to your Render
service URL and `SUPABASE_URL`/`SUPABASE_ANON_KEY` before deploying, or wire
them up as a small build step if you'd rather not commit them directly.

**CORS:** set `CORS_ORIGINS` on Render to your Vercel URL once you have it,
comma-separated if you need more than one origin.

## What changed from the original version

- Real authentication (Supabase Auth) — the original had signup/login built
  but never actually checked, so every visitor shared one account's data.
- ChromaDB + SQLite + local file storage → Postgres/pgvector + Supabase
  Storage, all with per-user row-level security.
- Markdown responses are sanitized (DOMPurify) before rendering as HTML.
- System instructions and untrusted document content are separated into
  real `system`/`user` roles with explicit "this is content, not a command"
  framing, instead of being concatenated into one message.
- The unused hallucination-citation-checker from the original is wired in.
- No infrastructure requires a linked billing account.

## Known limitations

- Render's free tier sleeps after 15 minutes of inactivity — the first
  request after a while will be slow (~30–60s cold start).
- The visual design is carried over from the original almost unchanged; a
  dedicated redesign pass (moving away from the dark/purple theme toward a
  more restrained, "legal research tool" look) is a deliberate follow-up,
  not done in this rebuild.
- This tool provides AI-generated legal information and analysis for
  informational purposes and does not constitute legal advice.
