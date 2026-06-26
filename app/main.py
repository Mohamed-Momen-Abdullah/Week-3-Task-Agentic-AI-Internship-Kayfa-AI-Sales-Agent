import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
from app.utils import inject_custom_css, get_theme_colors
from app.auth import login, is_logged_in
from database.mongo import create_user

st.set_page_config(
    page_title="Kayfa — Welcome",
    page_icon="🔐",
    layout="centered",
    initial_sidebar_state="collapsed",
)

inject_custom_css()

# Hide sidebar page navigation — user hasn't logged in yet
st.markdown(
    "<style>[data-testid='stSidebarNav']{display:none;}</style>",
    unsafe_allow_html=True,
)

# Already authenticated → bounce to correct page immediately
if is_logged_in():
    if st.session_state.user["role"] == "agent":
        st.switch_page("pages/2_CRM_Tickets.py")
    else:
        st.switch_page("pages/1_Chat.py")

c = get_theme_colors()

# ── Centered card ─────────────────────────────────────────────────────────────
_, mid, _ = st.columns([1, 1.4, 1])
with mid:
    st.markdown("<div style='height:6vh'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        _, logocol, _ = st.columns([1, 1, 1])
        with logocol:
            st.image("app/kayfa_logo_light.png", width=72)

        st.markdown(
            f"<h3 style='text-align:center;margin:0.75rem 0 0.1rem;color:{c['text']};'>"
            f"Welcome to Kayfa</h3>"
            f"<p style='text-align:center;color:{c['text_muted']};margin-bottom:1.25rem;'>"
            f"Your AI-powered sales assistant</p>",
            unsafe_allow_html=True,
        )

        sign_in_tab, sign_up_tab = st.tabs(["Sign In", "Sign Up"])

        # ── SIGN IN ───────────────────────────────────────────────────────────
        with sign_in_tab:
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

            username_in = st.text_input(
                "Username",
                placeholder="Your username",
                key="signin_username",
                label_visibility="collapsed",
            )
            password_in = st.text_input(
                "Password",
                type="password",
                placeholder="Your password",
                key="signin_password",
                label_visibility="collapsed",
            )

            if st.button("Sign In", type="primary", use_container_width=True, key="signin_btn"):
                if not username_in or not password_in:
                    st.error("Please fill in both fields.")
                else:
                    user = login(username_in, password_in)
                    if user:
                        st.session_state.user = user
                        if user["role"] == "agent":
                            st.switch_page("pages/2_CRM_Tickets.py")
                        else:
                            st.switch_page("pages/1_Chat.py")
                    else:
                        st.error("Incorrect username or password.")

        # ── SIGN UP ───────────────────────────────────────────────────────────
        with sign_up_tab:
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

            new_username = st.text_input(
                "Username",
                placeholder="Choose a username",
                key="signup_username",
                label_visibility="collapsed",
            )
            new_password = st.text_input(
                "Password",
                type="password",
                placeholder="Choose a password (min 6 characters)",
                key="signup_password",
                label_visibility="collapsed",
            )
            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
                placeholder="Repeat your password",
                key="signup_confirm",
                label_visibility="collapsed",
            )

            role_choice = st.radio(
                "Account type",
                options=["Customer", "Agent"],
                horizontal=True,
                key="signup_role",
            )

            # Agents must provide a secret code set in secrets.toml
            agent_code_input = ""
            if role_choice == "Agent":
                agent_code_input = st.text_input(
                    "Agent Code",
                    type="password",
                    placeholder="Enter the agent access code",
                    key="signup_agent_code",
                    label_visibility="collapsed",
                )
                st.markdown(
                    f"<p style='font-size:0.78rem;color:{c['text_muted']};margin-top:2px;'>"
                    f"Contact your admin for the agent access code.</p>",
                    unsafe_allow_html=True,
                )

            if st.button("Create Account", type="primary", use_container_width=True, key="signup_btn"):
                error = None

                if not new_username or not new_password or not confirm_password:
                    error = "Please fill in all fields."
                elif len(new_username.strip()) < 3:
                    error = "Username must be at least 3 characters."
                elif len(new_password) < 6:
                    error = "Password must be at least 6 characters."
                elif new_password != confirm_password:
                    error = "Passwords don't match."
                elif role_choice == "Agent":
                    expected_code = st.secrets.get("agent_signup_code", "")
                    if not expected_code:
                        error = "Agent sign-up is not configured. Contact your admin."
                    elif agent_code_input != expected_code:
                        error = "Invalid agent access code."

                if error:
                    st.error(error)
                else:
                    role = role_choice.lower()
                    success = create_user(new_username.strip(), new_password, role)

                    if not success:
                        st.error("That username is already taken — please choose another.")
                    else:
                        user = login(new_username.strip(), new_password)
                        if user:
                            st.session_state.user = user
                            st.success(f"Account created! Welcome, {user['username']} 👋")
                            st.balloons()
                            import time; time.sleep(1)
                            if user["role"] == "agent":
                                st.switch_page("pages/2_CRM_Tickets.py")
                            else:
                                st.switch_page("pages/1_Chat.py")