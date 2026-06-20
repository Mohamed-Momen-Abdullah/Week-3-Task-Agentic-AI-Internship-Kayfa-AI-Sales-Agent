import os
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
from pydantic_ai.messages import ModelMessagesTypeAdapter

load_dotenv()


# This automatically falls back to local only if Atlas URI isn't in your .env
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client.kayfa_crm

def save_session_state(session_id: str, ui_messages: list, agent_history: list):
    """Saves both the UI track and Agent track to MongoDB to survive refreshes."""
    
    # Convert complex ModelMessage objects (including tool calls) to JSON-safe dicts
    history_dump = ModelMessagesTypeAdapter.dump_python(agent_history)
    
    db.chat_sessions.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "messages": ui_messages,
                "history": history_dump,
                "last_updated": datetime.now().isoformat()
            }
        },
        upsert=True
    )

def load_session(session_id: str):
    """Reconstructs both memory tracks using the TypeAdapter."""
    record = db.chat_sessions.find_one({"session_id": session_id})
    if record:
        ui_msgs = record.get("messages", [])
        # Reconstruct the strict ModelMessage objects for PydanticAI's context
        agent_hist = ModelMessagesTypeAdapter.validate_python(record.get("history", []))
        return ui_msgs, agent_hist
    return [], []

def save_ticket(ticket_data: dict):
    """Injects a timestamp and saves the Pydantic dictionary to MongoDB."""
    ticket_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    ticket_data["status"] = "Open"
    db.tickets.insert_one(ticket_data)
    
def save_chat_turn(session_id: str, role: str, content: str):
    """Saves a single conversation turn to MongoDB for dual-track memory."""
    db.messages.insert_one({
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })

def get_chat_history(session_id: str):
    """Retrieves standard chat history for Streamlit UI rendering."""
    return list(db.messages.find({"session_id": session_id}).sort("timestamp", 1))

def get_all_tickets():
    """Fetches all CRM tickets, newest first."""
    return list(db.tickets.find().sort("timestamp", -1))