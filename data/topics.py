"""
Topic and difficulty definitions for the Adaptive AI Study Tutor.
Add or modify topics here to customize the tutor for any subject.
"""

TOPICS = {
    "search_algorithms": {
        "name": "Search Algorithms",
        "emoji": "🔍",
        "description": "BFS, DFS, A*, Dijkstra, heuristics",
        "color": "#4F8EF7",
    },
    "reinforcement_learning": {
        "name": "Reinforcement Learning",
        "emoji": "🤖",
        "description": "Q-learning, MDPs, rewards, policies",
        "color": "#F76C6C",
    },
    "machine_learning": {
        "name": "Machine Learning",
        "emoji": "📊",
        "description": "Supervised, unsupervised, evaluation metrics",
        "color": "#43D9AD",
    },
    "neural_networks": {
        "name": "Neural Networks",
        "emoji": "🧠",
        "description": "Backprop, activation functions, CNNs, RNNs",
        "color": "#F7B731",
    },
    "nlp": {
        "name": "Natural Language Processing",
        "emoji": "💬",
        "description": "Tokenization, transformers, embeddings, LLMs",
        "color": "#A55EEA",
    },
    "probability": {
        "name": "Probability & Bayesian AI",
        "emoji": "🎲",
        "description": "Bayes theorem, Naive Bayes, HMMs, inference",
        "color": "#FC5C65",
    },
}

DIFFICULTIES = {
    "easy": {
        "name": "Easy",
        "emoji": "🌱",
        "description": "Basic definitions and concepts",
        "multiplier": 1.0,
    },
    "medium": {
        "name": "Medium",
        "emoji": "⚡",
        "description": "Application and analysis",
        "multiplier": 1.5,
    },
    "hard": {
        "name": "Hard",
        "emoji": "🔥",
        "description": "Complex reasoning and edge cases",
        "multiplier": 2.0,
    },
}

# All (topic, difficulty) arms for the RL bandit
def get_all_arms():
    arms = []
    for topic_key in TOPICS:
        for diff_key in DIFFICULTIES:
            arms.append((topic_key, diff_key))
    return arms
