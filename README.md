# AI-Powered Knowledge Quiz Builder

A web app that generates a 5-question multiple-choice quiz on any topic,
using an LLM grounded with real Wikipedia context, and scores the user's
answers with explanations.

## Architecture

```
Browser (HTML/JS)
      |
      v
FastAPI backend  ----->  Wikipedia API   (retrieval layer)
      |
      v
   Groq LLM       (generation layer, returns structured JSON)
      |
      v
In-memory quiz store + scoring logic
```

The system is split into four independent layers:

1. **Retrieval layer** (`retrieval.py`) — fetches a short factual summary of
   the topic from Wikipedia before generating questions.
2. **Validation layer** (`validation.py` + `retrieval.topic_has_any_match`) —
   a two-stage guardrail that rejects topics that look like gibberish
   (e.g. "sgndklsg", "qwerty") when Wikipedia also has no matching page,
   instead of letting the LLM hallucinate a fake quiz about a nonsense
   string. Stage 1 is a fast local letter-pattern heuristic (no network
   call); stage 2 confirms using Wikipedia's "opensearch" endpoint, which
   is a much stronger signal since a letter-pattern check alone can be
   fooled by short fake words that happen to contain vowels (e.g. "qwerty").
3. **Generation layer** (`generator.py`) — sends the topic (+ context, if
   available) to Groq's LLM API, forces strict JSON output, and validates
   the response shape.
4. **API / scoring layer** (`main.py`) — exposes two endpoints, keeps the
   correct answers server-side until submission, and computes the score.

Each layer can fail or be swapped independently. If Wikipedia retrieval
fails (network issue, topic not found), the system falls back to
LLM-only generation rather than crashing.

## Why these technical choices

- **Groq API**: fast inference, free tier, OpenAI-compatible request shape
  (easy to swap providers later with minimal code change).
- **Retrieval-augmented generation (RAG)**: grounding the LLM with a real
  Wikipedia summary before generation reduces hallucinated facts compared
  to asking the LLM to generate purely from memory.
- **Forced JSON output** (`response_format: json_object`): avoids fragile
  regex parsing of LLM responses and removes an entire class of bugs
  (markdown fences, conversational preamble in the response).
- **Server-side answer key**: correct answers and explanations are
  stripped from the API response until the quiz is submitted, so a user
  can't see answers via browser dev tools before answering.
- **In-memory quiz store (not a database)**: a deliberate scope decision
  for this MVP. The take-home is scoped to ~2 hours and focused on AI
  integration, not persistence infrastructure. In a production version,
  this would be replaced with Redis (with a TTL) or a Postgres table.
- **Vanilla JS frontend, no framework**: the brief explicitly deprioritizes
  UI polish. A framework would add build tooling overhead without adding
  value to what's being evaluated.

## Tradeoffs / what I'd do differently in production

- Add persistence for quiz history (explicitly listed as a bonus, skipped
  here in favor of retrieval + explanations, which add more evaluative
  value for the time available).
- Add caching for repeated topics to avoid redundant Wikipedia + LLM calls.
- Add retry logic with exponential backoff for the Groq API call.
- Move the in-memory store to Redis with expiry for multi-instance
  deployments (current version assumes a single backend instance).
- The gibberish-topic guardrail uses a fast local heuristic plus a
  Wikipedia "opensearch" check as the authoritative signal. It still isn't
  perfect for extremely short ambiguous strings, but it's meaningfully
  stronger than a letter-pattern heuristic alone, which could be fooled by
  short fake words containing real vowels (e.g. "qwerty").

## Running it locally

### 1. Backend setup
```bash
cd backend
pip install -r requirements.txt
export GROQ_API_KEY=your_key_here       # get a free key at console.groq.com
uvicorn main:app --reload --port 8000
```

### 2. Open the app
Visit `http://localhost:8000` in your browser. The FastAPI backend serves
the frontend directly, so no separate frontend server is needed.

### 3. Usage
1. Enter a topic (e.g. "Photosynthesis")
2. Click "Generate Quiz" — wait a few seconds for the LLM call
3. Answer all 5 questions
4. Click "Submit Answers" to see your score, correct answers, and
   explanations for each question

## Tech stack

| Layer       | Technology              |
|-------------|--------------------------|
| Backend     | FastAPI (Python)         |
| LLM         | Groq (`llama-3.1-8b-instant`) |
| Retrieval   | Wikipedia REST API       |
| Frontend    | Vanilla HTML/CSS/JS      |


## Output Screenshots

### Home Page
![Home Page](quiz-builder/OUTPUT%20SS/OUTPUT0.png)

### Quiz Generated
![Quiz Generated](quiz-builder/OUTPUT%20SS/OUTPUT1.png)

### Answer Submission
![Answer Submission](quiz-builder/OUTPUT%20SS/OUTPUT2.png)

### Score & Explanation
![Score](quiz-builder/OUTPUT%20SS/OUTPUT3.png)
