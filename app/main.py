import sys
import uuid
from pathlib import Path
import streamlit as st

# Add the root project directory to Python's import path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# --- 1. MUST BE THE ABSOLUTE FIRST STREAMLIT COMMAND ---
st.set_page_config(
    page_title="Kayfa AI Assistant",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Local Imports
from pydantic_ai.messages import ModelMessage
from agent.bot import kayfa_agent, KayfaDeps
from agent.rag import kayfa_db
from database.mongo import save_chat_turn, load_session, save_session_state
from app.utils import inject_custom_css, render_text, render_header, require_password

# --- 2. THEME, AUTH, HEADER ---
inject_custom_css()

if not require_password("the Kayfa AI Sales Assistant"):
    st.stop()

render_header(
    "Kayfa AI Sales Assistant",
    "Your courses, pricing & diplomas — answered instantly",
    logo_width=600 
)

# --- 3. CHAT STATE INITIALIZATION ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Load the exact state from MongoDB to prevent the memory-wipe bug
if "messages" not in st.session_state or "history" not in st.session_state:
    ui_msgs, agent_hist = load_session(st.session_state.session_id)
    st.session_state.messages = ui_msgs
    st.session_state.history = agent_hist

# PydanticAI's internal memory fallback
if "history" not in st.session_state:
    st.session_state.history = []


# --- 4. SUGGESTION PROMPTS (shown only on the empty state) ---
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
    # --- 5. RENDER EXISTING CONVERSATION ---
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🧑‍💻" if msg["role"] == "user" else "🤖"):
            st.markdown(render_text(msg["content"]), unsafe_allow_html=True)


# --- 6. MAIN CHAT INPUT LOOP ---
queued_prompt = st.session_state.pop("queued_prompt", None)
user_input = st.chat_input("Ask me about our courses, prices, or diplomas...")
prompt = user_input or queued_prompt

if prompt:

    # User Turn
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(render_text(prompt), unsafe_allow_html=True)

    save_chat_turn(st.session_state.session_id, "user", prompt)

    # Agent Turn
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):

            deps = KayfaDeps(
                db=kayfa_db,
                session_id=st.session_state.session_id
            )
            result = kayfa_agent.run_sync(
                prompt,
                deps=deps,
                message_history=st.session_state.history
            )

            st.markdown(render_text(result.output), unsafe_allow_html=True)

    # Update UI & Agent memory
    st.session_state.messages.append({"role": "assistant", "content": result.output})
    st.session_state.history += result.new_messages()

    # Save the dual-track state to MongoDB Atlas
    save_session_state(
        st.session_state.session_id,
        st.session_state.messages,
        st.session_state.history
    )

    # Rerun so the hero/suggestions cleanly give way to the message thread
    st.rerun()