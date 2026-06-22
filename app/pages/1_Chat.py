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
)
from app.utils import inject_custom_css, render_text, render_header, get_theme_colors
from app.auth import require_auth, logout, get_current_user

# ── Page config must come first ───────────────────────────────────────────────
st.set_page_config(
    page_title="Kayfa AI Assistant",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── Auth guard — customers only ───────────────────────────────────────────────
# This must run before any other Streamlit calls.
require_auth(role="customer")

# ── Theme ─────────────────────────────────────────────────────────────────────
inject_custom_css()
c = get_theme_colors()

# Hide sidebar nav so customers can't navigate to the CRM Tickets page
st.markdown(
    "<style>[data-testid='stSidebarNav']{display:none;}</style>",
    unsafe_allow_html=True,
)

user = get_current_user()
username = user["username"]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # User info
    st.markdown(
        f"<div style='padding:0.5rem 0 1rem;'>"
        f"<span style='font-size:0.8rem;color:{c['text_muted']};text-transform:uppercase;"
        f"letter-spacing:.05em;'>Signed in as</span><br>"
        f"<strong style='font-size:1rem;color:{c['text']};'>👤 {username}</strong>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # New chat button — clears current session so a fresh one is created below
    if st.button("➕  New Chat", use_container_width=True):
        for key in ["session_id", "messages", "history"]:
            st.session_state.pop(key, None)
        st.rerun()

    st.markdown(
        f"<hr style='border-color:{c['card_border']};margin:0.75rem 0;'>",
        unsafe_allow_html=True,
    )

    # Past conversations (read-only)
    st.markdown(
        f"<p style='font-size:0.75rem;color:{c['text_muted']};font-weight:600;"
        f"letter-spacing:.06em;margin-bottom:0.5rem;'>PAST CONVERSATIONS</p>",
        unsafe_allow_html=True,
    )

    past_sessions = get_user_sessions(username)

    # Filter out the session currently active
    past_sessions = [
        s for s in past_sessions
        if s["session_id"] != st.session_state.get("session_id")
    ]

    if not past_sessions:
        st.markdown(
            f"<p style='font-size:0.85rem;color:{c['text_muted']};'>No previous chats yet.</p>",
            unsafe_allow_html=True,
        )
    else:
        for s in past_sessions:
            with st.expander(f"💬 {s['preview']}", expanded=False):
                st.markdown(
                    f"<p style='font-size:0.72rem;color:{c['text_muted']};margin-bottom:8px;'>"
                    f"🕐 {s['last_updated'][:16]}</p>",
                    unsafe_allow_html=True,
                )
                for msg in s["messages"]:
                    role_label = "🧑‍💻 You" if msg["role"] == "user" else "🤖 Kayfa"
                    preview_text = msg["content"][:200] + ("…" if len(msg["content"]) > 200 else "")
                    st.markdown(
                        f"<div style='margin-bottom:8px;border-left:3px solid {c['card_border']};"
                        f"padding-left:8px;'>"
                        f"<strong style='font-size:0.8rem;color:{c['text']};'>{role_label}</strong><br>"
                        f"<span style='font-size:0.82rem;color:{c['text_muted']};'>{preview_text}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

    st.markdown(
        f"<hr style='border-color:{c['card_border']};margin:0.75rem 0;'>",
        unsafe_allow_html=True,
    )

    if st.button("🚪  Sign Out", use_container_width=True):
        logout()


# ── Session state init ────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    # Prefix with username so MongoDB can filter sessions by user efficiently
    st.session_state.session_id = f"{username}::{uuid.uuid4()}"

if "messages" not in st.session_state or "history" not in st.session_state:
    ui_msgs, agent_hist = load_session(st.session_state.session_id)
    st.session_state.messages = ui_msgs
    st.session_state.history = agent_hist

if "history" not in st.session_state:
    st.session_state.history = []


# ── Header ────────────────────────────────────────────────────────────────────
render_header(
    "Kayfa AI Sales Assistant",
    "Your courses, pricing & diplomas — answered instantly",
    logo_width=600,
)

# ── Suggestion prompts (empty state only) ─────────────────────────────────────
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
    # Render existing conversation thread
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🧑‍💻" if msg["role"] == "user" else "🤖"):
            st.markdown(render_text(msg["content"]), unsafe_allow_html=True)


# ── Main chat loop ────────────────────────────────────────────────────────────
queued_prompt = st.session_state.pop("queued_prompt", None)
user_input = st.chat_input("Ask me about our courses, prices, or diplomas...")
prompt = user_input or queued_prompt

if prompt:
    # User turn
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(render_text(prompt), unsafe_allow_html=True)

    save_chat_turn(st.session_state.session_id, "user", prompt)

    # Agent turn
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            deps = KayfaDeps(db=kayfa_db, session_id=st.session_state.session_id)
            try:
                result = kayfa_agent.run_sync(
                    prompt,
                    deps=deps,
                    message_history=st.session_state.history,
                )
            except Exception as e:
                st.error(f"{type(e).__name__}: {e}")
                st.write("status_code:", getattr(e, "status_code", None))
                st.write("body:", getattr(e, "body", None))
                st.stop()

            st.markdown(render_text(result.output), unsafe_allow_html=True)

    # Update both memory tracks
    st.session_state.messages.append({"role": "assistant", "content": result.output})
    st.session_state.history += result.new_messages()

    # Persist to MongoDB — username is passed so sessions are queryable per user
    save_session_state(
        st.session_state.session_id,
        st.session_state.messages,
        st.session_state.history,
        username=username,
    )

    st.rerun()