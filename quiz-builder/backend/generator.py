"""
generator.py
------------
Responsible for ONE thing only: turning (topic + optional context) into
a structured quiz of 5 multiple-choice questions, using Groq's LLM API.

Why Groq:
- Free tier, very fast inference (important when you have 2 hours to build
  and test repeatedly)
- OpenAI-compatible API shape, so swapping providers later is a small change
  (this is the "tradeoff" you can mention in the interview)

Design decision:
We force the LLM to return STRICT JSON (no markdown, no preamble) so we
never have to write fragile regex to extract questions from free-form text.
This is the single most important reliability decision in this project.
"""

import json
import os
from groq import Groq


MODEL_NAME = "llama-3.1-8b-instant"  # fast + free-tier friendly


def _build_prompt(topic: str, context: str) -> str:
    context_block = (
        f"Use the following factual context to ensure accuracy:\n{context}\n\n"
        if context
        else ""
    )

    return f"""You are a quiz generation engine. Generate a multiple-choice quiz
about the topic: "{topic}".

{context_block}Requirements:
- Generate exactly 5 questions.
- Each question must have exactly 4 options labeled A, B, C, D.
- Exactly one option must be correct.
- Include a short explanation (1-2 sentences) for why the correct answer is correct.
- Questions should test understanding, not just trivia recall.

Respond with ONLY valid JSON, no markdown fences, no extra text, in this exact shape:

{{
  "topic": "{topic}",
  "questions": [
    {{
      "question": "string",
      "options": {{
        "A": "string",
        "B": "string",
        "C": "string",
        "D": "string"
      }},
      "correct_answer": "A",
      "explanation": "string"
    }}
  ]
}}
"""


def generate_quiz(topic: str, context: str = "") -> dict:
    """
    Calls Groq's chat completion API and parses the response into a
    Python dict matching our quiz schema.

    Raises ValueError if the model does not return valid JSON, so the
    API layer can turn that into a proper HTTP error instead of silently
    returning garbage to the frontend.
    """
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    prompt = _build_prompt(topic, context)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1500,
        response_format={"type": "json_object"},  # Groq's structured output mode
    )

    raw_text = response.choices[0].message.content

    try:
        quiz_data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model did not return valid JSON: {exc}") from exc

    _validate_quiz_shape(quiz_data)
    return quiz_data


def _validate_quiz_shape(quiz_data: dict) -> None:
    """Defensive check: make sure the LLM actually followed our schema."""
    questions = quiz_data.get("questions")
    if not questions or len(questions) != 5:
        raise ValueError("Quiz must contain exactly 5 questions.")

    for q in questions:
        options = q.get("options", {})
        if set(options.keys()) != {"A", "B", "C", "D"}:
            raise ValueError("Each question must have exactly options A-D.")
        if q.get("correct_answer") not in {"A", "B", "C", "D"}:
            raise ValueError("correct_answer must be one of A, B, C, D.")
