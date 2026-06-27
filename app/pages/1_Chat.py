import sys
import uuid
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from agent.bot import kayfa_agent, KayfaDeps
from agent.rag import kayfa_db
from database.mongo import (
    save_chat_turn,
    load_session,
    save_session_state,
    get_user_sessions,
    delete_session
)

from app.utils import inject_custom_css, render_text, render_header, get_theme_colors
from app.auth import require_auth, logout, get_current_user

st.set_page_config(
    page_title="Kayfa AI Assistant",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded",
)
import time
from agent.logger import log_agent_turn
from app.auth import get_current_user

# ── Auth guard ────────────────────────────────────────────────────────────────
require_auth(role="customer")

# ── Theme ─────────────────────────────────────────────────────────────────────
inject_custom_css()
c = get_theme_colors()

st.markdown(
    "<style>[data-testid='stSidebarNav']{display:none;}</style>",
    unsafe_allow_html=True,
)

user = get_current_user()
username = user["username"]

# ── Session init ──────────────────────────────────────────────────────────────
# Must happen before sidebar so session_id exists when filtering past sessions
if "session_id" not in st.session_state:
    st.session_state.session_id = f"{username}::{uuid.uuid4()}"

if "messages" not in st.session_state or "history" not in st.session_state:
    ui_msgs, agent_hist = load_session(st.session_state.session_id)
    st.session_state.messages = ui_msgs
    st.session_state.history = agent_hist

if "history" not in st.session_state:
    st.session_state.history = []

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # User info
    st.markdown(
        f"<div style='padding:0.5rem 0 1rem;'>"
        f"<span style='font-size:0.75rem;color:{c['text_muted']};text-transform:uppercase;"
        f"letter-spacing:.06em;'>Signed in as</span><br>"
        f"<strong style='font-size:1rem;color:{c['text']};'>👤 {username}</strong>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if st.button("➕  New Chat", use_container_width=True):
        for key in ["session_id", "messages", "history"]:
            st.session_state.pop(key, None)
        # Also clear any pending delete confirmations
        for key in list(st.session_state.keys()):
            if key.startswith("confirm_delete_"):
                del st.session_state[key]
        st.rerun()

    st.markdown(
        f"<hr style='border-color:{c['card_border']};margin:0.75rem 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='font-size:0.75rem;color:{c['text_muted']};font-weight:600;"
        f"letter-spacing:.06em;margin-bottom:0.6rem;'>CONVERSATIONS</p>",
        unsafe_allow_html=True,
    )

    # Load all sessions for this user, excluding the one currently active
    past_sessions = [
        s for s in get_user_sessions(username)
        if s["session_id"] != st.session_state.get("session_id")
    ]

    if not past_sessions:
        st.markdown(
            f"<p style='font-size:0.85rem;color:{c['text_muted']};'>No previous chats yet.</p>",
            unsafe_allow_html=True,
        )
    else:
        for s in past_sessions:
            sid = s["session_id"]
            confirm_key = f"confirm_delete_{sid}"

            # Session preview card
            st.markdown(
                f"<div style='margin-bottom:2px;'>"
                f"<span style='font-size:0.85rem;color:{c['text']};font-weight:500;'>"
                f"💬 {s['preview']}</span><br>"
                f"<span style='font-size:0.72rem;color:{c['text_muted']};'>"
                f"🕐 {s['last_updated'][:16]}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            if st.session_state.get(confirm_key):
                # ── Delete confirmation state ──────────────────────────────
                st.markdown(
                    f"<p style='font-size:0.8rem;color:{c['danger_text']};margin:4px 0;'>"
                    f"⚠️ Delete this chat?</p>",
                    unsafe_allow_html=True,
                )
                yes_col, no_col = st.columns(2)
                with yes_col:
                    if st.button("✅ Yes", key=f"yes_{sid}", use_container_width=True):
                        delete_session(sid)
                        st.session_state.pop(confirm_key, None)
                        # If deleted session was somehow loaded, clear it
                        if st.session_state.get("session_id") == sid:
                            for key in ["session_id", "messages", "history"]:
                                st.session_state.pop(key, None)
                        st.rerun()
                with no_col:
                    if st.button("❌ No", key=f"no_{sid}", use_container_width=True):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
            else:
                # ── Normal state: Resume + Delete buttons ──────────────────
                resume_col, delete_col = st.columns([3, 1])
                with resume_col:
                    if st.button(
                        "▶ Resume", key=f"resume_{sid}", use_container_width=True
                    ):
                        # Load the selected session as the active one
                        ui_msgs, agent_hist = load_session(sid)
                        st.session_state.session_id = sid
                        st.session_state.messages = ui_msgs
                        st.session_state.history = agent_hist
                        st.rerun()
                with delete_col:
                    if st.button("🗑", key=f"del_{sid}", use_container_width=True):
                        st.session_state[confirm_key] = True
                        st.rerun()

            st.markdown(
                f"<hr style='margin:6px 0;border-color:{c['card_border']};'>",
                unsafe_allow_html=True,
            )

    st.markdown(
        f"<hr style='border-color:{c['card_border']};margin:0.5rem 0;'>",
        unsafe_allow_html=True,
    )
    if st.button("🚪  Sign Out", use_container_width=True):
        logout()


# ── Header ────────────────────────────────────────────────────────────────────
render_header(
    "Kayfa AI Sales Assistant",
    "Your courses, pricing & diplomas — answered instantly",
    logo_width=600,
)

# ── Suggestions (empty state only) ───────────────────────────────────────────
SUGGESTIONS = [
    ("📚", "Available courses", "What courses do you currently offer?"),
    ("💰", "Pricing & diplomas", "Can you tell me about your course prices and diploma options?"),
    ("🎓", "Certification", "How does the certification process work?"),
    ("📅", "Enrollment dates", "When does the next enrollment period start?"),
]

if not st.session_state.messages:
    st.markdown(
        """
        <div class="kayfa-hero">
            <h1>How can I help you today?</h1>
            <p>Ask about our courses, pricing, diplomas, or anything else about Kayfa.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for i, (emoji, short, full_question) in enumerate(SUGGESTIONS):
        if cols[i % 2].button(f"{emoji}  {short}", key=f"sugg_{i}", use_container_width=True):
            st.session_state.queued_prompt = full_question
            st.rerun()
else:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🧑‍💻" if msg["role"] == "user" else "🤖"):
            st.markdown(render_text(msg["content"]), unsafe_allow_html=True)

# ── Chat loop ─────────────────────────────────────────────────────────────────
queued_prompt = st.session_state.pop("queued_prompt", None)
user_input = st.chat_input("Ask me about our courses, prices, or diplomas...")
prompt = user_input or queued_prompt

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(render_text(prompt), unsafe_allow_html=True)

    save_chat_turn(st.session_state.session_id, "user", prompt)

    # Agent turn
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            deps = KayfaDeps(db=kayfa_db, session_id=st.session_state.session_id)
            history_window = st.session_state.history[-6:] if len(st.session_state.history) > 6 else st.session_state.history
            
            start_time = time.time()
            try:
                result = kayfa_agent.run_sync(
                    prompt,
                    deps=deps,
                    message_history=history_window,
                )
            except Exception as e:
                st.error(f"{type(e).__name__}: {e}")
                st.write("status_code:", getattr(e, "status_code", None))
                st.write("body:", getattr(e, "body", None))
                st.stop()

            latency = time.time() - start_time
            st.markdown(render_text(result.output), unsafe_allow_html=True)
            
            # --- PART 2: TRACE & COST LOGGING ---
            user = get_current_user()
            user_id = user["username"] if user else "anonymous"
            log_agent_turn(result, st.session_state.session_id, user_id, latency)

    st.session_state.messages.append({"role": "assistant", "content": result.output})
    st.session_state.history += result.new_messages()

    save_session_state(
        st.session_state.session_id,
        st.session_state.messages,
        st.session_state.history,
        username=username,
    )

    st.rerun()