"""
Session Manager: Tracks quiz sessions, answers, and performance over time.
Uses SQLite for lightweight, local persistence — no external database needed.
"""

import sqlite3
import time
import os
from dataclasses import dataclass, field
from typing import Optional


DB_PATH = "data/tutor.db"


@dataclass
class Answer:
    question_id: int
    topic: str
    difficulty: str
    question_text: str
    selected: str
    correct_answer: str
    is_correct: bool
    response_time: float
    timestamp: float = field(default_factory=time.time)


class SessionManager:
    """
    Manages quiz session state and persistent history.

    Responsibilities:
    - Start / end sessions
    - Record individual answers
    - Query performance stats (per topic, per session)
    - Track streaks and badges
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

        # In-memory session state
        self.session_id: Optional[int] = None
        self.session_answers: list[Answer] = []
        self.session_start: Optional[float] = None
        self.current_streak: int = 0
        self.question_cache: list[str] = []

    # ──────────────────────────── DB Setup ───────────────────────────────────

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at  REAL NOT NULL,
                    ended_at    REAL,
                    total_q     INTEGER DEFAULT 0,
                    correct_q   INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS answers (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id      INTEGER NOT NULL,
                    topic           TEXT NOT NULL,
                    difficulty      TEXT NOT NULL,
                    question_text   TEXT NOT NULL,
                    selected        TEXT NOT NULL,
                    correct_answer  TEXT NOT NULL,
                    is_correct      INTEGER NOT NULL,
                    response_time   REAL NOT NULL,
                    timestamp       REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );
            """)

    def _conn(self):
        return sqlite3.connect(self.db_path)

    # ──────────────────────────── Session Lifecycle ───────────────────────────

    def start_session(self) -> int:
        """Start a new quiz session. Returns the session ID."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO sessions (started_at) VALUES (?)", (time.time(),)
            )
            self.session_id = cur.lastrowid

        self.session_answers = []
        self.session_start = time.time()
        self.current_streak = 0
        self.question_cache = []
        return self.session_id

    def end_session(self) -> dict:
        """End current session and return summary stats."""
        if self.session_id is None:
            return {}

        total = len(self.session_answers)
        correct = sum(1 for a in self.session_answers if a.is_correct)

        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET ended_at=?, total_q=?, correct_q=? WHERE id=?",
                (time.time(), total, correct, self.session_id),
            )

        summary = self.get_session_stats()
        self.session_id = None
        self.session_answers = []
        return summary

    # ──────────────────────────── Recording ──────────────────────────────────

    def record_answer(
        self,
        topic: str,
        difficulty: str,
        question_text: str,
        selected: str,
        correct_answer: str,
        is_correct: bool,
        response_time: float,
    ) -> Answer:
        """Save an answer to DB and update in-memory state."""
        if self.session_id is None:
            self.start_session()

        answer = Answer(
            question_id=len(self.session_answers) + 1,
            topic=topic,
            difficulty=difficulty,
            question_text=question_text,
            selected=selected,
            correct_answer=correct_answer,
            is_correct=is_correct,
            response_time=response_time,
        )
        self.session_answers.append(answer)
        self.question_cache.append(question_text)

        # Update streak
        if is_correct:
            self.current_streak += 1
        else:
            self.current_streak = 0

        with self._conn() as conn:
            conn.execute(
                """INSERT INTO answers
                   (session_id, topic, difficulty, question_text, selected,
                    correct_answer, is_correct, response_time, timestamp)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    self.session_id, topic, difficulty, question_text,
                    selected, correct_answer, int(is_correct),
                    response_time, answer.timestamp,
                ),
            )

        return answer

    # ──────────────────────────── Stats Queries ───────────────────────────────

    def get_session_stats(self) -> dict:
        """Stats for the current/just-ended session."""
        if not self.session_answers:
            return {"total": 0, "correct": 0, "accuracy": 0.0, "by_topic": {}}

        total = len(self.session_answers)
        correct = sum(1 for a in self.session_answers if a.is_correct)
        by_topic: dict[str, dict] = {}

        for a in self.session_answers:
            if a.topic not in by_topic:
                by_topic[a.topic] = {"total": 0, "correct": 0}
            by_topic[a.topic]["total"] += 1
            if a.is_correct:
                by_topic[a.topic]["correct"] += 1

        for t in by_topic:
            t_data = by_topic[t]
            t_data["accuracy"] = t_data["correct"] / t_data["total"]

        avg_time = sum(a.response_time for a in self.session_answers) / total

        return {
            "total": total,
            "correct": correct,
            "accuracy": correct / total,
            "by_topic": by_topic,
            "avg_response_time": round(avg_time, 1),
            "max_streak": self.current_streak,
        }

    def get_all_time_stats(self) -> dict:
        """Aggregate stats across all sessions."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*), SUM(total_q), SUM(correct_q) FROM sessions WHERE ended_at IS NOT NULL"
            ).fetchone()

        sessions, total_q, correct_q = row
        total_q = total_q or 0
        correct_q = correct_q or 0

        return {
            "sessions": sessions or 0,
            "total_questions": total_q,
            "correct": correct_q,
            "accuracy": (correct_q / total_q) if total_q > 0 else 0.0,
        }

    def get_topic_performance(self) -> dict[str, dict]:
        """Performance breakdown by topic across all sessions."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT topic,
                          COUNT(*) as total,
                          SUM(is_correct) as correct,
                          AVG(response_time) as avg_time
                   FROM answers
                   GROUP BY topic"""
            ).fetchall()

        result = {}
        for row in rows:
            topic, total, correct, avg_time = row
            result[topic] = {
                "total": total,
                "correct": correct,
                "accuracy": correct / total,
                "avg_time": round(avg_time, 1),
            }
        return result

    def get_recent_questions(self, n: int = 5) -> list[str]:
        """Get recent question texts to avoid repetition."""
        return self.question_cache[-n:]

    def get_badges(self) -> list[dict]:
        """Return earned achievement badges."""
        stats = self.get_all_time_stats()
        session_stats = self.get_session_stats()
        badges = []

        if stats["total_questions"] >= 10:
            badges.append({"icon": "🎯", "name": "First 10", "desc": "Answered 10 questions"})
        if stats["total_questions"] >= 50:
            badges.append({"icon": "📚", "name": "Bookworm", "desc": "Answered 50 questions"})
        if stats["accuracy"] >= 0.8 and stats["total_questions"] >= 5:
            badges.append({"icon": "🏆", "name": "High Achiever", "desc": "80%+ overall accuracy"})
        if self.current_streak >= 5:
            badges.append({"icon": "🔥", "name": "On Fire", "desc": "5 correct in a row"})
        if session_stats.get("accuracy", 0) == 1.0 and session_stats.get("total", 0) >= 5:
            badges.append({"icon": "💎", "name": "Perfect Round", "desc": "100% in a session"})

        return badges

    def reset_all(self):
        """Wipe all stored data (use with caution)."""
        with self._conn() as conn:
            conn.executescript("DELETE FROM answers; DELETE FROM sessions;")
        self.session_id = None
        self.session_answers = []
