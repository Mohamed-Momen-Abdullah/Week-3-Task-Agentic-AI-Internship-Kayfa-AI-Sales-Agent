import os
import hashlib
import streamlit as st
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
from pydantic_ai.messages import ModelMessagesTypeAdapter

load_dotenv()

# Prioritize Streamlit secrets, fallback to OS environment, then local host
try:
    MONGO_URI = st.secrets["MONGO_URI"]
except (FileNotFoundError, KeyError):
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
db = client.kayfa_crm


# ─── USER AUTH ────────────────────────────────────────────────────────────────

def get_user(username: str) -> dict | None:
    """Fetch a user document by username. Returns None if not found."""
    return db.users.find_one({"username": username}, {"_id": 0})


def create_user(username: str, password: str, role: str) -> bool:
    """
    Create a new user in the `users` collection.
    Password is stored as a SHA-256 hash — never in plain text.
    Returns False if the username already exists, True on success.
    Roles should be either "customer" or "agent".
    """
    username = username.strip().lower()
    if db.users.find_one({"username": username}):
        return False  # username already taken
    db.users.insert_one({
        "username": username,
        "password_hash": hashlib.sha256(password.encode()).hexdigest(),
        "role": role,
        "created_at": datetime.now().isoformat(),
    })
    return True


# ─── CHAT SESSIONS ────────────────────────────────────────────────────────────

def save_session_state(
    session_id: str,
    ui_messages: list,
    agent_history: list,
    username: str = None,   # ← NEW: tag the session with the owner's username
):
    """
    Saves both the UI track and Agent track to MongoDB to survive refreshes.
    The optional `username` parameter lets us query sessions per user later.
    """
    history_dump = ModelMessagesTypeAdapter.dump_python(agent_history)

    update_doc = {
        "messages": ui_messages,
        "history": history_dump,
        "last_updated": datetime.now().isoformat(),
    }
    # Only set username on the document if provided (backwards-compatible)
    if username:
        update_doc["username"] = username

    db.chat_sessions.update_one(
        {"session_id": session_id},
        {"$set": update_doc},
        upsert=True,
    )


def load_session(session_id: str):
    """Reconstructs both memory tracks using the TypeAdapter."""
    record = db.chat_sessions.find_one({"session_id": session_id})
    if record:
        ui_msgs = record.get("messages", [])
        agent_hist = ModelMessagesTypeAdapter.validate_python(record.get("history", []))
        return ui_msgs, agent_hist
    return [], []


def get_user_sessions(username: str) -> list[dict]:
    """
    Returns all chat sessions belonging to `username`, newest first.
    Each item contains:
      - session_id
      - last_updated  (ISO string)
      - preview       (first 60 chars of the user's opening message)
      - messages      (full list, for the read-only history sidebar)
    """
    raw_sessions = list(
        db.chat_sessions.find(
            {"username": username},
            {"session_id": 1, "messages": 1, "last_updated": 1, "_id": 0},
        ).sort("last_updated", -1)
    )

    result = []
    for s in raw_sessions:
        messages = s.get("messages", [])
        first_user_msg = next(
            (m["content"] for m in messages if m.get("role") == "user"),
            "New conversation",
        )
        result.append({
            "session_id": s["session_id"],
            "last_updated": s.get("last_updated", ""),
            "preview": first_user_msg[:60] + ("…" if len(first_user_msg) > 60 else ""),
            "messages": messages,
        })
    return result


# ─── TICKETS ──────────────────────────────────────────────────────────────────

def save_ticket(ticket_data: dict):
    """Injects a timestamp and saves the Pydantic dictionary to MongoDB."""
    ticket_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    ticket_data["status"] = "Open"
    db.tickets.insert_one(ticket_data)


def get_all_tickets():
    """Fetches all CRM tickets, newest first."""
    return list(db.tickets.find().sort("timestamp", -1))


# ─── MESSAGES (individual turns) ──────────────────────────────────────────────

def save_chat_turn(session_id: str, role: str, content: str):
    """Saves a single conversation turn to MongoDB for dual-track memory."""
    db.messages.insert_one({
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    })


def get_chat_history(session_id: str):
    """Retrieves standard chat history for Streamlit UI rendering."""
    return list(db.messages.find({"session_id": session_id}).sort("timestamp", 1))