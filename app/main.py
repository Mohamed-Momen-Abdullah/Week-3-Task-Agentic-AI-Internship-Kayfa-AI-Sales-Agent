import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
from app.utils import inject_custom_css, get_theme_colors
from app.auth import login, is_logged_in

st.set_page_config(
    page_title="Kayfa — Sign In",
    page_icon="🔐",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Theme must be injected first so the login card is styled correctly
inject_custom_css()

# Hide sidebar page navigation — visitors haven't logged in yet
st.markdown(
    "<style>[data-testid='stSidebarNav']{display:none;}</style>",
    unsafe_allow_html=True,
)

# ── Already authenticated? Bounce straight to the correct page ────────────────
if is_logged_in():
    if st.session_state.user["role"] == "agent":
        st.switch_page("pages/2_CRM_Tickets.py")
    else:
        st.switch_page("pages/1_Chat.py")

c = get_theme_colors()

# ── Centered login card ───────────────────────────────────────────────────────
_, mid, _ = st.columns([1, 1.4, 1])
with mid:
    st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        # Logo
        _, logocol, _ = st.columns([1, 1, 1])
        with logocol:
            st.image("app/kayfa_logo_light.png", width=72)

        st.markdown(
            f"<h3 style='text-align:center;margin:0.75rem 0 0.25rem;color:{c['text']};'>"
            f"Welcome back</h3>"
            f"<p style='text-align:center;color:{c['text_muted']};margin-bottom:1.25rem;'>"
            f"Sign in to your Kayfa account</p>",
            unsafe_allow_html=True,
        )

        username_input = st.text_input(
            "Username",
            placeholder="Enter your username",
            key="login_username",
            label_visibility="collapsed",
        )
        password_input = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your password",
            key="login_password",
            label_visibility="collapsed",
        )

        if st.button("Sign In", type="primary", use_container_width=True):
            if not username_input or not password_input:
                st.error("Please fill in both fields.")
            else:
                user = login(username_input, password_input)
                if user:
                    st.session_state.user = user
                    # Role-based redirect
                    if user["role"] == "agent":
                        st.switch_page("pages/2_CRM_Tickets.py")
                    else:
                        st.switch_page("pages/1_Chat.py")
                else:
                    st.error("Incorrect username or password — please try again.")