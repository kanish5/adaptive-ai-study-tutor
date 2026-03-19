"""
Adaptive AI Study Tutor — Main Streamlit Application
=====================================================
Run with: streamlit run app.py

Architecture:
  - UCBAgent (agents/rl_agent.py)     → decides what topic/difficulty to quiz next
  - QuestionGenerator (llm/)          → calls Claude API to generate fresh questions
  - SessionManager (core/)            → tracks answers, streaks, badges in SQLite
"""

import time
import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(__file__))

from agents.rl_agent import UCBAgent
from llm.question_generator import QuestionGenerator
from core.session_manager import SessionManager
from data.topics import TOPICS, DIFFICULTIES

# ──────────────────────────── Page Config ────────────────────────────────────

st.set_page_config(
    page_title="Adaptive AI Tutor",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────── Custom CSS ─────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
    --bg: #0d0f14;
    --surface: #161922;
    --surface2: #1e2330;
    --border: #2a2f3d;
    --accent: #5b8dee;
    --accent2: #43d9ad;
    --warn: #f7b731;
    --danger: #fc5c65;
    --text: #e8ecf4;
    --muted: #6b7394;
}

html, body, [class*="css"] {
    font-family: 'Space Grotesk', sans-serif;
    background-color: var(--bg) !important;
    color: var(--text) !important;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

/* Cards */
.tutor-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}

/* Question card */
.question-card {
    background: linear-gradient(135deg, #1a1f2e 0%, #161922 100%);
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent);
    border-radius: 12px;
    padding: 2rem;
    margin: 1rem 0;
}

/* Option buttons */
.stRadio > div { gap: 0.5rem; }
.stRadio label {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    padding: 0.75rem 1rem !important;
    cursor: pointer;
    transition: all 0.2s ease;
    display: block;
    width: 100%;
}
.stRadio label:hover { border-color: var(--accent) !important; }

/* Metric boxes */
.metric-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem;
    text-align: center;
}
.metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: var(--accent);
    font-family: 'JetBrains Mono', monospace;
}
.metric-label {
    font-size: 0.75rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 0.25rem;
}

/* Progress bar */
.stProgress > div > div { background: var(--accent) !important; }

/* Topic pills */
.topic-pill {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-right: 0.3rem;
}

/* Correct / Wrong banners */
.correct-banner {
    background: rgba(67, 217, 173, 0.1);
    border: 1px solid var(--accent2);
    border-radius: 10px;
    padding: 1.25rem;
    margin: 1rem 0;
}
.wrong-banner {
    background: rgba(252, 92, 101, 0.1);
    border: 1px solid var(--danger);
    border-radius: 10px;
    padding: 1.25rem;
    margin: 1rem 0;
}

/* Badge */
.badge {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.5rem 0.75rem;
    display: inline-block;
    margin: 0.25rem;
    font-size: 0.8rem;
}

/* Sidebar tweaks */
.css-1d391kg, [data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}

/* Buttons */
.stButton > button {
    background: var(--accent) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.5rem !important;
    transition: opacity 0.2s !important;
}
.stButton > button:hover { opacity: 0.85 !important; }

.stButton.secondary > button {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
}

/* Selectbox */
.stSelectbox > div > div {
    background: var(--surface2) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
}

/* Info boxes */
.stAlert { border-radius: 10px !important; }

h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; font-weight: 700; }

.section-title {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--muted);
    margin-bottom: 0.5rem;
    font-weight: 600;
}

.streak-badge {
    background: linear-gradient(135deg, #f7b731, #fc5c65);
    color: white;
    border-radius: 20px;
    padding: 0.2rem 0.75rem;
    font-weight: 700;
    font-size: 0.85rem;
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────── Init State ─────────────────────────────────────

@st.cache_resource
def get_agent():
    return UCBAgent(save_path="data/agent_state.json")

@st.cache_resource
def get_generator():
    return QuestionGenerator()

@st.cache_resource
def get_session():
    mgr = SessionManager()
    return mgr


def init_state():
    defaults = {
        "page": "home",              # home | quiz | results | dashboard
        "question": None,            # current question dict
        "topic": None,
        "difficulty": None,
        "answered": False,
        "selected_option": None,
        "q_start_time": None,
        "session_active": False,
        "locked_topic": None,        # None = RL chooses; str = user-locked
        "hint_shown": False,
        "hint_text": "",
        "questions_this_session": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()
agent = get_agent()
session_mgr = get_session()
gen = get_generator()


# ──────────────────────────── Sidebar ────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.markdown("## 🧠 AI Study Tutor")
        st.markdown("---")

        # All-time stats
        ats = session_mgr.get_all_time_stats()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class='metric-box'>
                <div class='metric-value'>{ats['total_questions']}</div>
                <div class='metric-label'>Questions</div>
            </div>""", unsafe_allow_html=True)
        with col2:
            acc = f"{ats['accuracy']*100:.0f}%"
            st.markdown(f"""
            <div class='metric-box'>
                <div class='metric-value'>{acc}</div>
                <div class='metric-label'>Accuracy</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Navigation
        st.markdown("<div class='section-title'>Navigation</div>", unsafe_allow_html=True)
        if st.button("🏠 Home", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
        if st.button("📊 Dashboard", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()

        st.markdown("---")

        # Topic lock
        st.markdown("<div class='section-title'>Focus Mode</div>", unsafe_allow_html=True)
        topic_options = {"🎲 Let AI Decide": None}
        topic_options.update({
            f"{TOPICS[k]['emoji']} {TOPICS[k]['name']}": k for k in TOPICS
        })
        selected_label = st.selectbox(
            "Topic",
            list(topic_options.keys()),
            label_visibility="collapsed",
        )
        st.session_state.locked_topic = topic_options[selected_label]

        st.markdown("---")

        # Mastery heatmap (simple)
        mastery = agent.get_topic_mastery()
        if mastery:
            st.markdown("<div class='section-title'>Topic Mastery</div>", unsafe_allow_html=True)
            for topic_key, score in sorted(mastery.items(), key=lambda x: x[1]):
                topic = TOPICS.get(topic_key, {})
                name = topic.get("name", topic_key)[:18]
                pct = int(score * 100)
                color = "#43d9ad" if pct >= 70 else "#f7b731" if pct >= 40 else "#fc5c65"
                st.markdown(f"""
                <div style='margin-bottom:0.4rem'>
                  <div style='display:flex;justify-content:space-between;font-size:0.75rem'>
                    <span>{topic.get('emoji','')} {name}</span>
                    <span style='color:{color};font-weight:600'>{pct}%</span>
                  </div>
                  <div style='height:4px;background:#2a2f3d;border-radius:2px;margin-top:2px'>
                    <div style='height:4px;width:{pct}%;background:{color};border-radius:2px'></div>
                  </div>
                </div>""", unsafe_allow_html=True)

        st.markdown("---")

        # Reset
        if st.button("🗑️ Reset All Data", use_container_width=True):
            agent.reset()
            session_mgr.reset_all()
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


# ──────────────────────────── Home Page ──────────────────────────────────────

def render_home():
    st.markdown("# 🧠 Adaptive AI Study Tutor")
    st.markdown(
        "Powered by **Reinforcement Learning** (UCB1 Bandit) + **Claude AI**.\n"
        "The tutor learns your weak spots and focuses there automatically."
    )
    st.markdown("---")

    # Topic cards
    st.markdown("### 📚 Available Topics")
    cols = st.columns(3)
    for i, (key, topic) in enumerate(TOPICS.items()):
        mastery = agent.get_topic_mastery().get(key, 0.5)
        pct = int(mastery * 100)
        with cols[i % 3]:
            st.markdown(f"""
            <div class='tutor-card'>
                <div style='font-size:2rem'>{topic['emoji']}</div>
                <div style='font-weight:700;margin-top:0.5rem'>{topic['name']}</div>
                <div style='font-size:0.8rem;color:#6b7394;margin:0.3rem 0'>{topic['description']}</div>
                <div style='height:3px;background:#2a2f3d;border-radius:2px;margin-top:0.75rem'>
                  <div style='height:3px;width:{pct}%;background:{topic['color']};border-radius:2px'></div>
                </div>
                <div style='font-size:0.7rem;color:#6b7394;margin-top:0.25rem'>Mastery: {pct}%</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🚀 Start Quiz Session", use_container_width=True):
            _start_quiz()
    with col2:
        if st.button("📊 View Dashboard", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()


def _start_quiz():
    if not st.session_state.session_active:
        session_mgr.start_session()
        gen.clear_cache()
        st.session_state.session_active = True
        st.session_state.questions_this_session = 0
    _load_next_question()
    st.session_state.page = "quiz"
    st.rerun()


# ──────────────────────────── Quiz Page ──────────────────────────────────────

def _load_next_question():
    """Use RL agent to pick next arm, then generate question."""
    locked = st.session_state.locked_topic
    topic_key, diff_key = agent.select_arm(locked_topic=locked)

    with st.spinner("🤖 Generating your next question..."):
        prev_q = session_mgr.get_recent_questions(5)
        question = gen.generate_question(topic_key, diff_key, prev_q)

    st.session_state.question = question
    st.session_state.topic = topic_key
    st.session_state.difficulty = diff_key
    st.session_state.answered = False
    st.session_state.selected_option = None
    st.session_state.q_start_time = time.time()
    st.session_state.hint_shown = False
    st.session_state.hint_text = ""


def render_quiz():
    q = st.session_state.question
    if q is None:
        st.warning("No question loaded. Go back home to start.")
        return

    topic_key = st.session_state.topic
    diff_key = st.session_state.difficulty
    topic = TOPICS.get(topic_key, {})
    diff = DIFFICULTIES.get(diff_key, {})

    # ── Header bar ──
    col_t, col_d, col_s, col_n = st.columns([3, 2, 2, 1])
    with col_t:
        st.markdown(f"### {topic.get('emoji','')} {topic.get('name','')}")
    with col_d:
        st.markdown(f"**Difficulty:** {diff.get('emoji','')} {diff.get('name','')}")
    with col_s:
        if session_mgr.current_streak > 0:
            st.markdown(
                f"<span class='streak-badge'>🔥 {session_mgr.current_streak} streak</span>",
                unsafe_allow_html=True,
            )
    with col_n:
        st.markdown(f"**Q #{st.session_state.questions_this_session + 1}**")

    # ── Question ──
    st.markdown(f"""
    <div class='question-card'>
        <p style='font-size:0.7rem;color:#6b7394;text-transform:uppercase;letter-spacing:0.1em;margin:0'>Question</p>
        <p style='font-size:1.15rem;font-weight:500;margin:0.5rem 0 0'>{q.get('question','')}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Options ──
    options = q.get("options", {})
    option_labels = [f"{k}. {v}" for k, v in options.items()]

    if not st.session_state.answered:
        chosen = st.radio(
            "Choose your answer:",
            option_labels,
            key=f"radio_{st.session_state.questions_this_session}",
            label_visibility="collapsed",
        )
        st.session_state.selected_option = chosen[0] if chosen else None

        col_submit, col_hint, col_skip = st.columns([2, 1, 1])
        with col_submit:
            if st.button("✅ Submit Answer", use_container_width=True):
                _submit_answer()
        with col_hint:
            if st.button("💡 Hint", use_container_width=True):
                with st.spinner("Thinking of a hint..."):
                    st.session_state.hint_text = gen.get_hint(
                        q["question"], options, q["correct_answer"]
                    )
                st.session_state.hint_shown = True
                st.rerun()
        with col_skip:
            if st.button("⏭ Skip", use_container_width=True):
                _load_next_question()
                st.rerun()

        if st.session_state.hint_shown and st.session_state.hint_text:
            st.info(f"💡 **Hint:** {st.session_state.hint_text}")

    else:
        # ── Show result ──
        selected = st.session_state.selected_option
        correct = q.get("correct_answer", "")
        is_correct = selected == correct

        # Render all options with color coding
        for key, val in options.items():
            label = f"{key}. {val}"
            if key == correct:
                st.success(f"✅ {label}")
            elif key == selected and not is_correct:
                st.error(f"❌ {label}")
            else:
                st.markdown(f"&nbsp;&nbsp;&nbsp;{label}")

        if is_correct:
            st.markdown(f"""
            <div class='correct-banner'>
                <strong>🎉 Correct!</strong><br>
                {q.get('explanation','')}
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class='wrong-banner'>
                <strong>❌ Not quite.</strong> The answer was <strong>{correct}</strong>.<br>
                {q.get('explanation','')}
            </div>""", unsafe_allow_html=True)

        if q.get("fun_fact"):
            st.markdown(f"🌟 **Fun fact:** {q['fun_fact']}")

        col_next, col_end = st.columns([2, 1])
        with col_next:
            if st.button("➡️ Next Question", use_container_width=True):
                _load_next_question()
                st.rerun()
        with col_end:
            if st.button("🏁 End Session", use_container_width=True):
                _end_session()


def _submit_answer():
    q = st.session_state.question
    selected = st.session_state.selected_option
    if not selected:
        st.warning("Please select an answer first.")
        return

    correct = q.get("correct_answer", "")
    is_correct = selected == correct
    elapsed = time.time() - (st.session_state.q_start_time or time.time())

    # Update RL agent
    agent.update(
        topic=st.session_state.topic,
        difficulty=st.session_state.difficulty,
        correct=is_correct,
        response_time_seconds=elapsed,
    )

    # Record in session
    session_mgr.record_answer(
        topic=st.session_state.topic,
        difficulty=st.session_state.difficulty,
        question_text=q.get("question", ""),
        selected=selected,
        correct_answer=correct,
        is_correct=is_correct,
        response_time=elapsed,
    )

    st.session_state.answered = True
    st.session_state.questions_this_session += 1
    st.rerun()


def _end_session():
    summary = session_mgr.end_session()
    st.session_state.session_active = False
    st.session_state.page = "results"
    st.session_state.last_summary = summary
    st.rerun()


# ──────────────────────────── Results Page ───────────────────────────────────

def render_results():
    summary = st.session_state.get("last_summary", {})
    st.markdown("# 🏁 Session Complete!")

    total = summary.get("total", 0)
    correct = summary.get("correct", 0)
    accuracy = summary.get("accuracy", 0)

    # Big stats
    c1, c2, c3, c4 = st.columns(4)
    for col, val, label in zip(
        [c1, c2, c3, c4],
        [total, correct, f"{accuracy*100:.0f}%", summary.get("max_streak", 0)],
        ["Questions", "Correct", "Accuracy", "Best Streak"],
    ):
        with col:
            st.markdown(f"""
            <div class='metric-box'>
                <div class='metric-value'>{val}</div>
                <div class='metric-label'>{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Topic breakdown
    if summary.get("by_topic"):
        st.markdown("### 📊 Breakdown by Topic")
        cols = st.columns(len(summary["by_topic"]))
        for col, (t_key, t_stats) in zip(cols, summary["by_topic"].items()):
            t = TOPICS.get(t_key, {})
            with col:
                acc = t_stats["accuracy"]
                color = "#43d9ad" if acc >= 0.7 else "#f7b731" if acc >= 0.4 else "#fc5c65"
                st.markdown(f"""
                <div class='tutor-card' style='text-align:center'>
                    <div style='font-size:1.5rem'>{t.get('emoji','')}</div>
                    <div style='font-size:0.85rem;font-weight:600'>{t.get('name', t_key)}</div>
                    <div style='font-size:1.5rem;font-weight:700;color:{color}'>{int(acc*100)}%</div>
                    <div style='font-size:0.75rem;color:#6b7394'>{t_stats['correct']}/{t_stats['total']} correct</div>
                </div>""", unsafe_allow_html=True)

    # Badges
    badges = session_mgr.get_badges()
    if badges:
        st.markdown("### 🏅 Badges Earned")
        badge_html = "".join(
            f"<span class='badge'>{b['icon']} <strong>{b['name']}</strong> — {b['desc']}</span>"
            for b in badges
        )
        st.markdown(badge_html, unsafe_allow_html=True)

    # AI summary
    if total > 0:
        st.markdown("### 🤖 AI Study Coach Says...")
        with st.spinner("Generating personalized feedback..."):
            weak = agent.get_weakest_topics(3)
            topics_done = list(summary.get("by_topic", {}).keys())
            ai_summary = gen.generate_session_summary(topics_done, correct, total, weak)
        st.info(ai_summary)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Start New Session", use_container_width=True):
            _start_quiz()
    with col2:
        if st.button("📊 View Dashboard", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()


# ──────────────────────────── Dashboard ──────────────────────────────────────

def render_dashboard():
    st.markdown("# 📊 Learning Dashboard")
    st.markdown("*Powered by the UCB1 RL agent — tracks your adaptive learning journey*")
    st.markdown("---")

    # All-time stats
    ats = session_mgr.get_all_time_stats()
    c1, c2, c3, c4 = st.columns(4)
    for col, val, label in zip(
        [c1, c2, c3, c4],
        [
            ats["sessions"],
            ats["total_questions"],
            ats["correct"],
            f"{ats['accuracy']*100:.0f}%",
        ],
        ["Sessions", "Total Questions", "Correct", "All-Time Accuracy"],
    ):
        with col:
            st.markdown(f"""
            <div class='metric-box'>
                <div class='metric-value'>{val}</div>
                <div class='metric-label'>{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # RL Agent internals
    st.markdown("### 🤖 RL Agent — Arm Exploration Map")
    st.markdown(
        "Each cell = (topic × difficulty) arm. The agent uses **UCB1** to prioritize "
        "your weakest, least-explored areas."
    )

    arm_stats = agent.get_arm_stats()
    col_headers = list(DIFFICULTIES.keys())
    row_headers = list(TOPICS.keys())

    header_cols = st.columns([2] + [1] * len(col_headers))
    header_cols[0].markdown("**Topic**")
    for i, d in enumerate(col_headers):
        header_cols[i + 1].markdown(f"**{DIFFICULTIES[d]['emoji']} {DIFFICULTIES[d]['name']}**")

    for topic_key in row_headers:
        cols = st.columns([2] + [1] * len(col_headers))
        topic = TOPICS[topic_key]
        cols[0].markdown(f"{topic['emoji']} {topic['name']}")
        for j, diff_key in enumerate(col_headers):
            stat = next((s for s in arm_stats if s["topic"] == topic_key and s["difficulty"] == diff_key), None)
            if stat:
                q = stat["q_value"]
                pulls = stat["pulls"]
                color = "#43d9ad" if q >= 0.7 else "#f7b731" if q >= 0.4 else "#fc5c65"
                if pulls == 0:
                    color = "#6b7394"
                cols[j + 1].markdown(
                    f"<span style='color:{color};font-family:JetBrains Mono;font-size:0.85rem'>"
                    f"{q:.2f}</span><br><span style='font-size:0.65rem;color:#6b7394'>{pulls} tries</span>",
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    # Topic mastery chart using Streamlit native
    mastery = agent.get_topic_mastery()
    if mastery:
        st.markdown("### 📈 Topic Mastery")
        import pandas as pd
        df = pd.DataFrame([
            {"Topic": TOPICS[t]["name"], "Mastery": round(v * 100, 1)}
            for t, v in sorted(mastery.items(), key=lambda x: x[1])
        ])
        st.bar_chart(df.set_index("Topic"))

    # Topic performance from DB
    perf = session_mgr.get_topic_performance()
    if perf:
        st.markdown("### 📋 Historical Performance")
        rows = []
        for t_key, stats in perf.items():
            t = TOPICS.get(t_key, {})
            rows.append({
                "Topic": f"{t.get('emoji','')} {t.get('name', t_key)}",
                "Total Questions": stats["total"],
                "Correct": stats["correct"],
                "Accuracy": f"{stats['accuracy']*100:.1f}%",
                "Avg Time (s)": stats["avg_time"],
            })
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Badges
    badges = session_mgr.get_badges()
    if badges:
        st.markdown("### 🏅 Achievements")
        badge_html = "".join(
            f"<span class='badge'>{b['icon']} <strong>{b['name']}</strong> — {b['desc']}</span>"
            for b in badges
        )
        st.markdown(badge_html, unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🚀 Start Quiz", use_container_width=True):
        _start_quiz()


# ──────────────────────────── Router ─────────────────────────────────────────

render_sidebar()

page = st.session_state.page
if page == "home":
    render_home()
elif page == "quiz":
    render_quiz()
elif page == "results":
    render_results()
elif page == "dashboard":
    render_dashboard()
