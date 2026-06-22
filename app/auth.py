import hashlib
import streamlit as st
from database.mongo import get_user


def _hash(password: str) -> str:
    """SHA-256 hash — passwords are never stored in plain text."""
    return hashlib.sha256(password.encode()).hexdigest()


def login(username: str, password: str) -> dict | None:
    """
    Verify credentials against the MongoDB `users` collection.
    Returns a user dict {"username": ..., "role": ...} on success, else None.
    """
    user = get_user(username.strip().lower())
    if user and user.get("password_hash") == _hash(password):
        return {"username": user["username"], "role": user["role"]}
    return None


def is_logged_in() -> bool:
    return bool(st.session_state.get("user"))


def get_current_user() -> dict | None:
    return st.session_state.get("user")


def logout():
    """Wipe the entire session and redirect to the login page."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.switch_page("main.py")


def require_auth(role: str = None):
    """
    Guard function — call at the very top of every protected page (before any
    other Streamlit calls).

    - Not logged in  → redirect to login
    - Wrong role     → show error and hard-stop
    """
    if not is_logged_in():
        st.switch_page("main.py")
        st.stop()
    if role and st.session_state.user.get("role") != role:
        st.error("⛔ Access denied — you don't have permission to view this page.")
        st.stop()