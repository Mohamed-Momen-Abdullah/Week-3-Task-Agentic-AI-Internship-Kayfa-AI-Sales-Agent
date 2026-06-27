import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from database.mongo import get_all_tickets
from app.utils import inject_custom_css, render_header, get_theme_colors
from app.auth import require_auth, logout, get_current_user

st.set_page_config(
    page_title="Kayfa CRM Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth guard — agents only ──────────────────────────────────────────────────
require_auth(role="agent")

# ── Theme ─────────────────────────────────────────────────────────────────────
c = inject_custom_css()

# Hide sidebar nav so agents can't navigate to the customer chat page
st.markdown(
    "<style>[data-testid='stSidebarNav']{display:none;}</style>",
    unsafe_allow_html=True,
)

agent = get_current_user()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"<div style='padding:0.5rem 0 1rem;'>"
        f"<span style='font-size:0.8rem;color:{c['text_muted']};text-transform:uppercase;"
        f"letter-spacing:.05em;'>SALES AGENT</span><br>"
        f"<strong style='font-size:1rem;color:{c['text']};'>👤 {agent['username']}</strong>"
        f"</div>",
        unsafe_allow_html=True,
    )
    
    # --- ADD THIS NEW BUTTON ---
    if st.button("⚡ Token Metrics", width="stretch"):
        st.switch_page("pages/3_Token_Metrics.py")
    # ---------------------------
        
    st.markdown(
        f"<hr style='border-color:{c['card_border']};margin:0.5rem 0 1rem;'>",
        unsafe_allow_html=True,
    )
    if st.button("🚪  Sign Out", width="stretch"):
        logout()

# ── Header ────────────────────────────────────────────────────────────────────
render_header(
    "CRM Lead Tickets",
    "Review captured leads and follow up with prospective learners",
)

# ── Tickets ───────────────────────────────────────────────────────────────────
tickets = get_all_tickets()

if not tickets:
    st.info("No leads captured yet. Go back to the Chat Agent and try matching a lead!")
else:
    st.metric("Total Qualified Leads", len(tickets))
    st.divider()

    for t in tickets:
        name = t.get("customer_name", "غير معروف")
        timestamp = t.get("timestamp", "N/A")
        signals = t.get("buying_signals", "ساخن")
        lead_id = str(t.get("_id"))[-6:].upper()
        contact = t.get("contact_info", "")
        city = t.get("city", "")
        dialect = t.get("language_dialect", "")
        products = t.get("products_of_interest", "")
        goal = t.get("goal", "")
        level = t.get("current_level", "")
        objections = t.get("objections", "")
        summary = t.get("arabic_summary", "")
        next_action = t.get("next_action", "")

        card_content = f"""
        <div dir="rtl" style="background-color: {c['card_bg']}; border: 1px solid {c['card_border']}; border-radius: 12px; padding: 20px; margin-bottom: 20px; text-align: right; font-family: sans-serif; color: {c['text']};">
            <div style="display: flex; justify-content: space-between; border-bottom: 2px solid {c['card_border']}; padding-bottom: 8px; margin-bottom: 12px;">
                <span style="background-color: {c['danger_bg']}; color: {c['danger_text']}; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;">{signals}</span>
                <span style="color: {c['text_muted']}; font-size: 14px; font-weight: bold;">LEAD-{lead_id}</span>
            </div>
            <p style="margin: 6px 0;"><strong>الاسم:</strong> {name}</p>
            <p style="margin: 6px 0;"><strong>رقم التواصل:</strong> <span dir="ltr">{contact}</span></p>
            <p style="margin: 6px 0;"><strong>المدينة:</strong> {city}</p>
            <p style="margin: 6px 0;"><strong>اللغة / اللهجة:</strong> {dialect}</p>
            <p style="margin: 6px 0; color: {c['primary']};"><strong>المنتجات محل الاهتمام:</strong> {products}</p>
            <p style="margin: 6px 0;"><strong>الهدف:</strong> {goal}</p>
            <p style="margin: 6px 0;"><strong>المستوى الحالي:</strong> {level}</p>
            <p style="margin: 6px 0; color: {c['warning_text']};"><strong>الاعتراضات:</strong> {objections}</p>
            <div style="background: {c['bg']}; padding: 10px; border-radius: 6px; margin-top: 10px; border-left: 4px solid {c['primary']};">
                <strong>ملخّص المحادثة:</strong>
                <p style="margin: 4px 0; line-height: 1.5; color: {c['text']};">{summary}</p>
            </div>
            <p style="margin: 10px 0 0 0; color: {c['success_text']};"><strong>الإجراء التالي:</strong> {next_action}</p>
            <p style="margin: 8px 0 0 0; color: {c['text_muted']}; font-size: 12px;" dir="ltr">التاريخ: {timestamp}</p>
        </div>
        """
        st.markdown(card_content, unsafe_allow_html=True)