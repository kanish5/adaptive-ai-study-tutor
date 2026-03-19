"""
LLM Question Generator using the Anthropic API.

Generates multiple-choice questions tailored to:
  - Topic (e.g., Search Algorithms, Neural Networks)
  - Difficulty (easy / medium / hard)
  - Previously asked questions (to avoid repetition)

Returns structured JSON every time for reliable parsing.
"""

import json
import re
import time
import anthropic
from data.topics import TOPICS, DIFFICULTIES


# ─────────────────────── Prompt Templates ────────────────────────────────────

SYSTEM_PROMPT = """You are an expert AI tutor specializing in computer science and artificial intelligence.
Your job is to generate high-quality multiple-choice quiz questions.

STRICT RULES:
1. Always respond with VALID JSON only — no markdown, no preamble, no backticks.
2. Every question must have exactly 4 answer options labeled A, B, C, D.
3. The correct answer must be one of A, B, C, or D.
4. Explanations should be educational and 2-3 sentences.
5. Match difficulty precisely: easy=recall, medium=apply, hard=analyze/edge-cases.
"""

QUESTION_TEMPLATE = """Generate ONE multiple-choice question with these constraints:

Topic: {topic_name}
Topic Description: {topic_desc}
Difficulty: {difficulty_name} ({difficulty_desc})
Previously asked questions (DO NOT repeat): {prev_questions}

Respond with this exact JSON structure:
{{
  "question": "The full question text here?",
  "options": {{
    "A": "First option",
    "B": "Second option",
    "C": "Third option",
    "D": "Fourth option"
  }},
  "correct_answer": "A",
  "explanation": "Why the correct answer is right, and why the others are wrong.",
  "fun_fact": "One interesting related fact to make learning engaging."
}}"""

HINT_TEMPLATE = """A student is answering this question and needs a hint.
Do NOT give away the answer directly.

Question: {question}
Options: {options}
Correct Answer: {correct} (keep this secret!)

Give a short helpful hint (1-2 sentences) in plain text (not JSON)."""

SUMMARY_TEMPLATE = """Based on this student's quiz session, write a personalized 3-sentence study summary.
Be encouraging but honest about weak areas.

Topics attempted: {topics}
Correct answers: {correct}/{total}
Weakest topics: {weak_topics}

Respond in plain text (not JSON)."""


# ─────────────────────── Main Generator Class ────────────────────────────────

class QuestionGenerator:
    """Generates quiz questions and hints using Claude via Anthropic API."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic()
        self.model = model
        self._question_cache: list[str] = []  # Track used questions

    def generate_question(
        self,
        topic_key: str,
        difficulty_key: str,
        prev_questions: list[str] | None = None,
    ) -> dict:
        """
        Generate a fresh MCQ for the given topic and difficulty.

        Returns:
            {
                "question": str,
                "options": {"A": str, "B": str, "C": str, "D": str},
                "correct_answer": str,   # "A", "B", "C", or "D"
                "explanation": str,
                "fun_fact": str,
                "topic": str,
                "difficulty": str,
                "generated_at": float
            }
        """
        topic = TOPICS[topic_key]
        difficulty = DIFFICULTIES[difficulty_key]
        prev = prev_questions or self._question_cache[-5:]

        prompt = QUESTION_TEMPLATE.format(
            topic_name=topic["name"],
            topic_desc=topic["description"],
            difficulty_name=difficulty["name"],
            difficulty_desc=difficulty["description"],
            prev_questions=json.dumps(prev) if prev else "None yet",
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        data = self._parse_json(raw)

        # Add metadata
        data["topic"] = topic_key
        data["difficulty"] = difficulty_key
        data["generated_at"] = time.time()

        # Cache question text
        self._question_cache.append(data.get("question", ""))

        return data

    def get_hint(self, question: str, options: dict, correct_answer: str) -> str:
        """Generate a non-spoiler hint for the student."""
        options_str = "\n".join(f"{k}: {v}" for k, v in options.items())
        prompt = HINT_TEMPLATE.format(
            question=question,
            options=options_str,
            correct=correct_answer,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    def generate_session_summary(
        self,
        topics_attempted: list[str],
        correct: int,
        total: int,
        weak_topics: list[str],
    ) -> str:
        """Generate a personalized study summary after a session."""
        topic_names = [TOPICS[t]["name"] for t in topics_attempted if t in TOPICS]
        weak_names = [TOPICS[t]["name"] for t in weak_topics if t in TOPICS]

        prompt = SUMMARY_TEMPLATE.format(
            topics=", ".join(topic_names) or "None",
            correct=correct,
            total=total,
            weak_topics=", ".join(weak_names) or "None identified yet",
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    def clear_cache(self):
        """Reset question cache (new session)."""
        self._question_cache.clear()

    # ──────────────────────────── Helpers ────────────────────────────────────

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Robustly parse JSON from LLM response."""
        # Strip markdown fences if present
        text = re.sub(r"```(?:json)?", "", text).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try extracting first {...} block
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            # Return a fallback error question
            return {
                "question": "⚠️ Could not generate question. Please try again.",
                "options": {"A": "Retry", "B": "Skip", "C": "Change topic", "D": "End session"},
                "correct_answer": "A",
                "explanation": "The LLM response could not be parsed.",
                "fun_fact": "",
            }
