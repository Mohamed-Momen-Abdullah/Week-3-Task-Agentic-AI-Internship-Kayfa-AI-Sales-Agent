import sys
from pathlib import Path

# Add the root project directory to Python's import path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import uuid
from pydantic_ai.messages import ModelMessage
from agent.bot import kayfa_agent, KayfaDeps
from agent.rag import kayfa_db
from database.mongo import save_chat_turn
from app.utils import render_text
from database.mongo import load_session, save_session_state

st.set_page_config(page_title="Kayfa Assistant", page_icon="💬", layout="centered")

st.title("Kayfa AI Assistant 💬")
st.markdown("Chat with our agent to find your perfect course or diploma.")


# 1. Initialize Session States
if "session_id" not in st.session_state:
    # In a real app, this might come from a login or URL param.
    st.session_state.session_id = str(uuid.uuid4())

# Load the exact state from MongoDB to prevent the memory-wipe bug
if "messages" not in st.session_state or "history" not in st.session_state:
    ui_msgs, agent_hist = load_session(st.session_state.session_id)
    st.session_state.messages = ui_msgs
    st.session_state.history = agent_hist

# PydanticAI's internal memory (ModelMessage objects)
if "history" not in st.session_state:
    st.session_state.history = []

# 2. Render Existing Conversation
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # Use our utility to correctly format Arabic or English
        formatted_text = render_text(msg["content"])
        st.markdown(formatted_text, unsafe_allow_html=True)

# 3. The Chat Input Loop
if prompt := st.chat_input("Ask me about our courses, prices, or diplomas..."):
    
    # --- USER TURN ---
    # Append to UI memory and render
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(render_text(prompt), unsafe_allow_html=True)
        
    # Save to MongoDB
    save_chat_turn(st.session_state.session_id, "user", prompt)

    # --- AGENT TURN ---
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            
            # Inject dependencies (our knowledge base)
            deps = KayfaDeps(db=kayfa_db)
            
            # Run the agent synchronously, passing in the existing history
            result = kayfa_agent.run_sync(
                prompt,
                deps=deps,
                message_history=st.session_state.history
            )
            
            # Render the final response using the RTL helper
            st.markdown(render_text(result.output), unsafe_allow_html=True)
            
    # Update UI memory
    st.session_state.messages.append({"role": "assistant", "content": result.output})    
    # Update PydanticAI history
    st.session_state.history += result.new_messages()
    
    # NEW: Save the entire dual-track state to MongoDB Atlas
    save_session_state(
        st.session_state.session_id, 
        st.session_state.messages, 
        st.session_state.history
    )