/*
 * app.js
 * ------
 * Pure vanilla JS, no framework. Handles 3 things:
 * 1. Sending the topic to the backend and rendering the returned quiz
 * 2. Collecting the user's selected answers
 * 3. Sending answers to the backend for scoring and rendering results
 *
 * Why no framework (React/Vue):
 * The brief said "UI polish is not the priority" and "any frontend is
 * acceptable." Vanilla JS keeps the project lightweight and avoids
 * build-tooling overhead for a take-home with a tight timeline. This
 * is a deliberate scope decision, not a skill gap -- worth saying
 * explicitly if asked.
 */

const API_BASE = ""; // same-origin, since FastAPI serves the frontend too

let currentQuizId = null;
let currentQuestionCount = 0;

const topicScreen = document.getElementById("topic-screen");
const quizScreen = document.getElementById("quiz-screen");
const resultsScreen = document.getElementById("results-screen");

const topicInput = document.getElementById("topic-input");
const generateBtn = document.getElementById("generate-btn");
const loadingText = document.getElementById("loading-text");
const errorText = document.getElementById("error-text");

const quizTopicHeading = document.getElementById("quiz-topic");
const questionsContainer = document.getElementById("questions-container");
const submitBtn = document.getElementById("submit-btn");

const scoreDisplay = document.getElementById("score-display");
const resultsContainer = document.getElementById("results-container");
const restartBtn = document.getElementById("restart-btn");

generateBtn.addEventListener("click", handleGenerateQuiz);
submitBtn.addEventListener("click", handleSubmitAnswers);
restartBtn.addEventListener("click", resetToTopicScreen);

async function handleGenerateQuiz() {
  const topic = topicInput.value.trim();
  errorText.classList.add("hidden");

  if (!topic) {
    showError("Please enter a topic first.");
    return;
  }

  setLoading(true);

  try {
    const response = await fetch(`${API_BASE}/api/quiz`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic }),
    });

    if (!response.ok) {
      const errBody = await response.json();
      throw new Error(errBody.detail || "Failed to generate quiz.");
    }

    const data = await response.json();
    renderQuiz(data);
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

function renderQuiz(data) {
  currentQuizId = data.quiz_id;
  currentQuestionCount = data.questions.length;

  quizTopicHeading.textContent = `Quiz: ${data.topic}`;
  questionsContainer.innerHTML = "";

  data.questions.forEach((q, index) => {
    const block = document.createElement("div");
    block.className = "question-block";

    const qText = document.createElement("div");
    qText.className = "question-text";
    qText.textContent = `${index + 1}. ${q.question}`;
    block.appendChild(qText);

    Object.entries(q.options).forEach(([letter, optionText]) => {
      const row = document.createElement("label");
      row.className = "option-row";

      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = `question-${index}`;
      radio.value = letter;

      row.appendChild(radio);
      row.appendChild(document.createTextNode(`${letter}. ${optionText}`));
      block.appendChild(row);
    });

    questionsContainer.appendChild(block);
  });

  topicScreen.classList.add("hidden");
  quizScreen.classList.remove("hidden");
}

async function handleSubmitAnswers() {
  const answers = {};
  for (let i = 0; i < currentQuestionCount; i++) {
    const selected = document.querySelector(`input[name="question-${i}"]:checked`);
    answers[i] = selected ? selected.value : null;
  }

  const response = await fetch(`${API_BASE}/api/quiz/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quiz_id: currentQuizId, answers }),
  });

  const data = await response.json();
  renderResults(data);
}

function renderResults(data) {
  scoreDisplay.textContent = `You scored ${data.score} / ${data.total}`;
  resultsContainer.innerHTML = "";

  data.results.forEach((r, index) => {
    const block = document.createElement("div");
    block.className = `result-block ${r.is_correct ? "result-correct" : "result-incorrect"}`;

    const qText = document.createElement("div");
    qText.style.fontWeight = "600";
    qText.textContent = `${index + 1}. ${r.question}`;
    block.appendChild(qText);

    const answerLine = document.createElement("div");
    answerLine.textContent = r.is_correct
      ? `✅ Your answer: ${r.your_answer}`
      : `❌ Your answer: ${r.your_answer ?? "(none)"} — Correct: ${r.correct_answer}`;
    block.appendChild(answerLine);

    const explanation = document.createElement("div");
    explanation.className = "explanation";
    explanation.textContent = r.explanation;
    block.appendChild(explanation);

    resultsContainer.appendChild(block);
  });

  quizScreen.classList.add("hidden");
  resultsScreen.classList.remove("hidden");
}

function resetToTopicScreen() {
  topicInput.value = "";
  currentQuizId = null;
  resultsScreen.classList.add("hidden");
  topicScreen.classList.remove("hidden");
}

function setLoading(isLoading) {
  loadingText.classList.toggle("hidden", !isLoading);
  generateBtn.disabled = isLoading;
}

function showError(message) {
  errorText.textContent = message;
  errorText.classList.remove("hidden");
}
