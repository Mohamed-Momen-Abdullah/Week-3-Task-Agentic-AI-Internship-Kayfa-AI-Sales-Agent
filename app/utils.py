import re
import streamlit as st


def get_theme_colors() -> dict:
    """
    Single source of truth for every color used in the app.
    Light mode is the default/primary look now — dark mode is the
    secondary option via the sidebar toggle.
    """
    if "theme" not in st.session_state:
        st.session_state.theme = "light"

    if st.session_state.theme == "dark":
        return {
            "mode": "dark",
            "bg": "#0b0f19",
            "bg_secondary": "#11151f",
            "card_bg": "#161b27",
            "card_border": "#262c3a",
            "text": "#f3f4f6",
            "text_muted": "#9aa3b2",
            "primary": "#818cf8",
            "primary_hover": "#a5b4fc",
            "primary_text": "#0b0f19",
            "danger_bg": "#3f1d1d",
            "danger_text": "#fca5a5",
            "success_text": "#4ade80",
            "warning_text": "#fbbf24",
            "input_bg": "#161b27",
            "shadow": "rgba(0, 0, 0, 0.45)",
        }

    return {
        "mode": "light",
        "bg": "#fafafa",
        "bg_secondary": "#ffffff",
        "card_bg": "#ffffff",
        "card_border": "#e5e7eb",
        "text": "#111827",
        "text_muted": "#6b7280",
        "primary": "#4f46e5",
        "primary_hover": "#4338ca",
        "primary_text": "#ffffff",
        "danger_bg": "#fee2e2",
        "danger_text": "#b91c1c",
        "success_text": "#15803d",
        "warning_text": "#92400e",
        "input_bg": "#ffffff",
        "shadow": "rgba(17, 24, 39, 0.07)",
    }


def render_text(text: str) -> str:
    """Wraps Arabic text in an RTL container; passes LTR text through unchanged."""
    if not text:
        return text

    has_arabic = bool(re.search(r'[\u0600-\u06FF]', text))
    if has_arabic:
        return (
            '<div dir="rtl" style="text-align: right; '
            "font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; "
            'line-height: 1.6;">'
            f'{text}</div>'
        )
    return text


def inject_custom_css() -> dict:
    """
    Renders the light/dark toggle in the sidebar and injects CSS that re-skins
    every native widget — chat input, chat bubbles, buttons, text inputs,
    metrics, sidebar nav — to a modern look, in both themes.

    Call this FIRST on every page, before require_password(). Returns the
    active color dict so the page can reuse the same tokens elsewhere
    (e.g. the ticket cards' inline HTML).
    """
    if "theme" not in st.session_state:
        st.session_state.theme = "light"

    with st.sidebar:
        st.markdown("##### ⚙️ Display")
        is_light = st.toggle(
            "☀️ Light mode" if st.session_state.theme == "light" else "🌙 Dark mode",
            value=(st.session_state.theme == "light"),
            key="theme_toggle",
        )
        st.session_state.theme = "light" if is_light else "dark"

    c = get_theme_colors()

    st.markdown(
        f"""
        <style>
            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            header[data-testid="stHeader"] {{
                background-color: transparent;
                box-shadow: none;
            }}
            /* Hide only the Deploy button — not the whole toolbar, which is
               where the sidebar's expand/collapse arrow also lives. */
            [data-testid="stDeployButton"] {{
                display: none;
            }}
            /* Belt-and-suspenders: make sure the sidebar toggle is never
               accidentally caught by any rule above. */
            [data-testid="stSidebarCollapsedControl"],
            [data-testid="stSidebarCollapseButton"] {{
                visibility: visible !important;
                opacity: 1 !important;
                display: flex !important;
            }}

            .stApp {{
                background-color: {c['bg']};
                color: {c['text']};
            }}

            /* The chat input lives in a fixed bottom bar that sits outside
               .stApp, so it needs its own background override. */
            div[data-testid="stBottom"],
            div[data-testid="stBottom"] > div,
            div[data-testid="stBottomBlockContainer"],
            .stChatFloatingInputContainer {{
                background-color: {c['bg']} !important;
                background-image: none !important;
            }}

            .block-container {{
                padding-top: 1.5rem;
                padding-bottom: 6rem;
            }}

            /* ---------- Sidebar ---------- */
            section[data-testid="stSidebar"] {{
                background-color: {c['bg_secondary']};
                border-right: 1px solid {c['card_border']};
            }}
            section[data-testid="stSidebar"] * {{
                color: {c['text']} !important;
            }}
            [data-testid="stSidebarNav"] {{
                padding-top: 0.25rem;
            }}
            [data-testid="stSidebarNav"] li {{
                margin: 2px 8px;
            }}
            [data-testid="stSidebarNav"] a {{
                border-radius: 10px !important;
                padding: 0.5rem 0.9rem !important;
                font-weight: 500;
                transition: background-color .15s ease;
            }}
            [data-testid="stSidebarNav"] a:hover {{
                background-color: {c['primary']}15 !important;
            }}
            [data-testid="stSidebarNav"] a[aria-current="page"] {{
                background-color: {c['primary']}20 !important;
                color: {c['primary']} !important;
                font-weight: 700;
            }}

            /* ---------- Chat bubbles ---------- */
            [data-testid="stChatMessage"] {{
                background-color: {c['card_bg']};
                border: 1px solid {c['card_border']};
                border-radius: 14px;
                padding: 0.75rem 1rem;
                margin-bottom: 0.6rem;
                box-shadow: 0 1px 3px {c['shadow']};
            }}
            [data-testid="stChatMessage"] p,
            [data-testid="stChatMessage"] div,
            [data-testid="stChatMessage"] span {{
                color: {c['text']} !important;
            }}
            /* Tint the user's own messages so the thread reads at a glance */
            [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
                background-color: {c['primary']}0d;
                border-color: {c['primary']}33;
            }}

            /* ---------- Chat input ---------- */
            [data-testid="stChatInput"], 
            [data-testid="stChatInput"] > div {{
                background-color: {c['input_bg']} !important;
                border-color: {c['card_border']} !important;
            }}
            [data-testid="stChatInput"] {{
                border: 1px solid {c['card_border']};
                border-radius: 14px;
                box-shadow: 0 1px 2px {c['shadow']};
            }}
            
            /* Target the textarea AND Streamlit's internal Base Web wrappers */
            [data-testid="stChatInput"] textarea,
            [data-testid="stChatInput"] div[data-baseweb="textarea"],
            [data-testid="stChatInput"] div[data-baseweb="base-input"] {{
                color: {c['text']} !important;
                background-color: transparent !important;
                border: none !important;
            }}
            
            [data-testid="stChatInput"] textarea::placeholder {{
                color: {c['text_muted']} !important;
            }}
            /* ---------- Buttons ---------- */
            .stButton > button[kind="primary"], .stDownloadButton > button {{
                background-color: {c['primary']};
                color: {c['primary_text']};
                border: none;
                border-radius: 10px;
                font-weight: 600;
                transition: background-color 0.15s ease;
            }}
            .stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {{
                background-color: {c['primary_hover']};
                color: {c['primary_text']};
            }}
            /* Plain st.button() defaults to "secondary" — used for suggestion chips */
            .stButton > button[kind="secondary"] {{
                background-color: {c['card_bg']};
                color: {c['text']};
                border: 1px solid {c['card_border']};
                border-radius: 12px;
                font-weight: 500;
                text-align: left;
                padding: 0.65rem 1rem;
            }}
            .stButton > button[kind="secondary"]:hover {{
                border-color: {c['primary']};
                color: {c['primary']};
                background-color: {c['primary']}0d;
            }}

            /* ---------- Text inputs (incl. password box) ---------- */
            .stTextInput input, .stTextArea textarea {{
                background-color: {c['input_bg']} !important;
                color: {c['text']} !important;
                border: 1px solid {c['card_border']} !important;
                border-radius: 10px !important;
                padding: 0.6rem 0.85rem !important;
            }}

            /* ---------- Alerts / Metrics ---------- */
            div[data-testid="stAlert"] {{ border-radius: 10px; }}
            div[data-testid="stMetric"] {{
                background-color: {c['card_bg']};
                border: 1px solid {c['card_border']};
                border-radius: 12px;
                padding: 1rem;
            }}
            div[data-testid="stMetricValue"] {{ color: {c['primary']} !important; }}
            div[data-testid="stMetricLabel"] {{ color: {c['text_muted']} !important; }}

            /* ---------- Bordered containers (login card, etc.) ---------- */
            div[data-testid="stVerticalBlockBorderWrapper"] {{
                background-color: {c['card_bg']} !important;
                border: 1px solid {c['card_border']} !important;
                border-radius: 16px;
                padding: 1.5rem;
                color: {c['text']} !important;
                box-shadow: 0 4px 16px {c['shadow']};
            }}
            div[data-testid="stVerticalBlockBorderWrapper"] h1,
            div[data-testid="stVerticalBlockBorderWrapper"] h2,
            div[data-testid="stVerticalBlockBorderWrapper"] h3,
            div[data-testid="stVerticalBlockBorderWrapper"] p {{
                color: {c['text']} !important;
            }}

            hr {{ border-color: {c['card_border']}; }}
            a {{ color: {c['primary']}; }}

            /* ---------- App bar logo, flush right ---------- */
            div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child img {{
                margin-left: auto;
                display: block;
            }}

            /* ---------- Empty-state hero ---------- */
            .kayfa-hero {{
                text-align: center;
                padding: 2.5rem 1rem 1.75rem;
            }}
            .kayfa-hero h1 {{
                font-size: 1.85rem;
                font-weight: 700;
                margin-bottom: 0.5rem;
                color: {c['text']};
            }}
            .kayfa-hero p {{
                color: {c['text_muted']};
                font-size: 1.05rem;
                margin: 0;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    return c


def render_header(title: str, subtitle: str = None, logo_width: int = 56) -> None:
    """
    Slim top app bar: title (+ optional subtitle) on the left, small Kayfa
    logo flush right, thin divider underneath. Call right after
    require_password() on every page.
    """
    c = get_theme_colors()
    left, right = st.columns([6, 1])
    with left:
        st.markdown(
            f"<div style='font-size:1.3rem;font-weight:700;color:{c['text']};'>{title}</div>",
            unsafe_allow_html=True,
        )
        if subtitle:
            st.markdown(
                f"<div style='font-size:0.9rem;color:{c['text_muted']};margin-top:2px;'>{subtitle}</div>",
                unsafe_allow_html=True,
            )
    with right:
        st.image("app/kayfa_logo_light.png", width=logo_width)
    st.markdown(
        f"<hr style='margin:0.75rem 0 1.5rem 0;border-color:{c['card_border']};'>",
        unsafe_allow_html=True,
    )


def require_password(app_title: str = "Kayfa") -> bool:
    """
    Modern centered login card. Returns True once the correct password has
    been entered. Call this AFTER inject_custom_css(); st.stop() immediately
    if it returns False.
    """
    if st.session_state.get("password_correct"):
        return True

    c = get_theme_colors()

    def _password_entered():
        if st.session_state["password"] == st.secrets["app_password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            _, logocol, _ = st.columns([1, 1, 1])
            with logocol:
                st.image("app/kayfa_logo_light.png", width=72)

            st.markdown(
                f"<h3 style='text-align:center;margin:0.75rem 0 0.25rem;color:{c['text']};'>Welcome back</h3>"
                f"<p style='text-align:center;color:{c['text_muted']};margin-bottom:1rem;'>"
                f"Enter your password to access {app_title}</p>",
                unsafe_allow_html=True,
            )

            st.text_input(
                "Password",
                type="password",
                on_change=_password_entered,
                key="password",
                label_visibility="collapsed",
                placeholder="Enter password",
            )

            if st.session_state.get("password_correct") is False:
                st.error("Incorrect password — please try again.")

    return bool(st.session_state.get("password_correct"))