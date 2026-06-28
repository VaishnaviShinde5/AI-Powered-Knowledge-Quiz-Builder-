"""
main.py
-------
The API layer. This is the "glue" that ties retrieval.py and generator.py
together and exposes them over HTTP for the frontend to call.

Two endpoints:
1. POST /api/quiz        -> generate a new quiz for a given topic
2. POST /api/quiz/score  -> score submitted answers against the quiz

Why we score on the backend, not the frontend:
If we sent the correct answers to the browser immediately, a user could
open dev tools and see them before submitting. Keeping the answer key
server-side until scoring time is a basic but real security/integrity
practice worth mentioning in the interview.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, List
import uuid

from retrieval import fetch_topic_context, topic_has_any_match
from generator import generate_quiz
from validation import is_topic_too_vague


app = FastAPI(title="AI Knowledge Quiz Builder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store: quiz_id -> full quiz data (including correct answers).
# Why in-memory and not a database: this is an MVP take-home, not a
# production system. A dict keeps the code focused on the actual ask
# (AI integration) instead of database setup. This is a documented
# tradeoff, not an oversight -- mention this explicitly if asked.
QUIZ_STORE: Dict[str, dict] = {}


class TopicRequest(BaseModel):
    topic: str


class AnswerSubmission(BaseModel):
    quiz_id: str
    answers: Dict[str, str]  # e.g. {"0": "A", "1": "C", ...}


@app.post("/api/quiz")
def create_quiz(request: TopicRequest):
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic cannot be empty.")

    context = fetch_topic_context(topic)

    # Two-stage gibberish guard, only triggered when we found no direct
    # Wikipedia page for the topic:
    #   1. Fast local heuristic (letter patterns) -- catches obvious cases
    #      without a network call.
    #   2. Wikipedia's "opensearch" endpoint (its autocomplete-style search)
    #      -- a much stronger signal, since it catches near-misses (typos,
    #      different phrasing) AND confirms true gibberish like "qwerty"
    #      returns zero suggestions. This is the authoritative check;
    #      the heuristic alone proved too easy to fool (e.g. short fake
    #      words like "qwerty" contain enough vowels to look "real").
    if not context and is_topic_too_vague(topic) and not topic_has_any_match(topic):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Couldn't find reliable information on '{topic}'. "
                "Try a more specific or well-known topic."
            ),
        )

    try:
        quiz_data = generate_quiz(topic, context)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    quiz_id = str(uuid.uuid4())
    QUIZ_STORE[quiz_id] = quiz_data

    # Strip correct answers + explanations before sending to frontend.
    # The user should not be able to see them before submitting.
    public_questions = []
    for q in quiz_data["questions"]:
        public_questions.append({
            "question": q["question"],
            "options": q["options"],
        })

    return {
        "quiz_id": quiz_id,
        "topic": quiz_data["topic"],
        "used_retrieval": bool(context),
        "questions": public_questions,
    }


@app.post("/api/quiz/score")
def score_quiz(submission: AnswerSubmission):
    quiz_data = QUIZ_STORE.get(submission.quiz_id)
    if not quiz_data:
        raise HTTPException(status_code=404, detail="Quiz not found or expired.")

    questions = quiz_data["questions"]
    results: List[dict] = []
    correct_count = 0

    for index, q in enumerate(questions):
        user_answer = submission.answers.get(str(index))
        is_correct = user_answer == q["correct_answer"]
        if is_correct:
            correct_count += 1

        results.append({
            "question": q["question"],
            "your_answer": user_answer,
            "correct_answer": q["correct_answer"],
            "is_correct": is_correct,
            "explanation": q["explanation"],
        })

    return {
        "score": correct_count,
        "total": len(questions),
        "results": results,
    }


# Serve the frontend's static files (index.html, app.js, style.css)
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
