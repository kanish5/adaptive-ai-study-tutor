"""
RL Agent: UCB1 Multi-Armed Bandit for adaptive topic/difficulty selection.

Each "arm" = (topic, difficulty) pair.
The agent learns which combinations the student struggles with most
and prioritizes them to maximize long-term learning.

Algorithm: UCB1 (Upper Confidence Bound)
  score(arm) = Q(arm) + C * sqrt(ln(total_pulls) / pulls(arm))

  - Q(arm): estimated mastery (exploit known weak areas)
  - Exploration bonus: forces trying under-tested topics
  - C: exploration constant (tunable)
"""

import math
import json
import os
from typing import Optional
from data.topics import get_all_arms, DIFFICULTIES


class UCBAgent:
    """
    UCB1 Bandit Agent for adaptive topic selection.
    
    Reward design:
      - Correct answer:   +1.0 base reward
      - Wrong answer:     +0.0 base reward
      - Difficulty bonus: multiplied by difficulty multiplier
      - Speed bonus:      up to +0.3 for fast answers
    
    The agent MINIMIZES mastery score (weak topics get pulled more).
    This is achieved by inverting the Q-value in UCB selection.
    """

    def __init__(self, exploration_constant: float = 1.5, save_path: Optional[str] = None):
        self.C = exploration_constant
        self.save_path = save_path or "data/agent_state.json"
        self.arms = get_all_arms()
        self.n_arms = len(self.arms)
        self.arm_index = {arm: i for i, arm in enumerate(self.arms)}

        # Per-arm statistics
        self.q_values = [0.5] * self.n_arms      # Estimated mastery (0=bad, 1=perfect)
        self.pull_counts = [0] * self.n_arms      # Times each arm was selected
        self.total_pulls = 0
        self.arm_history = [[] for _ in range(self.n_arms)]  # Raw reward history

        self._load_state()

    # ─────────────────────────────── Selection ───────────────────────────────

    def select_arm(self, locked_topic: Optional[str] = None) -> tuple[str, str]:
        """
        Select the best (topic, difficulty) arm using UCB1.
        
        Args:
            locked_topic: If set, only select from arms with this topic.
        
        Returns:
            (topic_key, difficulty_key)
        """
        candidate_indices = []
        for i, (topic, diff) in enumerate(self.arms):
            if locked_topic and topic != locked_topic:
                continue
            candidate_indices.append(i)

        if not candidate_indices:
            candidate_indices = list(range(self.n_arms))

        # Force exploration: any unvisited arm gets infinite priority
        unvisited = [i for i in candidate_indices if self.pull_counts[i] == 0]
        if unvisited:
            chosen = unvisited[0]
            return self.arms[chosen]

        # UCB1 score: we want to REVISIT weak areas, so invert Q-value
        best_score = -float("inf")
        best_idx = candidate_indices[0]

        for i in candidate_indices:
            weakness = 1.0 - self.q_values[i]   # Higher = student struggles here
            exploration = self.C * math.sqrt(
                math.log(self.total_pulls) / self.pull_counts[i]
            )
            ucb_score = weakness + exploration

            if ucb_score > best_score:
                best_score = ucb_score
                best_idx = i

        return self.arms[best_idx]

    # ──────────────────────────────── Update ─────────────────────────────────

    def update(
        self,
        topic: str,
        difficulty: str,
        correct: bool,
        response_time_seconds: float = 10.0,
    ):
        """
        Update Q-value for the arm after a student answer.

        Args:
            topic: Topic key
            difficulty: Difficulty key
            correct: Whether the student answered correctly
            response_time_seconds: How long the student took
        """
        arm = (topic, difficulty)
        if arm not in self.arm_index:
            return

        i = self.arm_index[arm]
        diff_multiplier = DIFFICULTIES[difficulty]["multiplier"]

        # Compute reward
        base_reward = 1.0 if correct else 0.0

        # Speed bonus: full +0.3 if under 5s, scaling down to 0 at 30s
        speed_bonus = max(0.0, 0.3 * (1.0 - min(response_time_seconds, 30.0) / 30.0))

        raw_reward = (base_reward + (speed_bonus if correct else 0.0)) * diff_multiplier

        # Normalize to [0, 1] (max possible = 1.3 * 2.0 = 2.6 → divide by 2.6)
        reward = min(raw_reward / 2.6, 1.0)

        # Incremental mean update
        self.pull_counts[i] += 1
        self.total_pulls += 1
        n = self.pull_counts[i]
        self.q_values[i] += (reward - self.q_values[i]) / n
        self.arm_history[i].append(reward)

        self._save_state()

    # ──────────────────────────────── Stats ──────────────────────────────────

    def get_topic_mastery(self) -> dict:
        """Return mastery score per topic (averaged across difficulties)."""
        topic_scores = {}
        topic_counts = {}

        for i, (topic, diff) in enumerate(self.arms):
            if self.pull_counts[i] == 0:
                continue
            if topic not in topic_scores:
                topic_scores[topic] = 0.0
                topic_counts[topic] = 0
            topic_scores[topic] += self.q_values[i]
            topic_counts[topic] += 1

        return {
            t: topic_scores[t] / topic_counts[t]
            for t in topic_scores
        }

    def get_weakest_topics(self, n: int = 3) -> list[str]:
        """Return the n weakest topics by mastery score."""
        mastery = self.get_topic_mastery()
        return sorted(mastery, key=lambda t: mastery[t])[:n]

    def get_arm_stats(self) -> list[dict]:
        """Return full stats for all arms (for display)."""
        stats = []
        for i, (topic, diff) in enumerate(self.arms):
            stats.append({
                "topic": topic,
                "difficulty": diff,
                "q_value": round(self.q_values[i], 3),
                "pulls": self.pull_counts[i],
            })
        return stats

    def reset(self):
        """Reset all agent state."""
        self.q_values = [0.5] * self.n_arms
        self.pull_counts = [0] * self.n_arms
        self.total_pulls = 0
        self.arm_history = [[] for _ in range(self.n_arms)]
        self._save_state()

    # ─────────────────────────────── Persistence ─────────────────────────────

    def _save_state(self):
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
        state = {
            "q_values": self.q_values,
            "pull_counts": self.pull_counts,
            "total_pulls": self.total_pulls,
        }
        with open(self.save_path, "w") as f:
            json.dump(state, f)

    def _load_state(self):
        if not os.path.exists(self.save_path):
            return
        try:
            with open(self.save_path) as f:
                state = json.load(f)
            self.q_values = state.get("q_values", self.q_values)
            self.pull_counts = state.get("pull_counts", self.pull_counts)
            self.total_pulls = state.get("total_pulls", 0)
        except Exception:
            pass  # Start fresh on corrupt file
