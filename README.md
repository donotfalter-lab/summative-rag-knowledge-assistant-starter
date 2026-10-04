# Local RAG-Powered Knowledge Assistant

A local full-stack AI app that answers employee questions using a small, approved knowledge base. A React (Vite) frontend sends questions to a Flask backend. The backend finds the most relevant document chunks in a Chroma vector database, asks a local Ollama model to answer using only those chunks, and returns the answer together with the sources it used.

Everything runs on your machine. No cloud services and no deployment are involved.

---

## Problem Definition

New and current employees lose time looking through onboarding notes, support guides, security rules, and FAQs to find out how to handle everyday situations. Examples: what to do when they can't log in, how to report a suspicious email, or what to finish in their first week. This assistant lets them ask those questions in plain language and get a short, practical answer drawn only from the four approved documents in `server/knowledge_base/`. A useful answer gives the specific steps for the situation and shows which document (and which part of it) the steps came from. Sources matter here because the answers cover security and customer-support processes. A fluent but invented answer could lead someone to break a policy, so employees need to be able to check the original text before acting.

---

## Design Notes

```text
User browser
→ React frontend (client/src/App.jsx)
    POST /api/ask  { "question": "..." }   (Vite proxies /api → http://localhost:5555)
→ Flask /api/ask route (server/app.py)
    validates the question, handles errors
→ RAG workflow (server/rag_service.py: answer_question)
    → Vector database retrieval (server/vector_store.py: retrieve_relevant_chunks)
        embed question with Ollama nomic-embed-text  → POST /api/embed
        query Chroma collection for TOP_K nearest chunks
        drop chunks farther than MAX_DISTANCE
    → Prompt construction (build_prompt): instructions + numbered context blocks + question
    → Model service (call_generation_model): Ollama llama3.2 → POST /api/generate
→ JSON { answer, sources[] } returned to the frontend
→ Frontend renders the answer and one card per source (title, file, chunk, excerpt)
```

Offline seeding step (run once, and again whenever the documents change):

```text
server/knowledge_base/*.txt
→ documents.py: load_text_documents + build_chunks (120-word chunks, 25-word overlap)
→ vector_store.py: seed_vector_store → embed each chunk → Chroma upsert
   (id = "<file>::chunk-<n>", metadata = source, title, chunk_index)
→ server/chroma_db/ (persistent, git-ignored)
```

---

## Installation

**Requirements:** Python 3.10+, Node.js 18+ and npm, and [Ollama](https://ollama.com/download).

### 1. Install Ollama and pull the models

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
ollama run llama3.2 "Reply with one short sentence."   # sanity check
```

If Ollama is not already running as a service, start it with `ollama serve` in its own terminal.

### 2. Set up the Flask backend

```bash
cd server
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt    # or: pipenv install
cp .env.example .env
```

### 3. Seed the vector database

```bash
python seed_knowledge_base.py
```

Expected output:

```text
Loaded 4 documents.
Prepared 9 chunks.
Stored 9 chunks in collection 'knowledge_assistant'.
```

The script uses `upsert`, so it is safe to run again; it updates chunks rather than duplicating them.

### 4. Install the frontend

```bash
cd ../client
npm install
```

---

## Running the App

Use two terminals (plus Ollama running in the background).

**Terminal 1: backend**

```bash
cd server
source .venv/bin/activate
flask --app app run --debug --port 5555
```

Check it at <http://localhost:5555/api/health>.

**Terminal 2: frontend**

```bash
cd client
npm run dev
```

Open <http://localhost:5173>. The status badge should read "Backend is running." Type a question or click a sample question, then press **Ask Assistant**.

---

## Environment Variables

Copy `server/.env.example` to `server/.env`. Never commit the real `.env` file; it is git-ignored.

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL for the local model service |
| `GENERATION_MODEL` | `llama3.2` | Model used to generate answers |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Model used to create embeddings |
| `CHROMA_PATH` | `./chroma_db` | Local folder where Chroma stores vector data |
| `COLLECTION_NAME` | `knowledge_assistant` | Name of the vector collection |
| `KNOWLEDGE_BASE_PATH` | `./knowledge_base` | Folder containing source documents |
| `TOP_K` | `3` | Number of chunks to retrieve |
| `MAX_DISTANCE` | `0.5` | Maximum cosine distance for a chunk to count as relevant (0 = identical). If no chunk passes, the app says it lacks information and skips the model call. |
| `TEMPERATURE` | `0.2` | Controls response variation |
| `CLIENT_ORIGIN` | `http://localhost:5173` | Local frontend origin allowed by CORS |

If you change `EMBEDDING_MODEL`, delete `server/chroma_db/` and re-run the seed script, because embeddings from different models can't be compared.

---

## API Routes

### GET `/api/health`

Confirms that the backend is running.

```json
{ "status": "ok", "message": "Backend is running." }
```

### POST `/api/ask`

Receives a question and returns an answer with sources.

Request:

```json
{ "question": "What should I do if I cannot log into the product dashboard?" }
```

Success response (`200`):

```json
{
  "answer": "A helpful answer grounded in the knowledge base.",
  "sources": [
    {
      "title": "Product Support Guide",
      "source": "product_support.txt",
      "chunk_index": 0,
      "distance": 0.233,
      "excerpt": "Relevant source excerpt..."
    }
  ]
}
```

`distance` is the cosine distance between the question and the chunk (lower = more relevant).

If nothing in the knowledge base is close enough to the question, the route returns `200` with a "could not find enough relevant information" answer and an empty `sources` list.

Error responses:

| Status | When | Body |
|---|---|---|
| `400` | `question` missing, blank, not a string, or body not JSON | `{ "error": "Question is required." }` |
| `503` | Ollama unreachable or model not pulled | `{ "error": "Could not reach the model service...", "sources": [] }` |
| `500` | Any other failure in the RAG workflow (details are logged in the Flask terminal) | `{ "error": "Something went wrong while generating an answer.", "sources": [] }` |

---

## RAG Workflow

1. **Receive the question.** The frontend sends the user's question to the Flask `/api/ask` route. The route checks that it is a non-empty string and passes it to `answer_question()` in `rag_service.py`.
2. **Retrieve relevant chunks.** `retrieve_relevant_chunks()` embeds the question with `nomic-embed-text` through Ollama's `/api/embed` endpoint. It then queries the Chroma collection (cosine distance) for the `TOP_K` closest chunks and drops any farther than `MAX_DISTANCE`. Each chunk keeps its `source`, `title`, and `chunk_index` metadata from seeding.
3. **Short-circuit when nothing is relevant.** If no chunk passes the threshold, the service immediately returns an "I could not find enough relevant information" answer with no sources. The model is never called, so it can't make something up.
4. **Build the prompt.** `build_prompt()` lists each chunk as `[Source N: Title | file]` followed by its text, then adds the user's question. The instructions tell the model to use only that context, to say so when the context is insufficient, not to merge steps meant for a different situation, not to invent policies, and to name the source title it used.
5. **Call the model.** `call_generation_model()` sends a non-streaming request to Ollama's `/api/generate` with `llama3.2` and `TEMPERATURE` (0.2 keeps answers consistent).
6. **Return answer and sources.** The route returns `{ answer, sources }`. Each source includes the title, file name, chunk index, distance, and a 280-character excerpt. The frontend shows the answer with line breaks preserved, plus one card per source.

---

## Sample Questions and Observations

Tested locally through the Vite dev server proxy (frontend → Flask → Chroma → Ollama) using `llama3.2` (3B) and `nomic-embed-text`, with `TOP_K=3`. Responses took about 8–23 seconds each on CPU; the first request is slowest because the model has to load.

| Sample Question | Was the Answer Relevant? | Were Useful Sources Returned? | Notes |
|---|---|---|---|
| What should I do if I cannot log into the product dashboard? | Mostly | Yes: Product Support Guide chunks 0 and 1 (distance 0.23, 0.35) and Employee Onboarding Guide chunk 1 (0.36), which covers employee access problems | The correct login steps (confirm email, check for a recent password reset, send a reset link) came first. But the model also added the "dashboard loads slowly / check status page" steps, which belong to a different situation. This persisted even after the prompt was tightened, so it looks like a limit of the small 3B model. The answer is also written from the support agent's point of view, while an employee asking "I" would need the onboarding steps (company email, accepted invitation, contact operations). |
| Why are source-backed answers important? | Yes | Yes: the top source was the exact Workplace FAQ section (distance 0.26) | The answer closely paraphrased the FAQ: fluent answers can still be incomplete, outdated, or unsupported, and sources let users decide whether to trust them. |
| What should employees do if they receive a suspicious email? | Yes | Yes: Security Guidelines chunks 0 and 1 (0.25, 0.26) | Before the prompt was refined, the answer included a stray phrase ("…for an approved work task") taken from a nearby sentence; after refinement it was clean. It listed "don't click links or open attachments" and "report it", but left out the follow-up step for someone who has already clicked a link. |
| What should a support agent do if the knowledge base does not answer a customer question? | Yes | Yes: Workplace FAQ (0.22) and Product Support Guide (0.27, 0.31) | Correct steps: don't invent an answer, explain the issue needs review, escalate. The answer pointed out that both documents agree. |
| What should a new employee complete during the first week? | Yes | Yes: Employee Onboarding Guide chunk 0 (0.20) | All seven first-week steps listed accurately and in order. |
| What is the company vacation policy? *(out of scope)* | Yes: correctly refused | Not ideal: three weakly related chunks (0.42–0.47) were still shown | The model said it didn't have enough information. The sources were displayed even though they weren't used, because their distances fall in the same range as some useful chunks. |
| How do I bake sourdough bread? *(off-topic)* | Yes: correctly refused | Correctly none | All chunks were above `MAX_DISTANCE` (≥ 0.57), so the app returned the "not enough information" answer without calling the model. |

**Refinements made based on these tests:**

- Added the `MAX_DISTANCE` threshold (chosen from the distances observed above) so clearly off-topic questions return no sources and skip the model call.
- Added prompt rules against combining steps from different situations and asking the model to name its source. This removed the stray phrase in the suspicious-email answer.
- Returned `distance` in each source and showed the chunk number on source cards, so reviewers can see how strong each match was.
- Preserved line breaks in the answer display, because the model often answers with numbered lists that were collapsing into one paragraph.
- Pinned `posthog==5.4.0`. chromadb 0.5.5 printed "Failed to send telemetry event" errors with newer posthog releases.
- Returned clear JSON errors (`400`/`503`/`500`) so the frontend shows a helpful message instead of breaking.

---

## Project Structure

```text
summative-rag-knowledge-assistant-starter/
├── client/                    React + Vite frontend
│   ├── vite.config.js         proxies /api to Flask on port 5555
│   └── src/App.jsx            question form, answer and source display
├── server/
│   ├── app.py                 Flask routes (/api/health, /api/ask)
│   ├── config.py              environment variable configuration
│   ├── documents.py           load .txt files and split into overlapping chunks
│   ├── vector_store.py        Chroma client, Ollama embeddings, seeding, retrieval
│   ├── rag_service.py         prompt building, generation call, source formatting
│   ├── seed_knowledge_base.py one-time script to populate Chroma
│   ├── requirements.txt / Pipfile
│   ├── .env.example
│   └── knowledge_base/        the four approved source documents
└── README.md
```

---

## Known Limitations and Future Improvements

- **Small-model accuracy.** `llama3.2` (3B) sometimes merges steps from neighbouring sections (see the dashboard login question) or leaves out a step. A larger model, or putting each FAQ question/answer in its own chunk, would help.
- **Perspective mix-ups.** The knowledge base has both employee-facing and support-agent-facing guidance on similar topics, so first-person questions can get agent-oriented answers. Tagging chunks by audience, or letting the user choose a role, would improve this.
- **Chunking ignores structure.** Chunks are fixed 120-word windows, so a chunk can start or end mid-sentence. Splitting by paragraph or FAQ question would give cleaner context and excerpts.
- **Fixed relevance threshold.** `MAX_DISTANCE=0.5` was tuned on this small corpus. Some unrelated chunks still pass for borderline questions (the vacation example), and the value would need re-tuning for a different embedding model or a larger knowledge base. Re-ranking, or hiding sources when the model says it lacks information, would make the source list more trustworthy.
- **Sources aren't tied to sentences.** All retrieved chunks are listed, not just the ones the answer actually used. Inline citations (e.g. `[1]`) linked to source cards would be clearer.
- **Latency.** Answers take roughly 8–23 seconds on CPU. Streaming the response to the frontend would make the wait feel shorter.
- **No chat history or feedback.** Each question is independent. Future versions could save history in a local database and add helpful/unhelpful feedback buttons.
- **Manual re-seeding.** After editing the knowledge base files, you have to re-run `seed_knowledge_base.py`. Chunks from deleted files or shortened documents are not removed automatically. To fully reset, delete `server/chroma_db/` and seed again.

---

## Submission Checklist

- [x] Backend starts successfully (`/api/health` returns `ok`)
- [x] Frontend loads and shows the backend status
- [x] Frontend submits questions to `/api/ask` through the Vite proxy
- [x] Backend retrieves relevant context from Chroma
- [x] Ollama returns an answer
- [x] Answer and supporting sources are displayed in the frontend
- [x] `.env.example` included; real `.env` is git-ignored
- [x] README updated with all required sections
- [x] Meaningful Git commits
- [ ] Final work pushed to GitHub and repository link submitted in Canvas
