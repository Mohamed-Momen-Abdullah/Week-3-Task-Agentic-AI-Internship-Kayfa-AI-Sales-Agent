import os
import hashlib
import streamlit as st
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
from pydantic_ai.messages import ModelMessagesTypeAdapter

load_dotenv()

try:
    MONGO_URI = st.secrets["MONGO_URI"]
except (FileNotFoundError, KeyError):
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
db = client.kayfa_crm


# ─── USER AUTH ────────────────────────────────────────────────────────────────

def get_user(username: str) -> dict | None:
    return db.users.find_one({"username": username}, {"_id": 0})


def create_user(username: str, password: str, role: str) -> bool:
    username = username.strip().lower()
    if db.users.find_one({"username": username}):
        return False
    db.users.insert_one({
        "username": username,
        "password_hash": hashlib.sha256(password.encode()).hexdigest(),
        "role": role,
        "created_at": datetime.now().isoformat(),
    })
    return True


# ─── CHAT SESSIONS ────────────────────────────────────────────────────────────

def save_session_state(session_id, ui_messages, agent_history, username=None):
    history_dump = ModelMessagesTypeAdapter.dump_python(agent_history)
    update_doc = {
        "messages": ui_messages,
        "history": history_dump,
        "last_updated": datetime.now().isoformat(),
    }
    if username:
        update_doc["username"] = username
    db.chat_sessions.update_one(
        {"session_id": session_id},
        {"$set": update_doc},
        upsert=True,
    )


def load_session(session_id: str):
    record = db.chat_sessions.find_one({"session_id": session_id})
    if record:
        ui_msgs = record.get("messages", [])
        agent_hist = ModelMessagesTypeAdapter.validate_python(record.get("history", []))
        return ui_msgs, agent_hist
    return [], []


def get_user_sessions(username: str) -> list[dict]:
    raw = list(
        db.chat_sessions.find(
            {"username": username},
            {"session_id": 1, "messages": 1, "last_updated": 1, "_id": 0},
        ).sort("last_updated", -1)
    )
    result = []
    for s in raw:
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


def delete_session(session_id: str) -> None:
    db.chat_sessions.delete_one({"session_id": session_id})
    db.messages.delete_many({"session_id": session_id})


# ─── TICKETS ──────────────────────────────────────────────────────────────────

def save_ticket(ticket_data: dict):
    session_id = ticket_data.get("session_id")
    ticket_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    if session_id:
        db.tickets.update_one(
            {"session_id": session_id},
            {
                "$set": ticket_data,
                "$setOnInsert": {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "status": "Open",
                },
            },
            upsert=True,
        )
    else:
        ticket_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        ticket_data["status"] = "Open"
        db.tickets.insert_one(ticket_data)


def get_all_tickets():
    return list(db.tickets.find().sort("timestamp", -1))


# ─── MESSAGES ─────────────────────────────────────────────────────────────────

def save_chat_turn(session_id: str, role: str, content: str):
    db.messages.insert_one({
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    })


def get_chat_history(session_id: str):
    return list(db.messages.find({"session_id": session_id}).sort("timestamp", 1))


# ─── USAGE LOGS & COST TRACKING ───────────────────────────────────────────────

def save_usage_log(log_data: dict):
    """Inserts one usage log record per agent turn."""
    db.usage_logs.insert_one(log_data)


def get_all_usage_logs() -> list[dict]:
    """Returns all usage logs, newest first, without MongoDB _id."""
    return list(db.usage_logs.find({}, {"_id": 0}).sort("timestamp", -1))


def get_cost_by_user() -> list[dict]:
    """Aggregates total cost and tokens per user, sorted by spend."""
    pipeline = [
        {"$group": {
            "_id":          "$user_id",
            "total_cost":   {"$sum": "$total_cost"},
            "total_tokens": {"$sum": {"$add": ["$input_tokens", "$output_tokens"]}},
            "message_count":{"$sum": 1},
        }},
        {"$sort": {"total_cost": -1}},
    ]
    return list(db.usage_logs.aggregate(pipeline))


def get_daily_cost_trend() -> list[dict]:
    """Aggregates cost per calendar day for the trend bar chart."""
    pipeline = [
        {"$addFields": {
            "date": {"$substr": ["$timestamp", 0, 10]}   # YYYY-MM-DD
        }},
        {"$group": {
            "_id":        "$date",
            "daily_cost": {"$sum": "$total_cost"},
            "messages":   {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    return list(db.usage_logs.aggregate(pipeline))


def get_sessions_with_logs() -> list[dict]:
    """
    Returns one summary document per session that has usage logs, newest first.
    Fields: _id (session_id), user_id, message_count, total_cost,
            total_tokens, avg_latency, last_timestamp, first_response.
    Used to populate the Monitor B session dropdown.
    """
    pipeline = [
        {"$group": {
            "_id":            "$session_id",
            "user_id":        {"$first": "$user_id"},
            "message_count":  {"$sum": 1},
            "total_cost":     {"$sum": "$total_cost"},
            "total_tokens":   {"$sum": {"$add": ["$input_tokens", "$output_tokens"]}},
            "avg_latency":    {"$avg": "$latency"},
            "last_timestamp": {"$max": "$timestamp"},
            "first_response": {"$first": "$final_response"},
        }},
        {"$sort": {"last_timestamp": -1}},
    ]
    return list(db.usage_logs.aggregate(pipeline))


def get_session_trace(session_id: str) -> list[dict]:
    """Returns all usage log records for a single session, oldest first (for replay)."""
    return list(
        db.usage_logs.find({"session_id": session_id}, {"_id": 0}).sort("timestamp", 1)
    )

# ─── SEMANTIC CACHE ───────────────────────────────────────────────────────────

def cache_lookup() -> list[dict]:
    """
    Returns all documents in the semantic_cache collection.
    Each doc has: query (str), embedding (list[float]), response (str).
    """
    return list(db.semantic_cache.find({}, {"_id": 0}))


def cache_store(entry: dict) -> None:
    """
    Inserts a new cache entry.
    entry must contain: query, embedding, response.
    Skips insertion if the exact same query string is already stored
    (prevents duplicates on concurrent identical requests).
    """
    db.semantic_cache.update_one(
        {"query": entry["query"]},
        {"$setOnInsert": entry},
        upsert=True,
    )