# 🎓 AI Exam Prep Agent

Turn a YouTube lecture into **smart notes**, **exam questions**, a **RAG tutor**,
and a **progress tracker** — all from one URL.

Built with **Python + FastAPI**, **Groq** (LLM + Whisper transcription),
**MongoDB Atlas** (data + vector search), and **Jina** (embeddings).
Deploys to **Vercel**.

## What it does (the 5 steps)

1. **Extract** the lecture transcript from a YouTube URL (captions; Whisper fallback).
2. **Smart notes** — summary, concise notes, definitions, formulas, examples, "memorize".
3. **Exam questions** — short, long, MCQ, true/false, scenario — each tagged by topic.
4. **RAG tutor** — answers questions using *only* this lecture's content.
5. **Progress** — quizzes, scores, per-topic mastery, revision recommendations.

## Architecture

```
public/            static frontend (HTML/CSS/JS)  -> Vercel CDN
api/index.py       Vercel Python serverless entry (exposes FastAPI `app`)
app/
  config.py        env config
  db.py            MongoDB collections: lectures, chunks, attempts
  llm.py           Groq chat + JSON mode
  embeddings.py    Jina embeddings (Groq has no embeddings endpoint)
  transcript.py    Step 1
  notes.py         Step 2
  questions.py     Step 3
  rag.py           Step 4 (Atlas Vector Search)
  progress.py      Step 5
  routes.py        FastAPI routes (/api/*)
```

## Free accounts you need

| Service | Key env var | Where |
|---|---|---|
| Groq (LLM + Whisper) | `GROQ_API_KEY` | https://console.groq.com/keys |
| MongoDB Atlas | `MONGODB_URI` | https://www.mongodb.com/atlas |
| Jina (embeddings) | `JINA_API_KEY` | https://jina.ai/embeddings |

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # then fill in the keys
uvicorn api.index:app --reload
```

Open http://127.0.0.1:8000

> The Whisper audio fallback also needs `yt-dlp` + `ffmpeg` installed. It is
> optional — captions are the primary path. `pip install yt-dlp` if you want it.

## MongoDB Atlas Vector Search index (required for the tutor)

The RAG tutor needs a vector index on the `chunks` collection. In the Atlas UI:
**Atlas Search → Create Search Index → JSON Editor**, target
`examprep.chunks`, name it `vector_index`, and paste:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1024,
      "similarity": "cosine"
    },
    { "type": "filter", "path": "lecture_id" }
  ]
}
```

`numDimensions` must match `EMBEDDING_DIM` (default 1024 for jina-embeddings-v3).

## Deploy to Vercel

1. Push this folder to a Git repo and import it in Vercel (or run `vercel`).
2. In **Project → Settings → Environment Variables**, add every var from
   `.env.example` (`GROQ_API_KEY`, `MONGODB_URI`, `MONGODB_DB`, `JINA_API_KEY`,
   `EMBEDDING_DIM`, `EMBEDDINGS_PROVIDER`, `VECTOR_INDEX_NAME`).
3. Deploy. `vercel.json` routes `/api/*` to the Python function and serves
   `public/` statically.

### Vercel serverless caveats
- **No local Whisper / heavy models** — transcription uses Groq's API; embeddings
  use Jina's API. Don't add `torch`/`sentence-transformers` (250 MB limit).
- **Read-only filesystem** — the `yt-dlp` audio fallback won't work reliably on
  Vercel. Lectures need captions in production.
- **Function duration** — long lectures may approach the timeout; the captions +
  Groq path is fast enough for typical lectures.

## API reference

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/process` | Steps 1-4: transcript → notes → questions → index |
| GET | `/api/lecture/{id}` | Fetch a stored lecture |
| POST | `/api/tutor` | RAG tutor answer |
| POST | `/api/quiz` | Build an MCQ quiz |
| POST | `/api/quiz/submit` | Grade + record an attempt |
| GET | `/api/progress/{student_id}` | Mastery + recommendations |

## Roadmap
- Real auth / multiple students (replace the `default` student id).
- Grade short/long answers with the LLM (not just MCQs).
- Spaced-repetition scheduling from weak topics.
